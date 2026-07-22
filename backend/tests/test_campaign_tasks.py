import json
import uuid
from datetime import date, datetime
from unittest.mock import patch

from backend.models import Article, Campaign, CampaignArticle, ReportHistory, Source
from backend.workers.campaign_tasks import _generate_campaign_report, resolve_campaign_article_ids


def _make_campaign(db_session):
    c = Campaign(name=f"C-{uuid.uuid4()}", start_date="2026-06-01", status="ACTIVE")
    db_session.add(c)
    db_session.flush()
    return c


def _make_source(db_session):
    s = Source(name="S", domain=f"s-{uuid.uuid4()}.example", group_name="G")
    db_session.add(s)
    db_session.flush()
    return s


def test_resolve_campaign_article_ids_filters_by_published_at_range(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    in_range = Article(
        source_id=source.source_id, url="https://x.vn/a1", url_hash=f"h-{uuid.uuid4()}",
        published_at=datetime(2026, 6, 15), status="analyzed",
    )
    out_of_range = Article(
        source_id=source.source_id, url="https://x.vn/a2", url_hash=f"h-{uuid.uuid4()}",
        published_at=datetime(2026, 7, 15), status="analyzed",
    )
    db_session.add_all([in_range, out_of_range])
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=in_range.article_id))
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=out_of_range.article_id))
    db_session.commit()

    result = resolve_campaign_article_ids(db_session, campaign.campaign_id, date(2026, 6, 1), date(2026, 6, 30))

    assert result == [in_range.article_id]


def test_resolve_campaign_article_ids_includes_articles_late_on_end_date(db_session):
    # Regression: published_at là TIMESTAMP, date_to là date thuần — Postgres cast date_to
    # thành 00:00:00 khi so sánh "<=". Bài đăng cuối ngày date_to (VD 23:00) trước đây bị
    # loại oan khỏi báo cáo dù rõ ràng thuộc phạm vi date_from..date_to.
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    late_on_end_date = Article(
        source_id=source.source_id, url="https://x.vn/a1", url_hash=f"h-{uuid.uuid4()}",
        published_at=datetime(2026, 6, 30, 23, 0, 0), status="analyzed",
    )
    db_session.add(late_on_end_date)
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=late_on_end_date.article_id))
    db_session.commit()

    result = resolve_campaign_article_ids(db_session, campaign.campaign_id, date(2026, 6, 1), date(2026, 6, 30))

    assert result == [late_on_end_date.article_id]


def test_resolve_campaign_article_ids_excludes_articles_from_other_campaigns(db_session):
    campaign_a = _make_campaign(db_session)
    campaign_b = _make_campaign(db_session)
    source = _make_source(db_session)
    article = Article(
        source_id=source.source_id, url="https://x.vn/a1", url_hash=f"h-{uuid.uuid4()}",
        published_at=datetime(2026, 6, 15), status="analyzed",
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign_b.campaign_id, article_id=article.article_id))
    db_session.commit()

    result = resolve_campaign_article_ids(db_session, campaign_a.campaign_id, date(2026, 6, 1), date(2026, 6, 30))

    assert result == []


