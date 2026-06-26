import logging
import os
import time
from datetime import datetime

from backend.ai.ollama_client import analyze_article
from backend.crawler.article import compute_url_hash, fetch_article
from backend.crawler.sitemap import get_article_urls
from backend.db import SessionLocal
from backend.models import Article, ArticleAnalysis, Job, ReportHistory, Source
from backend.report.aggregator import aggregate_basic
from backend.report.docx_generator import export_json, generate_docx
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _crawl_sources(db, job: Job) -> None:
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    for source_id in job.source_ids:
        source = db.get(Source, source_id)
        try:
            candidates = get_article_urls(source, job.date_from, job.date_to)
        except Exception:
            logger.exception("Lỗi lấy sitemap cho nguồn %s", source.domain)
            continue

        for candidate in candidates:
            url_hash = compute_url_hash(candidate["url"])
            if db.query(Article).filter_by(url_hash=url_hash).first() is not None:
                continue

            parsed = fetch_article(candidate["url"], source.parsing_rules)
            time.sleep(delay_seconds)
            if parsed is None:
                continue

            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=parsed["url"],
                    url_hash=parsed["url_hash"],
                    title=parsed["title"],
                    content_raw=parsed["content_raw"],
                    author=parsed["author"],
                    published_at=parsed["published_at"],
                )
            )
            db.commit()


def _analyze_articles(db, job: Job) -> None:
    pending = db.query(Article).filter_by(job_id=job.job_id, status="pending_analysis").all()
    for article in pending:
        try:
            result = analyze_article(article.title, article.content_raw)
        except ValueError:
            logger.exception("AI phân tích lỗi cho bài %s", article.url)
            article.status = "error"
            db.commit()
            continue

        db.add(
            ArticleAnalysis(
                article_id=article.article_id,
                job_id=job.job_id,
                topics=result["topics"],
                keywords=result.get("keywords", []),
                sentiment=result["sentiment"],
                emotion=result["emotion"],
                confidence=result["confidence"],
                needs_review=result["needs_review"],
                summary=result.get("summary"),
                prompt_version=result["prompt_version"],
            )
        )
        article.status = "analyzed"
        db.commit()


def _generate_report(db, job: Job) -> None:
    aggregates = aggregate_basic(db, job.job_id)
    storage_path = os.environ.get("STORAGE_PATH", "./storage")
    os.makedirs(storage_path, exist_ok=True)
    output_docx = os.path.join(storage_path, f"{job.job_id}.docx")
    output_json = os.path.join(storage_path, f"{job.job_id}.json")

    generate_docx(job, aggregates, output_docx)
    export_json(job, aggregates, output_json)

    job.output_docx = output_docx
    job.output_json = output_json
    db.add(ReportHistory(job_id=job.job_id, file_path=output_docx))
    db.commit()


@celery_app.task(name="workers.run_report_job")
def run_report_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        job.status = "running"
        db.commit()

        _crawl_sources(db, job)
        _analyze_articles(db, job)
        _generate_report(db, job)

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        logger.exception("Job %s thất bại", job_id)
        db.rollback()
        job = db.get(Job, job_id)
        job.status = "failed"
        job.error_log = str(exc)
        db.commit()
    finally:
        db.close()
