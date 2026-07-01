import uuid
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.celery_app import celery_app
from backend.workers.report_job import run_report_job

router = APIRouter(prefix="/api/reports", tags=["reports"])


class CreateReportRequest(BaseModel):
    source_ids: list[UUID]
    date_from: date
    date_to: date


@router.post("/create")
def create_report(payload: CreateReportRequest, db: Session = Depends(get_db)):
    if payload.date_from > payload.date_to:
        raise HTTPException(status_code=400, detail="date_from không được lớn hơn date_to")

    sources = db.query(Source).filter(Source.source_id.in_(payload.source_ids)).all()
    if len(sources) != len(payload.source_ids):
        raise HTTPException(status_code=400, detail="Có source_id không tồn tại")
    if any(not source.is_active for source in sources):
        raise HTTPException(status_code=400, detail="Có nguồn không active")

    task_id = str(uuid.uuid4())
    job = Job(
        source_ids=payload.source_ids,
        date_from=payload.date_from,
        date_to=payload.date_to,
        celery_task_id=task_id,
    )
    db.add(job)
    db.commit()

    run_report_job.apply_async(args=[str(job.job_id)], task_id=task_id)

    return {"job_id": str(job.job_id), "status": job.status}


@router.get("/{job_id}/status")
def get_report_status(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    crawled = db.query(Article).filter_by(job_id=job_id).count()
    analyzed = db.query(ArticleAnalysis).filter_by(job_id=job_id).count()

    return {
        "job_id": str(job.job_id),
        "status": job.status,
        "progress": {"crawled": crawled, "analyzed": analyzed, "total_estimated": crawled},
        "error_log": job.error_log,
        "created_at": job.created_at,
    }


@router.get("/{job_id}/articles")
def get_report_articles(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")

    rows = (
        db.query(Article, ArticleAnalysis)
        .outerjoin(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
        .filter(Article.job_id == job_id)
        .order_by(Article.crawled_at)
        .all()
    )

    articles = []
    for article, analysis in rows:
        analysis_duration = analysis.analysis_duration_seconds if analysis else None
        total_duration = None
        if article.crawl_duration_seconds is not None and analysis_duration is not None:
            total_duration = article.crawl_duration_seconds + analysis_duration
        articles.append(
            {
                "title": article.title,
                "url": article.url,
                "status": article.status,
                "crawl_duration_seconds": article.crawl_duration_seconds,
                "analysis_duration_seconds": analysis_duration,
                "total_duration_seconds": total_duration,
            }
        )

    return {"articles": articles}


@router.post("/{job_id}/cancel")
def cancel_report(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Job không ở trạng thái có thể hủy")

    if job.celery_task_id:
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = "cancelled"
    db.commit()

    return {"job_id": str(job.job_id), "status": job.status}


@router.get("/{job_id}/download")
def download_report(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job không tồn tại")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job chưa hoàn thành")

    return FileResponse(
        job.output_docx,
        filename=f"{job_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
