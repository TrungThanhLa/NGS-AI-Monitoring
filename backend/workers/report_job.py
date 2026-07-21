import asyncio
import logging
import os
import time
from datetime import datetime

import httpx

from backend.ai.ollama_client import analyze_articles_batch
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


def _distribute_evenly(total: int, n: int) -> list[int]:
    # Chia total thành n phần gần bằng nhau nhất, số dư dồn cho các phần tử ĐẦU tiên theo
    # thứ tự — khớp thứ tự source_ids user đã chọn ở FE. VD total=5, n=3 → [2, 2, 1].
    base, remainder = divmod(total, n)
    return [base + 1 if i < remainder else base for i in range(n)]


def _distribute_with_caps(total: int, caps: list[int]) -> list[int]:
    # Water-filling NHIỀU VÒNG, biết trước cap thật (số candidate thật) của MỌI nguồn.
    # Mỗi vòng chia đều ngân sách còn lại cho các nguồn chưa "khóa"; nguồn nào có cap thấp
    # hơn phần chia đều thì khóa quota đúng bằng cap của nó, ngân sách dư (quota - cap) dồn
    # tiếp cho các nguồn còn lại ở vòng sau — lặp đến khi hết ngân sách hoặc hết nguồn.
    # Khác thuật toán 1 vòng cũ (chỉ dồn ngân sách cho nguồn xử lý SAU trong lúc crawl): vì
    # biết cap thật của mọi nguồn ngay từ đầu, thuật toán này bù đúng cả khi nguồn thiếu
    # candidate nằm ở CUỐI danh sách (bug thật gặp 2026-07-13 — xem CLAUDE.md).
    n = len(caps)
    quotas = [0] * n
    remaining_indices = list(range(n))
    remaining_budget = total
    while remaining_indices and remaining_budget > 0:
        shares = _distribute_evenly(remaining_budget, len(remaining_indices))
        newly_capped = [idx for pos, idx in enumerate(remaining_indices) if shares[pos] > caps[idx]]
        if not newly_capped:
            for pos, idx in enumerate(remaining_indices):
                quotas[idx] = shares[pos]
            break
        for idx in newly_capped:
            quotas[idx] = caps[idx]
            remaining_budget -= caps[idx]
        remaining_indices = [idx for idx in remaining_indices if idx not in newly_capped]
    return quotas


