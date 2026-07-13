import logging
import uuid
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Article, ArticleAnalysis, Job, ReportHistory, Source
from backend.workers.celery_app import celery_app
from backend.workers.report_job import run_report_job

logger = logging.getLogger(__name__)

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

    # Cảnh báo (không chặn) nếu job mới trùng phạm vi ngày + nguồn với job đã completed
    # hoặc đang pending/running trước đó — sau khi bỏ dedup xuyên job (migration 0009),
    # trường hợp này sẽ crawl + phân tích AI lại TOÀN BỘ từ đầu, tốn thời gian đáng kể
    # (AI CPU-only ~90s/bài); nếu job kia đang chạy, còn tranh chấp cùng 1 tiến trình
    # Ollama local, dễ đẩy cả 2 job tới AI timeout.
    overlapping_jobs = (
        db.query(Job)
        .filter(
            Job.status.in_(["completed", "running", "pending"]),
            Job.date_from <= payload.date_to,
            Job.date_to >= payload.date_from,
            Job.source_ids.overlap(payload.source_ids),
        )
        .count()
    )
    if overlapping_jobs > 0:
        logger.warning(
            "Job mới trùng phạm vi ngày/nguồn với %d job đã completed/running/pending "
            "trước đó — sẽ crawl + phân tích AI lại toàn bộ, không dùng lại kết quả cũ",
            overlapping_jobs,
        )

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


@router.get("/history")
def get_report_history(db: Session = Depends(get_db)):
    rows = (
        db.query(ReportHistory, Job)
        .join(Job, Job.job_id == ReportHistory.job_id)
        .order_by(ReportHistory.created_at.desc())
        .all()
    )

    all_source_ids = {source_id for _, job in rows for source_id in (job.source_ids or [])}
    sources_by_id = {}
    if all_source_ids:
        sources_by_id = {
            source.source_id: source.name
            for source in db.query(Source).filter(Source.source_id.in_(all_source_ids)).all()
        }

    history = [
        {
            "report_id": str(report.report_id),
            "job_id": str(job.job_id),
            "file_path": report.file_path,
            "created_at": report.created_at,
            "date_from": job.date_from,
            "date_to": job.date_to,
            "job_status": job.status,
            "source_names": [
                sources_by_id[source_id] for source_id in (job.source_ids or []) if source_id in sources_by_id
            ],
        }
        for report, job in rows
    ]

    return {"history": history}


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
        db.query(Article, ArticleAnalysis, Source)
        .outerjoin(ArticleAnalysis, ArticleAnalysis.article_id == Article.article_id)
        .outerjoin(Source, Source.source_id == Article.source_id)
        .filter(Article.job_id == job_id)
        .order_by(Article.crawled_at)
        .all()
    )

    articles = []
    for article, analysis, source in rows:
        analysis_duration = analysis.analysis_duration_seconds if analysis else None
        total_duration = None
        if article.crawl_duration_seconds is not None and analysis_duration is not None:
            total_duration = article.crawl_duration_seconds + analysis_duration
        articles.append(
            {
                "title": article.title,
                "url": article.url,
                "status": article.status,
                "source_name": source.name if source else None,
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
