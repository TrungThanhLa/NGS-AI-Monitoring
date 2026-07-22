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