def _crawl_sources(db, job: Job) -> None:
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_articles = _parse_max_articles(os.environ.get("MAX_ARTICLES_PER_JOB"))
    even_distribute = os.environ.get("EVEN_DISTRIBUTE_ACROSS_SOURCES", "false").lower() == "true"

    # Chỉ chống trùng URL TRONG PHẠM VI 1 lần chạy job này (không đụng DB) — một số nguồn
    # (VD sitemap index) có thể vô tình trả về cùng 1 URL 2 lần. KHÔNG chặn URL đã crawl ở
    # job khác: mỗi job crawl/phân tích độc lập, kể cả trùng URL với job trước (xem spec
    # docs/superpowers/specs/2026-07-09-remove-cross-job-dedup-design.md). UNIQUE composite
    # (job_id, url_hash) ở DB (migration 0009) là lưới an toàn dự phòng cho trường hợp check
    # này có bug bỏ sót — không phải cơ chế chính, không cần xử lý IntegrityError riêng ở đây.
    seen_urls: set[str] = set()

    def crawled_count() -> int:
        return db.query(Article).filter_by(job_id=job.job_id).count()

    def source_crawled_count(source_id) -> int:
        return db.query(Article).filter_by(job_id=job.job_id, source_id=source_id).count()

    sources = [db.get(Source, source_id) for source_id in job.source_ids]

    # Chỉ cần biết trước cap thật (số candidate thật) của MỌI nguồn khi bật water-filling
    # nhiều vòng (even_distribute + có max_articles) — xem _distribute_with_caps. Các trường
    # hợp khác giữ nguyên hành vi fetch "lười" cũ (không fetch nguồn sau nếu nguồn trước đã
    # đủ quota) để không tốn request thừa khi tính năng bù quota không cần dùng tới.
    quota_by_source: dict = {}
    prefetched: dict = {}
    if even_distribute and max_articles is not None:
        caps = []
        for source in sources:
            try:
                candidates, failed_locs = _get_candidates(source, job.date_from, job.date_to)
            except Exception:
                logger.exception("Lỗi lấy danh sách bài viết cho nguồn %s", source.domain)
                candidates, failed_locs = [], []
            prefetched[source.source_id] = (candidates, failed_locs)
            caps.append(len(candidates))
        quotas = _distribute_with_caps(max_articles, caps)
        quota_by_source = {s.source_id: q for s, q in zip(sources, quotas)}

    for source in sources:
        if max_articles is not None and crawled_count() >= max_articles:
            break

        quota_for_source: int | None = quota_by_source.get(source.source_id) if quota_by_source else None

        if source.source_id in prefetched:
            candidates, failed_locs = prefetched[source.source_id]
        else:
            try:
                candidates, failed_locs = _get_candidates(source, job.date_from, job.date_to)
            except Exception:
                logger.exception("Lỗi lấy danh sách bài viết cho nguồn %s", source.domain)
                continue

        for loc in failed_locs:
            db.add(
                Article(
                    job_id=job.job_id,
                    source_id=source.source_id,
                    url=loc,
                    url_hash=compute_url_hash(loc),
                    status="error",
                )
            )
            db.commit()

        for candidate in candidates:
            if max_articles is not None and crawled_count() >= max_articles:
                break
            if quota_for_source is not None and source_crawled_count(source.source_id) >= quota_for_source:
                break

            if candidate["url"] in seen_urls:
                continue
            seen_urls.add(candidate["url"])
            url_hash = compute_url_hash(candidate["url"])

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
    if not pending:
        return

    # AI_CONCURRENCY: số bài AI xử lý đồng thời trong job này — mặc định 1, cho ra đúng
    # hành vi tuần tự cũ (an toàn cho CPU-only). Chỉ tăng khi chạy trên hạ tầng có GPU
    # (xem CLAUDE.md — checklist chuyển sang server).
    concurrency = int(os.environ.get("AI_CONCURRENCY", "1"))
    results = asyncio.run(
        analyze_articles_batch([(a.title, a.content_raw) for a in pending], concurrency=concurrency)
    )

    for article, result in zip(pending, results):
        if isinstance(result, (ValueError, httpx.HTTPError)):
            logger.error("AI phân tích lỗi cho bài %s", article.url, exc_info=result)
            article.status = "error"
            db.commit()
            continue
        if isinstance(result, Exception):
            # Lỗi không thuộc loại đã biết (JSON không hợp lệ / lỗi HTTP) — không nuốt âm
            # thầm, để job fail rõ ràng thay vì báo completed sai (xem 10-error-handling.md)
            raise result

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
                ai_model=result["ai_model"],
                analysis_duration_seconds=result.get("analysis_duration_seconds"),
            )
        )
        article.status = "analyzed"
        db.commit()


def _generate_report(db, job: Job) -> None:
    article_ids = [row[0] for row in db.query(Article.article_id).filter_by(job_id=job.job_id).all()]
    aggregates = aggregate_basic(db, article_ids)
    storage_path = os.environ.get("STORAGE_PATH", "./storage")
    os.makedirs(storage_path, exist_ok=True)
    output_docx = os.path.join(storage_path, f"{job.job_id}.docx")
    output_json = os.path.join(storage_path, f"{job.job_id}.json")

    generate_docx(job.date_from, job.date_to, aggregates, output_docx)
    export_json(str(job.job_id), job.date_from, job.date_to, aggregates, output_json)

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
