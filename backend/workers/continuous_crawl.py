import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from backend.crawler.article import compute_url_hash
from backend.crawler.crawl4ai_client import fetch_article_dispatch
from backend.crawler.listing import get_listing_urls
from backend.crawler.sitemap import get_article_urls
from backend.models import (
    Article,
    Campaign,
    CampaignArticle,
    CampaignArticleKeyword,
    CampaignKeyword,
    CampaignSource,
    CrawlQueue,
    Keyword,
    Source,
)

logger = logging.getLogger(__name__)

# [SỬA 2026-07-23] Trước đây Discover luôn dùng cửa sổ trượt 30 ngày cố định tính từ
# `today`, không quan tâm start_date của Campaign nào — bài đăng trước cửa sổ này
# không bao giờ được match (match_campaigns_for_article chỉ chạy trên bài MỚI fetch,
# không hồi tố). Giờ Discover tính động: hợp (union) start_date của mọi Campaign
# CONTINUOUS ACTIVE đang theo dõi Nguồn này (xem _compute_required_floor), cap tối đa
# _MAX_CONTINUOUS_BACKFILL_DAYS ngày (lưới an toàn thứ 2, dù đã chặn cứng lúc tạo/kích
# hoạt Campaign — xem routers/campaigns.py _validate_continuous_start_date). Khi không
# cần backfill (đã quét đủ xa từ trước, xem sources.discover_backfilled_from), dùng
# cửa sổ hẹp _INCREMENTAL_LOOKBACK_DAYS ngày — giữ tinh thần "tự phục hồi nếu Beat gián
# đoạn vài ngày" của cửa sổ 30 ngày gốc (Phase 3), chỉ thu hẹp vì phần "phủ xa theo
# Campaign" đã tách thành cơ chế backfill riêng.
_INCREMENTAL_LOOKBACK_DAYS = 5
_MAX_CONTINUOUS_BACKFILL_DAYS = 180


def _compute_required_floor(db, source: Source, today: date) -> date:
    """MIN(start_date) trong số Campaign CONTINUOUS đang ACTIVE theo dõi Nguồn này, cap
    tối đa _MAX_CONTINUOUS_BACKFILL_DAYS ngày trước `today`. Nếu không có Campaign nào
    (trường hợp hiếm — crawl_task chỉ được dispatch cho Nguồn đã qua list_due_sources,
    tức đã có ít nhất 1 Campaign ACTIVE), trả về cửa sổ incremental mặc định."""
    earliest_start = (
        db.query(func.min(Campaign.start_date))
        .join(CampaignSource, CampaignSource.campaign_id == Campaign.campaign_id)
        .filter(
            CampaignSource.source_id == source.source_id,
            Campaign.status == "ACTIVE",
            Campaign.mode == "CONTINUOUS",
        )
        .scalar()
    )
    if earliest_start is None:
        return today - timedelta(days=_INCREMENTAL_LOOKBACK_DAYS)
    earliest_start_date = earliest_start.date() if isinstance(earliest_start, datetime) else earliest_start
    floor_cap = today - timedelta(days=_MAX_CONTINUOUS_BACKFILL_DAYS)
    return max(earliest_start_date, floor_cap)


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