def test_generate_campaign_report_analyzes_pending_and_writes_json(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    article = Article(
        source_id=source.source_id, url="https://x.vn/a1", url_hash=f"h-{uuid.uuid4()}",
        title="Bài test", content_raw="Nội dung test",
        published_at=datetime(2026, 6, 15), status="pending_analysis",
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=article.article_id))
    report = ReportHistory(campaign_id=campaign.campaign_id, file_path="", status="pending", format="json")
    db_session.add(report)
    db_session.commit()

    fake_result = {
        "topics": ["A"], "keywords": [], "sentiment": "neutral", "emotion": "Trust",
        "confidence": 0.9, "needs_review": False, "summary": "tóm tắt",
        "prompt_version": 1, "ai_model": "qwen3:8b", "analysis_duration_seconds": 1.0,
    }
    # unittest.mock.patch tự phát hiện analyze_article là hàm async và bọc bằng AsyncMock —
    # return_value ở đây là giá trị trả về SAU KHI await, không cần tự tạo coroutine
    # (khác với ví dụ ban đầu trong brief dùng _async_result() wrapper, gây double-await lỗi
    # "'coroutine' object is not subscriptable" khi chạy thật).
    #
    # Gọi thẳng _generate_campaign_report(db_session, ...) — hàm inner không tự mở/đóng
    # session (giống _generate_report(db, job) trong report_job.py) — không cần patch
    # SessionLocal, không cần cờ test-only nào.
    with patch("backend.workers.campaign_tasks.analyze_article", return_value=fake_result):
        _generate_campaign_report(
            db_session, str(report.report_id), str(campaign.campaign_id), "2026-06-01", "2026-06-30", "json"
        )

    db_session.refresh(report)
    assert report.status == "completed"
    with open(report.file_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["summary_stats"]["Tổng số bài"] == 1


def test_generate_campaign_report_marks_failed_on_exception(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    campaign = _make_campaign(db_session)
    report = ReportHistory(campaign_id=campaign.campaign_id, file_path="", status="pending", format="docx")
    db_session.add(report)
    db_session.commit()

    with patch(
        "backend.workers.campaign_tasks.resolve_campaign_article_ids",
        side_effect=RuntimeError("boom"),
    ):
        _generate_campaign_report(
            db_session, str(report.report_id), str(campaign.campaign_id), "2026-06-01", "2026-06-30", "docx"
        )

    db_session.refresh(report)
    assert report.status == "failed"
    assert "boom" in report.error_log


def test_mark_crawl_done_sets_campaign_completed(db_session):
    """Callback của chord — chạy SAU KHI toàn bộ crawl_task con hoàn thành.
    Chỉ đánh dấu COMPLETED — KHÔNG chạm AI/report."""
    from backend.workers.campaign_tasks import _mark_crawl_done

    campaign = _make_campaign(db_session)
    campaign.status = "ACTIVE"
    db_session.commit()

    _mark_crawl_done(db_session, str(campaign.campaign_id))

    db_session.refresh(campaign)
    assert campaign.status == "COMPLETED"


def test_mark_crawl_done_no_op_if_campaign_not_found(db_session):
    """If campaign không tồn tại, hàm chỉ return ngay — không raise exception."""
    from backend.workers.campaign_tasks import _mark_crawl_done

    nonexistent_id = str(uuid.uuid4())
    _mark_crawl_done(db_session, nonexistent_id)  # Should not raise


from backend.models import CampaignCrawlProgress


def test_campaign_crawl_progress_model_roundtrip(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    db_session.add(CampaignCrawlProgress(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    row = db_session.query(CampaignCrawlProgress).filter_by(campaign_id=campaign.campaign_id).one()
    assert row.source_id == source.source_id
    assert row.total_urls is None
    assert row.done_urls == 0
    assert row.status == "pending"


from backend.crawler.article import compute_url_hash
from backend.models import CampaignArticle, CampaignKeyword, CampaignSource, CrawlQueue, Keyword
from backend.workers.campaign_tasks import _crawl_campaign_source_once


def _make_campaign_with_source_and_keyword(db_session, keyword_text="lừa đảo"):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session)
    kw = Keyword(keyword=keyword_text)
    db_session.add(kw)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw.keyword_id))
    db_session.commit()
    return campaign, source


def test_crawl_campaign_source_once_fetches_new_candidates_and_tracks_progress(db_session, monkeypatch):
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([{"url": "https://x.example/bai-1"}], []),
    )
    monkeypatch.setattr(
        "backend.workers.campaign_tasks.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": "hash-bai-1", "title": "Cảnh báo lừa đảo", "content_raw": "Nội dung",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    article = db_session.query(Article).filter_by(source_id=source.source_id, url_hash="hash-bai-1").one()
    assert article.title == "Cảnh báo lừa đảo"
    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=article.article_id).one()
    assert ca is not None

    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.total_urls == 1
    assert progress.done_urls == 1
    assert progress.status == "done"


def test_crawl_campaign_source_once_reuses_existing_article_without_refetching(db_session, monkeypatch):
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    # url_hash phải khớp compute_url_hash(url) thật — production luôn ghi Article.url_hash
    # bằng compute_url_hash (xem _get_candidates → fetch_article_dispatch → compute_url_hash
    # trong crawler/article.py), lookup "tái sử dụng" trong _crawl_campaign_source_once
    # cũng tra bằng compute_url_hash(url), không phải chuỗi tùy ý.
    existing = Article(
        source_id=source.source_id, url="https://x.example/bai-cu",
        url_hash=compute_url_hash("https://x.example/bai-cu"),
        title="Cảnh báo lừa đảo cũ", content_raw="Nội dung cũ", status="analyzed",
    )
    db_session.add(existing)
    db_session.commit()

    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([{"url": "https://x.example/bai-cu"}], []),
    )

    def _fail_if_called(url, rules):
        raise AssertionError("Không được gọi fetch_article_dispatch cho URL đã có Article")

    monkeypatch.setattr("backend.workers.campaign_tasks.fetch_article_dispatch", _fail_if_called)

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=existing.article_id).one()
    assert ca is not None
    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.done_urls == 1
    assert progress.status == "done"


def test_crawl_campaign_source_once_handles_reactivation_without_duplicate_match(db_session, monkeypatch):
    # Kích hoạt lại Campaign (crawl lần 2 cho cùng URL đã match từ lần 1) không được vỡ
    # IntegrityError ở campaign_articles — dựa vào guard idempotent đã thêm ở Task 3
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([{"url": "https://x.example/bai-2"}], []),
    )
    # url_hash trả về phải khớp compute_url_hash(url) thật — như production
    # (fetch_article_dispatch tự tính url_hash) — để lượt crawl thứ 2 tìm lại đúng
    # Article đã lưu ở lượt 1 (nhánh tái sử dụng), thay vì tạo trùng/vỡ constraint.
    monkeypatch.setattr(
        "backend.workers.campaign_tasks.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": compute_url_hash(url), "title": "Lừa đảo", "content_raw": "Nội dung",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")
    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    article = db_session.query(Article).filter_by(
        source_id=source.source_id, url_hash=compute_url_hash("https://x.example/bai-2")
    ).one()
    rows = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=article.article_id).all()
    assert len(rows) == 1


def test_crawl_campaign_source_once_sets_error_status_on_discover_failure(db_session, monkeypatch):
    campaign, source = _make_campaign_with_source_and_keyword(db_session)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")

    def _raise(src, date_from, date_to):
        raise RuntimeError("lỗi mạng giả lập")

    monkeypatch.setattr("backend.workers.continuous_crawl._get_candidates", _raise)

    _crawl_campaign_source_once(db_session, str(campaign.campaign_id), str(source.source_id), "2026-06-01", "2026-06-05")

    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.status == "error"
