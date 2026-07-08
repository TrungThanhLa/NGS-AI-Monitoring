import logging
import os
import time
from datetime import datetime

import httpx

from backend.ai.ollama_client import analyze_article
from backend.crawler.article import compute_url_hash
from backend.crawler.crawl4ai_client import fetch_article_dispatch
from backend.crawler.listing import get_listing_urls
from backend.crawler.sitemap import get_article_urls
from backend.db import SessionLocal
from backend.models import Article, ArticleAnalysis, Job, ReportHistory, Source
from backend.report.aggregator import aggregate_basic
from backend.report.docx_generator import export_json, generate_docx
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _parse_max_articles(raw: str | None) -> int | None:
    # Để trống/không parse được/<= 0 → không giới hạn (None)
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _get_candidates(source, date_from, date_to) -> tuple[list[dict], list[str]]:
    # parsing_rules.listing_pages (nhiều trang chuyên mục, VD bocongan.gov.vn) luôn được ưu
    # tiên cao nhất — kể cả khi nguồn vẫn còn khai sitemap_url (sitemap không đáng tin/đóng
    # băng thì cấu hình listing_pages thay thế, không cần xoá sitemap_url khỏi DB).
    if source.parsing_rules.get("listing_pages"):
        return get_listing_urls(source, date_from, date_to)
    # Sitemap được ưu tiên khi nguồn có khai sitemap_url; chỉ dùng listing-page 1 trang khi
    # nguồn không có sitemap (VD tingia.gov.vn) — đúng thứ tự ưu tiên ở 06-crawler-strategy.md
    if source.listing_url and not source.sitemap_url:
        return get_listing_urls(source, date_from, date_to)
    return get_article_urls(source, date_from, date_to)


def _crawl_sources(db, job: Job) -> None:
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_articles = _parse_max_articles(os.environ.get("MAX_ARTICLES_PER_JOB"))

    def crawled_count() -> int:
        return db.query(Article).filter_by(job_id=job.job_id).count()

    for source_id in job.source_ids:
        if max_articles is not None and crawled_count() >= max_articles:
            break

        source = db.get(Source, source_id)
        try:
            candidates, failed_locs = _get_candidates(source, job.date_from, job.date_to)
        except Exception:
            logger.exception("Lỗi lấy danh sách bài viết cho nguồn %s", source.domain)
            continue

        for loc in failed_locs:
            # Hash theo job_id+url (không phải SHA256(url) như bài viết) vì url_hash UNIQUE
            # toàn cục — cùng 1 sub-sitemap/listing-page có thể lỗi lại ở job khác, nguồn khác
            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=loc,
                    url_hash=compute_url_hash(f"{job.job_id}:{loc}"),
                    status="error",
                )
            )
            db.commit()

        for candidate in candidates:
            if max_articles is not None and crawled_count() >= max_articles:
                break

            url_hash = compute_url_hash(candidate["url"])
            if db.query(Article).filter_by(url_hash=url_hash).first() is not None:
                continue

            try:
                parsed = fetch_article_dispatch(candidate["url"], source.parsing_rules)
            except Exception:
                logger.exception("Crawl lỗi (exception), đánh dấu error: %s", candidate["url"])
                parsed = None
            time.sleep(delay_seconds)
            if parsed is None:
                logger.warning("Crawl lỗi (hết retry hoặc không parse được), đánh dấu error: %s", candidate["url"])
                db.add(
                    Article(
                        job_id=job.job_id,
                        source_id=source.source_id,
                        url=candidate["url"],
                        url_hash=url_hash,
                        status="error",
                    )
                )
                db.commit()
                continue

            # Một số nguồn (VD bocongan.gov.vn) không có published_at từ chính trang bài viết
            # (thiếu meta article:published_time) — dùng lại ngày đã lấy từ trang danh sách
            # (candidate["lastmod"], đã lọc date_from/date_to ở bước lấy candidate) làm dự
            # phòng, ưu tiên published_at thật nếu có.
            candidate_lastmod = candidate.get("lastmod")
            published_at = parsed.get("published_at") or (
                datetime.combine(candidate_lastmod, datetime.min.time()) if candidate_lastmod else None
            )
            if published_at and not (job.date_from <= published_at.date() <= job.date_to):
                # Sitemap phẳng/listing-page không lọc được chính xác theo ngày trước khi fetch
                # (VD bocongan.gov.vn ghi <lastmod> giống nhau cho mọi URL, không phải ngày đăng
                # thật) — lọc lại ở đây bằng ngày đăng thật lấy từ chính bài viết. Không phải
                # lỗi nên không insert status=error, chỉ bỏ qua âm thầm.
                logger.info("Bỏ qua bài ngoài khoảng ngày yêu cầu (%s): %s", published_at.date(), candidate["url"])
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
                    published_at=published_at,
                    crawl_duration_seconds=parsed.get("crawl_duration_seconds"),
                )
            )
            db.commit()


def _analyze_articles(db, job: Job) -> None:
    pending = db.query(Article).filter_by(job_id=job.job_id, status="pending_analysis").all()
    for article in pending:
        try:
            result = analyze_article(article.title, article.content_raw)
        except (ValueError, httpx.HTTPError):
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
                analysis_duration_seconds=result.get("analysis_duration_seconds"),
                ai_model=os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
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