def discover_source_urls(db, source: Source, today: date | None = None) -> int:
    """Giai đoạn 1 (Discover): tìm URL ứng viên của nguồn (dùng _get_candidates ở trên
    — không đổi logic ưu tiên sitemap/listing), ghi vào crawl_queue. Trả về số URL MỚI
    vừa ghi (không tính URL đã có từ chu kỳ trước — ON CONFLICT DO NOTHING không ghi
    đè trạng thái cũ).

    [SỬA 2026-07-23] date_from giờ tính động theo _compute_required_floor thay vì cố
    định _DISCOVER_LOOKBACK_DAYS — xem comment ở _compute_required_floor. Cập nhật
    sources.discover_backfilled_from bằng UPDATE nguyên tử LEAST() SAU MỌI LƯỢT chạy
    (kể cả khi 0 candidate) — vì "đã Discover xong tới date_from" là sự thật bất kể có
    tìm thấy URL mới hay không; bỏ qua bước này sẽ khiến lượt sau lặp lại đúng backfill
    tốn kém vừa chạy. UPDATE nguyên tử (không đọc-rồi-ghi qua ORM) để 2 crawl_task cùng
    Nguồn chạy chồng lấn (race đã biết, từng gây bug thật ở fetch_pending_urls) không
    ghi đè nhầm lẫn lên nhau — LEAST() luôn giữ giá trị nhỏ nhất (xa nhất về quá khứ)
    dù 2 UPDATE chạy theo thứ tự nào."""
    today = today or date.today()
    backfilled_from = source.discover_backfilled_from
    backfilled_from_date = backfilled_from.date() if isinstance(backfilled_from, datetime) and backfilled_from else backfilled_from

    required_floor = _compute_required_floor(db, source, today)
    if backfilled_from_date is None or required_floor < backfilled_from_date:
        date_from = required_floor
    else:
        date_from = today - timedelta(days=_INCREMENTAL_LOOKBACK_DAYS)

    candidates, _failed_locs = _get_candidates(source, date_from, today)

    inserted = 0
    if candidates:
        rows = [
            {
                "source_id": source.source_id,
                "url": c["url"],
                "url_hash": compute_url_hash(c["url"]),
                "status": "pending",
            }
            for c in candidates
        ]
        stmt = pg_insert(CrawlQueue).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["source_id", "url_hash"])
        result = db.execute(stmt)
        inserted = result.rowcount

    db.execute(
        text(
            "UPDATE sources "
            "SET discover_backfilled_from = LEAST(COALESCE(discover_backfilled_from, :date_from), :date_from) "
            "WHERE source_id = :source_id"
        ),
        {"date_from": date_from, "source_id": source.source_id},
    )
    db.commit()
    return inserted


_CONSECUTIVE_ERROR_LIMIT = 10  # BR-SRC-03 — ngưỡng khởi điểm, chưa dựa trên dữ liệu vận hành thật


