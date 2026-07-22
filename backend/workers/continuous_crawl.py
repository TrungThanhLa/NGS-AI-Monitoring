import os
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from backend.crawler.article import compute_url_hash
from backend.crawler.crawl4ai_client import fetch_article_dispatch
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

# Discover không giới hạn CỨNG theo date_from/date_to như Job on-demand — nhưng KHÔNG
# quét từ "vô hạn trong quá khứ" (đã thử date(2000,1,1) và phát hiện bug thật: với
# nguồn dùng _SITEMAP_URL_TEMPLATES sinh 1 URL sub-sitemap/tháng — VD vtv.vn — quét từ
# năm 2000 tạo ra ~300+ request HTTP mỗi chu kỳ, vi phạm nguyên tắc "không spam
# request" và có nguy cơ bị chặn IP — xem CLAUDE.md, phát hiện lúc smoke test thật
# 2026-07-21). Dùng cửa sổ trượt (rolling window) N ngày gần nhất tính từ `today` —
# đủ rộng để không bỏ lỡ bài nếu 1 chu kỳ bị gián đoạn vài ngày liên tiếp, chống
# trùng đã có crawl_queue lo (ON CONFLICT DO NOTHING).
_DISCOVER_LOOKBACK_DAYS = 30


def _get_candidates(source, date_from, date_to):
    # Import trì hoãn tới lúc gọi (không import ở đầu file) — report_job.py import
    # ngược lại celery_app (đăng ký cả continuous_crawl module này), nên nếu
    # report_job.py là entrypoint đầu tiên của tiến trình (VD `pytest
    # tests/test_report_job.py` chạy riêng lẻ), import ở top-level module sẽ tạo
    # vòng lặp: report_job → celery_app → continuous_crawl → report_job (lúc này
    # report_job vẫn đang khởi tạo dở, chưa định nghĩa xong _get_candidates thật).
    # Trì hoãn import xuống đây phá vòng lặp, đồng thời vẫn giữ được tên
    # continuous_crawl._get_candidates để test monkeypatch như cũ.
    from backend.workers.report_job import _get_candidates as _impl

    return _impl(source, date_from, date_to)


def discover_source_urls(db, source: Source, today: date | None = None) -> int:
    """Giai đoạn 1 (Discover): tìm URL ứng viên của nguồn (tái dùng nguyên xi
    _get_candidates của report_job.py — không đổi logic ưu tiên sitemap/listing),
    ghi vào crawl_queue. Trả về số URL MỚI vừa ghi (không tính URL đã có từ chu kỳ
    trước — ON CONFLICT DO NOTHING không ghi đè trạng thái cũ)."""
    today = today or date.today()
    date_from = today - timedelta(days=_DISCOVER_LOOKBACK_DAYS)
    candidates, _failed_locs = _get_candidates(source, date_from, today)

    if not candidates:
        return 0

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
    db.commit()
    return result.rowcount


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
            job_id=None,
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
            # Có thể xảy ra khi 1 chu kỳ Fetch chưa xử lý hết hàng đợi trước khi
            # crawl_frequency trôi qua lần nữa (VD nguồn có backlog lớn hơn dự kiến
            # lúc mới bật continuous crawl) — Beat enqueue thêm crawl_task cho CÙNG
            # source_id trong khi task cũ vẫn đang chạy, 2 tiến trình cùng fetch
            # trùng 1 URL và cùng insert — partial unique index (source_id, url_hash)
            # chặn đúng, nhưng phải rollback + bỏ qua thay vì để crash cả crawl_task
            # (mất luôn tiến độ các URL còn lại trong batch). Không phải lỗi dữ liệu —
            # bài đã được tiến trình kia lưu thành công, coi như hàng này xong việc.
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
            job_id=None,
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
        discover_source_urls(db, source)
        fetched_articles = fetch_pending_urls(db, source)
        for article in fetched_articles:
            match_campaigns_for_article(db, article)
            maybe_analyze_article(db, article)
    finally:
        db.close()
