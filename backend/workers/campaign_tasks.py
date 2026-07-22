import asyncio
import logging
import os
import time
import uuid
from datetime import date, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.ai.ollama_client import analyze_article
from backend.crawler.article import compute_url_hash
from backend.crawler.crawl4ai_client import fetch_article_dispatch
from backend.db import SessionLocal
from backend.models import (
    Article,
    ArticleAnalysis,
    Campaign,
    CampaignArticle,
    CampaignCrawlProgress,
    ReportHistory,
    Source,
)
from backend.report.aggregator import aggregate_basic
from backend.report.csv_generator import generate_csv
from backend.report.docx_generator import export_json, generate_docx
from backend.report.excel_generator import generate_excel
from backend.report.pdf_generator import generate_pdf
from backend.workers import continuous_crawl
from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_GENERATORS = {
    "docx": lambda date_from, date_to, aggregates, path: generate_docx(date_from, date_to, aggregates, path),
    "pdf": lambda date_from, date_to, aggregates, path: generate_pdf(date_from, date_to, aggregates, path),
    "xlsx": lambda date_from, date_to, aggregates, path: generate_excel(date_from, date_to, aggregates, path),
    "csv": lambda date_from, date_to, aggregates, path: generate_csv(date_from, date_to, aggregates, path),
}