def fetch_pending_urls(db, source: Source) -> list[Article]:
    """Giai đoạn 2 (Fetch): tải nội dung mọi URL đang 'pending' của nguồn (gồm cả URL
    lỡ chu kỳ trước — đây là cơ chế tự phục hồi khi worker bị đứt giữa chừng). Trả về
    danh sách Article vừa fetch THÀNH CÔNG trong lượt này."""
    delay_seconds = float(os.environ.get("CRAWLER_DELAY_SECONDS", "1.5"))
    max_retries = int(os.environ.get("CRAWLER_MAX_RETRIES", "3"))

    pending_rows = db.query(CrawlQueue).filter_by(source_id=source.source_id, status="pending").all()

    fetched_articles: list[Article] = []
    handled_count = 0  # bài fetch THÀNH CÔNG trong lượt này — gồm cả bài bị IntegrityError
    # (tiến trình khác đã lưu trước, xem nhánh dưới) — khác fetched_articles (chỉ bài MỚI,
    # dùng cho matching/AI ở crawl_task). Dùng cho quyết định BR-SRC-03 ở cuối hàm: 1 chu kỳ
    # toàn bài bị IntegrityError (do race, không phải do site lỗi) vẫn là chu kỳ THÀNH CÔNG
    # về mặt fetch — không được tính vào consecutive_error_count, nếu không nguồn khỏe mạnh
    # nhưng bị race trùng lặp nhiều lần sẽ bị oan chuyển ERROR.
    for row in pending_rows:
        try:
            parsed = fetch_article_dispatch(row.url, source.parsing_rules)
        except Exception:
            parsed = None
        time.sleep(delay_seconds)

        if parsed is None:
            row.retry_count += 1
            if row.retry_count > max_retries:
                row.status = "error"
            db.commit()
            continue

        article = Article(
            source_id=source.source_id,
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
            # [SỬA 2026-07-24] check_due_sources giờ đã "claim" nguyên tử (crawl_started_at)
            # trước khi dispatch nên Beat không còn tự chồng 2 crawl_task cho cùng source_id
            # nữa (xem scheduler.py check_due_sources) — nhưng vẫn CẦN giữ nguyên nhánh này
            # làm lưới an toàn cho 2 trường hợp khác: (1) gọi crawl_task trực tiếp/thủ công,
            # không qua check_due_sources nên không đi qua bước claim; (2) race với Campaign
            # ONE_SHOT — campaign_tasks.crawl_campaign_source_once (chord riêng, không qua
            # check_due_sources/claim) có thể fetch trùng URL với continuous_crawl.crawl_task
            # đang chạy song song cho cùng Source. Cả 2 trường hợp đều khiến 2 tiến trình cùng
            # fetch trùng 1 URL và cùng insert — partial unique index (source_id, url_hash)
            # chặn đúng, nhưng phải rollback + bỏ qua thay vì để crash cả crawl_task (mất luôn
            # tiến độ các URL còn lại trong batch). Không phải lỗi dữ liệu — bài đã được tiến
            # trình kia lưu thành công, coi như hàng này xong việc.
            db.rollback()
            row.status = "fetched"
            row.fetched_at = datetime.now(timezone.utc)
            db.commit()
            handled_count += 1
            continue
        row.status = "fetched"
        row.fetched_at = datetime.now(timezone.utc)
        db.commit()
        fetched_articles.append(article)
        handled_count += 1

    source.last_crawled_at = datetime.now(timezone.utc)
    # Chỉ tính là "chu kỳ lỗi" khi THỰC SỰ có URL để thử mà không fetch được bài nào —
    # nguồn không có bài mới trong 1 chu kỳ (pending_rows rỗng, VD nguồn đăng bài thưa)
    # KHÔNG được tính là lỗi, nếu không nguồn khỏe mạnh nhưng ít đăng bài sẽ bị tự
    # chuyển ERROR oan sau vài chu kỳ yên ắng. Dùng handled_count (không phải
    # fetched_articles) — 1 chu kỳ toàn bài bị IntegrityError (race, không phải site
    # lỗi thật) vẫn phải reset về 0, không được tính là lỗi.
    if pending_rows:
        if handled_count:
            source.consecutive_error_count = 0
        else:
            source.consecutive_error_count += 1
            if source.consecutive_error_count > _CONSECUTIVE_ERROR_LIMIT:
                source.status = "ERROR"
    db.commit()

    return fetched_articles


def match_campaigns_for_article(db, article: Article) -> None:
    """Hậu-crawl (rule 17): với mỗi Campaign ACTIVE đang theo dõi source_id của bài này,
    so khớp TOÀN BỘ từ khóa của Campaign đó (không dừng sớm khi trúng 1 từ) — mọi từ
    khóa trúng đều được ghi vào campaign_article_keywords để FE hiện đủ (Phase 4).
    campaign_articles.matched_keyword_id chỉ lưu keyword_id NHỎ NHẤT trong số trúng —
    dùng làm giá trị tham khảo/hiển thị rút gọn, vì campaign_keywords không có cột thứ
    tự khai báo nên không có khái niệm "từ khóa đầu tiên" thật sự, phải chọn 1 tiêu chí
    sắp xếp xác định (deterministic)."""
    haystack = f"{article.title or ''} {article.content_raw or ''}".lower()

    campaign_ids = (
        db.query(CampaignSource.campaign_id)
        .join(Campaign, Campaign.campaign_id == CampaignSource.campaign_id)
        .filter(CampaignSource.source_id == article.source_id, Campaign.status == "ACTIVE")
        .all()
    )

    for (campaign_id,) in campaign_ids:
        keywords = (
            db.query(Keyword)
            .join(CampaignKeyword, CampaignKeyword.keyword_id == Keyword.keyword_id)
            .filter(CampaignKeyword.campaign_id == campaign_id)
            .order_by(Keyword.keyword_id)
            .all()
        )
        matched = [k for k in keywords if k.keyword.lower() in haystack]
        if not matched:
            continue

        already_matched = (
            db.query(CampaignArticle)
            .filter_by(campaign_id=campaign_id, article_id=article.article_id)
            .first()
        )
        if already_matched is not None:
            continue

        db.add(
            CampaignArticle(
                campaign_id=campaign_id, article_id=article.article_id, matched_keyword_id=matched[0].keyword_id
            )
        )
        # Flush riêng CampaignArticle trước — FK composite của campaign_article_keywords
        # trỏ tới (campaign_id, article_id) của campaign_articles, SQLAlchemy không tự
        # suy ra được thứ tự insert giữa 2 bảng từ ForeignKeyConstraint composite này
        # (không có relationship() khai báo), nên phải flush tay để tránh
        # ForeignKeyViolation khi insert campaign_article_keywords ngay sau đó.
        db.flush()
        for k in matched:
            db.add(CampaignArticleKeyword(campaign_id=campaign_id, article_id=article.article_id, keyword_id=k.keyword_id))
        db.commit()


import asyncio

import httpx

from backend.ai.ollama_client import analyze_article
from backend.models import ArticleAnalysis
from backend.system_settings import get_bool_setting


def _has_continuous_campaign_match(db, article: Article) -> bool:
    """Kiểm tra bài này đã match (campaign_articles) với ít nhất 1 Campaign đang
    ACTIVE VÀ mode=CONTINUOUS — Campaign ONE_SHOT không tính (Phase 7, BR-CAMP-07)."""
    return (
        db.query(CampaignArticle)
        .join(Campaign, Campaign.campaign_id == CampaignArticle.campaign_id)
        .filter(
            CampaignArticle.article_id == article.article_id,
            Campaign.status == "ACTIVE",
            Campaign.mode == "CONTINUOUS",
        )
        .first()
        is not None
    )


def maybe_analyze_article(db, article: Article) -> None:
    """Nếu AI_AUTO_TRIGGER=true VÀ bài này match ít nhất 1 Campaign CONTINUOUS đang
    ACTIVE, phân tích AI ngay (per-article, KHÔNG theo Campaign — kết quả AI là thuộc
    tính của nội dung, không đổi theo Campaign nào đang xem, xem lý do đầy đủ ở design
    spec Phase 3 mục "Vì sao AI phân tích theo bài"). AI_AUTO_TRIGGER KHÔNG áp dụng cho
    Campaign ONE_SHOT (Phase 7, BR-CAMP-07) — ONE_SHOT luôn phân tích thủ công qua
    generate_campaign_report (backend/workers/campaign_tasks.py) khi người dùng bấm
    "Tạo báo cáo", tránh AI chạy nền liên tục không kiểm soát khi có nhiều Campaign
    ONE_SHOT chạy song song. Nếu không thỏa điều kiện nào, giữ nguyên
    articles.status='pending_analysis', không làm gì thêm."""
    if not get_bool_setting(db, "AI_AUTO_TRIGGER"):
        return
    if not _has_continuous_campaign_match(db, article):
        return

    try:
        result = asyncio.run(analyze_article(article.title or "", article.content_raw or ""))
    except (ValueError, httpx.HTTPError):
        article.status = "error"
        db.commit()
        return

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


import uuid

from backend.db import SessionLocal
from backend.workers.celery_app import celery_app


@celery_app.task(name="continuous_crawl.crawl_task")
def crawl_task(source_id: str) -> None:
    """Celery task nối toàn bộ pipeline crawl liên tục cho 1 Nguồn: Discover → Fetch →
    (per-article) Matching từ khóa Campaign → AI trigger (nếu AI_AUTO_TRIGGER=true).
    Mở/đóng SessionLocal() riêng cho task này (không dùng chung session với request FE)."""
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(source_id))
        if source is None:
            return
        # Cờ "đang quét" cho UI (Trạng thái: Đang quét/Đã quét) — ghi ngay khi bắt đầu,
        # xóa về NULL trong finally bên dưới (cả khi thành công lẫn lỗi) để không kẹt
        # mãi ở "Đang quét" nếu Discover/Fetch raise.
        source.crawl_started_at = datetime.now(timezone.utc)
        db.commit()
        try:
            discover_source_urls(db, source)
            fetched_articles = fetch_pending_urls(db, source)
            for article in fetched_articles:
                match_campaigns_for_article(db, article)
                maybe_analyze_article(db, article)
        except Exception:
            # KHÔNG được để lỗi 1 Source (VD Discover gọi sitemap/listing lỗi mạng, không có
            # try/except riêng như fetch_pending_urls đã có cho từng URL) raise ra ngoài task —
            # crawl_task là 1 phần tử trong Celery chord (mode=ONE_SHOT, xem
            # routers/campaigns.py::activate_campaign): nếu raise, Celery KHÔNG chạy callback
            # mark_crawl_done cho cả group, khiến Campaign kẹt mãi ở ACTIVE dù các Source khác
            # crawl thành công (xem thiết kế Phase 7 "Error Handling"). Log lại để vận hành biết
            # Source nào lỗi, nhưng để task tự coi là hoàn thành từ góc nhìn Celery.
            logger.exception("crawl_task thất bại cho source_id=%s", source_id)
        finally:
            source.crawl_started_at = None
            db.commit()
    finally:
        db.close()