def resolve_campaign_article_ids(db: Session, campaign_id, date_from: date, date_to: date) -> list[uuid.UUID]:
    """Chỉ lấy bài đã match từ khóa của Campaign này (qua campaign_articles — BR-CAMP-03
    áp dụng đồng nhất mọi mode, không đọc thẳng articles theo source_id), lọc theo
    published_at thật của bài (giữ đúng ý nghĩa date_from/date_to như luồng Job cũ), không
    phải matched_at (thời điểm hệ thống ghi nhận match).

    published_at là TIMESTAMP còn date_from/date_to là date thuần — Postgres cast date_to
    thành đúng 00:00:00 ngày đó khi so sánh, nên so sánh "<=date_to" sẽ bỏ sót gần như
    toàn bộ ngày cuối cùng (mọi bài đăng sau 00:00:00 hôm đó). Dùng "< date_to + 1 ngày"
    (đầu ngày kế tiếp) để bao trọn vẹn cả ngày date_to — giữ đúng hành vi full-day
    inclusive 2 đầu như luồng Job cũ (so sánh published_at.date() <= job.date_to)."""
    rows = (
        db.execute(
            select(Article.article_id)
            .join(CampaignArticle, CampaignArticle.article_id == Article.article_id)
            .where(
                CampaignArticle.campaign_id == campaign_id,
                Article.published_at.isnot(None),
                Article.published_at >= date_from,
                Article.published_at < date_to + timedelta(days=1),
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


def _analyze_pending_articles(db: Session, article_ids: list[uuid.UUID]) -> None:
    """Batch AI-analyze mọi bài còn pending_analysis trong phạm vi report — tuần tự
    (không dùng analyze_articles_batch có concurrency, vì đây là hành động thủ công 1
    lần/Campaign, không cần tối ưu như luồng Job cũ). Lỗi AI (timeout/JSON hỏng) → skip
    đúng 1 bài (status='error'), không chặn các bài còn lại (rule 10)."""
    pending = db.query(Article).filter(Article.article_id.in_(article_ids), Article.status == "pending_analysis").all()
    for article in pending:
        try:
            result = asyncio.run(analyze_article(article.title or "", article.content_raw or ""))
        except (ValueError, httpx.HTTPError):
            logger.exception("AI phân tích lỗi cho bài %s (report campaign)", article.url)
            article.status = "error"
            db.commit()
            continue

        db.add(
            ArticleAnalysis(
                article_id=article.article_id,
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


def _generate_campaign_report(db: Session, report_id: str, campaign_id: str, date_from: str, date_to: str, format: str) -> None:
    """Logic thật của generate_campaign_report — tách riêng khỏi việc mở/đóng session để
    test gọi thẳng với fixture db_session (giống _generate_report trong report_job.py),
    không cần patch SessionLocal."""
    try:
        report = db.get(ReportHistory, uuid.UUID(report_id))
        if report is None:
            return
        report.status = "running"
        db.commit()

        parsed_date_from = date.fromisoformat(date_from)
        parsed_date_to = date.fromisoformat(date_to)
        campaign_uuid = uuid.UUID(campaign_id)

        article_ids = resolve_campaign_article_ids(db, campaign_uuid, parsed_date_from, parsed_date_to)
        _analyze_pending_articles(db, article_ids)

        # Đọc lại article_ids SAU khi AI chạy xong — _analyze_pending_articles chỉ đổi
        # status của bài đã pending, không đổi tập article_ids đã resolve, nhưng
        # aggregate_basic cần bài đã có ArticleAnalysis (INNER JOIN) nên gọi lại
        # aggregate_basic với đúng article_ids ban đầu là đủ, không cần resolve lại.
        aggregates = aggregate_basic(db, article_ids)

        storage_path = os.environ.get("STORAGE_PATH", "./storage")
        os.makedirs(storage_path, exist_ok=True)
        extension = "json" if format == "json" else format
        output_path = os.path.join(storage_path, f"{report_id}.{extension}")

        if format == "json":
            export_json(report_id, parsed_date_from, parsed_date_to, aggregates, output_path)
        else:
            _GENERATORS[format](parsed_date_from, parsed_date_to, aggregates, output_path)

        report.file_path = output_path
        report.status = "completed"
        db.commit()
    except Exception as exc:
        logger.exception("generate_campaign_report thất bại cho report_id=%s", report_id)
        db.rollback()
        report = db.get(ReportHistory, uuid.UUID(report_id))
        if report is not None:
            report.status = "failed"
            report.error_log = str(exc)
            db.commit()


@celery_app.task(name="campaign_tasks.generate_campaign_report")
def generate_campaign_report(report_id: str, campaign_id: str, date_from: str, date_to: str, format: str) -> None:
    """report_id trỏ tới 1 dòng report_history đã tạo sẵn (status='pending') lúc
    POST /api/campaigns/{id}/reports — task này cập nhật status ngay trên dòng đó để FE
    polling theo report_id (GET /api/campaigns/{id}/reports/{report_id})."""
    db = SessionLocal()
    try:
        _generate_campaign_report(db, report_id, campaign_id, date_from, date_to, format)
    finally:
        db.close()


def _mark_crawl_done(db: Session, campaign_id: str) -> None:
    """Logic thật của mark_crawl_done — tách riêng khỏi việc mở/đóng session để
    test gọi thẳng với fixture db_session (không cần patch SessionLocal).
    Chỉ đánh dấu Campaign status = COMPLETED — KHÔNG chạm AI/report."""
    campaign = db.get(Campaign, uuid.UUID(campaign_id))
    if campaign is None:
        return
    campaign.status = "COMPLETED"
    db.commit()


@celery_app.task(name="campaign_tasks.mark_crawl_done")
def mark_crawl_done(results, campaign_id: str) -> None:
    """Callback của Celery chord — chạy SAU KHI toàn bộ crawl_task con (1 task/Source)
    trong group đã xong (kể cả khi 1 vài task con lỗi — crawl_task tự bắt lỗi nội bộ,
    không propagate exception ra ngoài group, xem Task 10).

    `results` là kết quả trả về của các task con trong chord, không dùng tới nhưng bắt buộc
    phải nhận theo đúng chữ ký callback của Celery chord.

    Chỉ đánh dấu COMPLETED — KHÔNG chạm AI/report (đó là hành động thủ công riêng,
    xem Task 7/8)."""
    db = SessionLocal()
    try:
        _mark_crawl_done(db, campaign_id)
    finally:
        db.close()


def _crawl_campaign_source_once(db: Session, campaign_id: str, source_id: str, date_from: str, date_to: str) -> None:
    """Logic thật của crawl_campaign_source_once — tách khỏi mở/đóng session để test gọi
    thẳng với fixture db_session. Đường crawl RIÊNG cho ONE_SHOT (khác continuous_crawl.
    crawl_task dùng cho CONTINUOUS): Discover đúng [date_from, date_to] của Campaign
    (không qua cửa sổ 30 ngày cố định), với mỗi URL — đã có Article thì tái sử dụng
    (không fetch lại), chưa có thì fetch mới. Không tự phục hồi nếu crash giữa chừng
    (khác CONTINUOUS) — kích hoạt lại Campaign là đủ, nhờ cơ chế tái sử dụng ở trên nên
    crawl lại rẻ. Bọc try/except toàn bộ để không phá chord (xem crawl_task."""
    try:
        campaign_uuid = uuid.UUID(campaign_id)
        source_uuid = uuid.UUID(source_id)

        progress = db.get(CampaignCrawlProgress, (campaign_uuid, source_uuid))
        if progress is None:
            progress = CampaignCrawlProgress(campaign_id=campaign_uuid, source_id=source_uuid)
            db.add(progress)

        source = db.get(Source, source_uuid)
        if source is None:
            progress.status = "error"
            db.commit()
            return

        progress.status = "discovering"
        progress.done_urls = 0
        db.commit()

        parsed_date_from = date.fromisoformat(date_from)
        parsed_date_to = date.fromisoformat(date_to)
        candidates, _failed = continuous_crawl._get_candidates(source, parsed_date_from, parsed_date_to)

        progress.total_urls = len(candidates)
        progress.status = "fetching"
        db.commit()

        delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))

        for candidate in candidates:
            url = candidate["url"]
            url_hash = compute_url_hash(url)
            article = db.query(Article).filter_by(source_id=source_uuid, url_hash=url_hash).first()

            if article is None:
                try:
                    parsed = fetch_article_dispatch(url, source.parsing_rules)
                except Exception:
                    parsed = None
                time.sleep(delay_seconds)

                if parsed is not None:
                    article = Article(
                        source_id=source_uuid,
                        url=parsed["url"],
                        url_hash=parsed["url_hash"],
                        title=parsed["title"],
                        content_raw=parsed["content_raw"],
                        author=parsed["author"],
                        published_at=parsed.get("published_at"),
                        crawl_duration_seconds=parsed.get("crawl_duration_seconds"),
                    )
                    db.add(article)
                    try:
                        db.commit()
                    except IntegrityError:
                        # Race hiếm: tiến trình khác (VD continuous_crawl.crawl_task cùng
                        # Source) đã insert đúng URL này trước — rollback, đọc lại bản đã có
                        db.rollback()
                        article = db.query(Article).filter_by(source_id=source_uuid, url_hash=url_hash).first()

            if article is not None:
                continuous_crawl.match_campaigns_for_article(db, article)

            progress.done_urls += 1
            db.commit()

        progress.status = "done"
        db.commit()
    except Exception:
        logger.exception(
            "crawl_campaign_source_once thất bại cho campaign_id=%s source_id=%s", campaign_id, source_id
        )
        try:
            db.rollback()
            if "progress" in locals() and progress is not None:
                progress.status = "error"
                db.commit()
        except Exception:
            logger.exception(
                "crawl_campaign_source_once: rollback/ghi trạng thái error cũng thất bại cho "
                "campaign_id=%s source_id=%s",
                campaign_id,
                source_id,
            )


@celery_app.task(name="campaign_tasks.crawl_campaign_source_once")
def crawl_campaign_source_once(campaign_id: str, source_id: str, date_from: str, date_to: str) -> None:
    """Thành viên của chord (mode=ONE_SHOT, xem routers/campaigns.py::activate_campaign) —
    1 task/Source. KHÔNG được raise ra ngoài (xử lý bên trong _crawl_campaign_source_once)
    — nếu raise, Celery không chạy callback mark_crawl_done, Campaign kẹt ACTIVE mãi."""
    db = SessionLocal()
    try:
        try:
            _crawl_campaign_source_once(db, campaign_id, source_id, date_from, date_to)
        except Exception:
            # Lớp phòng thủ thứ 2 — chỉ log, KHÔNG raise: nếu chính except block bên trong
            # _crawl_campaign_source_once cũng lỗi (VD DB connection đã chết thật), vẫn không
            # được để exception thoát ra khỏi task này, phá chord callback mark_crawl_done.
            logger.exception(
                "crawl_campaign_source_once: exception thoát khỏi _crawl_campaign_source_once "
                "cho campaign_id=%s source_id=%s",
                campaign_id,
                source_id,
            )
    finally:
        db.close()
