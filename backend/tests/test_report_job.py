import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from backend.crawler.article import compute_url_hash
from backend.models import Article, ArticleAnalysis, Job, Source
from backend.workers.report_job import _analyze_articles, _crawl_sources


def test_crawl_sources_stops_at_max_articles_per_job_limit(db_session, monkeypatch):
    monkeypatch.setenv("MAX_ARTICLES_PER_JOB", "2")

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": f"https://example.test/article-{i}", "lastmod": date(2026, 6, 1)} for i in range(5)]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": None,
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count = db_session.query(Article).filter_by(job_id=job.job_id).count()
        assert count == 2
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_inserts_error_row_when_fetch_article_returns_none(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/article-fail", "lastmod": date(2026, 6, 1)}]

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", return_value=None
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        articles = db_session.query(Article).filter_by(job_id=job.job_id).all()
        assert len(articles) == 1
        assert articles[0].status == "error"
        assert articles[0].url == "https://example.test/article-fail"
        assert articles[0].title is None
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_inserts_error_row_when_fetch_article_dispatch_raises(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [
        {"url": "https://example.test/article-raises", "lastmod": date(2026, 6, 1)},
        {"url": "https://example.test/article-ok", "lastmod": date(2026, 6, 1)},
    ]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        if url == "https://example.test/article-raises":
            raise ValueError("invalid isoformat string")
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": None,
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        articles = db_session.query(Article).filter_by(job_id=job.job_id).all()
        assert len(articles) == 2
        by_url = {a.url: a for a in articles}
        assert by_url["https://example.test/article-raises"].status == "error"
        assert by_url["https://example.test/article-ok"].status == "pending_analysis"
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_inserts_error_row_for_each_failed_sub_sitemap(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    failed_loc = "https://example.test/sitemaps/sitemaps-2026-6-1-15.xml"

    try:
        with patch(
            "backend.workers.report_job.get_article_urls", return_value=([], [failed_loc])
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        articles = db_session.query(Article).filter_by(job_id=job.job_id).all()
        assert len(articles) == 1
        assert articles[0].status == "error"
        assert articles[0].url == failed_loc
        assert articles[0].title is None
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_calls_fetch_article_dispatch_with_url_and_parsing_rules(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    parsing_rules = {"engine": "crawl4ai"}
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules=parsing_rules)
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/article-1", "lastmod": date(2026, 6, 1)}]
    captured = {}

    def fake_dispatch(url, rules, **kwargs):
        captured["called_with"] = (url, rules)
        return None

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        assert captured["called_with"] == ("https://example.test/article-1", parsing_rules)
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_marks_error_on_http_timeout_and_continues(db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/slow-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    try:
        with patch(
            "backend.workers.report_job.analyze_articles_batch",
            AsyncMock(return_value=[httpx.ReadTimeout("timed out")]),
        ):
            _analyze_articles(db_session, job)

        db_session.refresh(article)
        assert article.status == "error"
        assert db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).count() == 0
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_inserts_ai_model_from_result(db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/ok-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    fake_result = {
        "topics": ["Tin giả và thông tin sai lệch"],
        "keywords": ["deepfake"],
        "sentiment": "negative",
        "emotion": "Fear",
        "confidence": 0.85,
        "needs_review": False,
        "summary": "Tóm tắt.",
        "prompt_version": 1,
        "ai_model": "qwen3:8b",
        "analysis_duration_seconds": 1.23,
    }

    try:
        with patch(
            "backend.workers.report_job.analyze_articles_batch",
            AsyncMock(return_value=[fake_result]),
        ):
            _analyze_articles(db_session, job)

        db_session.refresh(article)
        assert article.status == "analyzed"
        analysis = db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).one()
        assert analysis.ai_model == "qwen3:8b"
    finally:
        db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).delete()
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_reraises_unexpected_exception_type(db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/bug-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    try:
        with patch(
            "backend.workers.report_job.analyze_articles_batch",
            AsyncMock(return_value=[RuntimeError("bug không lường trước")]),
        ), pytest.raises(RuntimeError):
            _analyze_articles(db_session, job)
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_passes_ai_concurrency_env_var_to_batch(db_session, monkeypatch):
    monkeypatch.setenv("AI_CONCURRENCY", "3")

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/concurrency-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    fake_batch = AsyncMock(return_value=[httpx.ReadTimeout("timed out")])

    try:
        with patch("backend.workers.report_job.analyze_articles_batch", fake_batch):
            _analyze_articles(db_session, job)

        assert fake_batch.call_args.kwargs["concurrency"] == 3
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_analyze_articles_defaults_ai_concurrency_to_1_when_env_unset(db_session, monkeypatch):
    monkeypatch.delenv("AI_CONCURRENCY", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        source_id=source.source_id,
        url="https://example.test/default-concurrency-article",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Title",
        content_raw="Content",
        status="pending_analysis",
    )
    db_session.add(article)
    db_session.commit()

    fake_batch = AsyncMock(return_value=[httpx.ReadTimeout("timed out")])

    try:
        with patch("backend.workers.report_job.analyze_articles_batch", fake_batch):
            _analyze_articles(db_session, job)

        assert fake_batch.call_args.kwargs["concurrency"] == 1
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_uses_listing_strategy_when_source_has_listing_url_and_no_sitemap(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(
        name="Test Listing",
        domain=f"test-listing-{uuid.uuid4()}.example",
        group_name="Test",
        listing_url="https://example.test/",
        parsing_rules={},
    )
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    try:
        with patch("backend.workers.report_job.get_listing_urls", return_value=([], [])) as mock_listing, patch(
            "backend.workers.report_job.get_article_urls"
        ) as mock_sitemap, patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        mock_listing.assert_called_once()
        mock_sitemap.assert_not_called()
    finally:
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_prefers_listing_pages_over_sitemap_when_both_configured(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(
        name="Test Multi Listing",
        domain=f"test-multi-listing-{uuid.uuid4()}.example",
        group_name="Test",
        sitemap_url="https://example.test/sitemap.xml",
        listing_url=None,
        parsing_rules={"listing_pages": ["https://example.test/chuyen-muc/a"]},
    )
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    try:
        with patch("backend.workers.report_job.get_listing_urls", return_value=([], [])) as mock_listing, patch(
            "backend.workers.report_job.get_article_urls"
        ) as mock_sitemap, patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        mock_listing.assert_called_once()
        mock_sitemap.assert_not_called()
    finally:
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_routes_sitemap_pages_source_through_get_article_urls(db_session, monkeypatch):
    # tingia.gov.vn: sitemap_url=NULL, listing_url=NULL, danh sách sub-sitemap curated nằm ở
    # parsing_rules.sitemap_pages — không nhánh listing nào (listing_url hay listing_pages)
    # khớp, nên phải rơi đúng vào get_article_urls() (không cần sửa _get_candidates()).
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(
        name="Test Sitemap Pages",
        domain=f"test-sitemap-pages-{uuid.uuid4()}.example",
        group_name="Test",
        sitemap_url=None,
        listing_url=None,
        parsing_rules={"sitemap_pages": ["https://example.test/sitemap/a.xml"]},
    )
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=([], [])) as mock_sitemap, patch(
            "backend.workers.report_job.get_listing_urls"
        ) as mock_listing, patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        mock_sitemap.assert_called_once()
        mock_listing.assert_not_called()
    finally:
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_skips_insert_when_published_at_outside_requested_range(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-ngoai-khoang", "lastmod": None}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": datetime(2025, 8, 20, 8, 2, 22),
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count = db_session.query(Article).filter_by(job_id=job.job_id).count()
        assert count == 0
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_inserts_when_published_at_inside_requested_range(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-trong-khoang", "lastmod": None}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": datetime(2026, 6, 15, 10, 0, 0),
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count = db_session.query(Article).filter_by(job_id=job.job_id).count()
        assert count == 1
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_falls_back_to_listing_lastmod_when_published_at_missing(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-viet/a", "lastmod": date(2026, 6, 15)}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": None,  # giống bocongan.gov.vn thật: thiếu meta article:published_time
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        article = db_session.query(Article).filter_by(job_id=job.job_id).one()
        assert article.published_at == datetime(2026, 6, 15, 0, 0)
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_prefers_parsed_published_at_over_listing_lastmod(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    candidates = [{"url": "https://example.test/bai-viet/a", "lastmod": date(2026, 6, 15)}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": f"hash-{url}",
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": datetime(2026, 6, 20, 8, 0),  # có giá trị thật từ chính bài viết
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        article = db_session.query(Article).filter_by(job_id=job.job_id).one()
        # published_at thật từ bài viết phải được ưu tiên hơn lastmod của trang danh sách
        assert article.published_at == datetime(2026, 6, 20, 8, 0)
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_recrawls_url_already_belonging_to_another_job(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job_a = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job_a)
    db_session.flush()

    shared_url = "https://example.test/bai-da-crawl-truoc"
    existing_article = Article(
        job_id=job_a.job_id,
        source_id=source.source_id,
        url=shared_url,
        url_hash=compute_url_hash(shared_url),
        title="Bài cũ",
        content_raw="Nội dung cũ",
        status="analyzed",
    )
    db_session.add(existing_article)
    db_session.commit()

    job_b = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job_b)
    db_session.flush()

    candidates = [{"url": shared_url, "lastmod": date(2026, 6, 1)}]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": compute_url_hash(url),
            "title": "Bài mới (đã crawl lại)",
            "content_raw": "Nội dung mới",
            "author": None,
            "published_at": None,
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job_b)

        job_b_articles = db_session.query(Article).filter_by(job_id=job_b.job_id).all()
        assert len(job_b_articles) == 1
        assert job_b_articles[0].url == shared_url
        assert job_b_articles[0].title == "Bài mới (đã crawl lại)"
    finally:
        db_session.query(Article).filter_by(job_id=job_b.job_id).delete()
        db_session.query(Article).filter_by(job_id=job_a.job_id).delete()
        db_session.delete(job_b)
        db_session.delete(job_a)
        db_session.delete(source)
        db_session.commit()


def test_crawl_sources_dedups_within_same_job_when_candidates_repeat_url(db_session, monkeypatch):
    monkeypatch.delenv("MAX_ARTICLES_PER_JOB", raising=False)

    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    repeated_url = "https://example.test/bai-lap-lai"
    candidates = [
        {"url": repeated_url, "lastmod": date(2026, 6, 1)},
        {"url": repeated_url, "lastmod": date(2026, 6, 1)},
    ]

    def fake_fetch_article_dispatch(url, parsing_rules, **kwargs):
        return {
            "url": url,
            "url_hash": compute_url_hash(url),
            "title": "Title",
            "content_raw": "Content",
            "author": None,
            "published_at": None,
            "crawl_duration_seconds": 0.01,
        }

    try:
        with patch("backend.workers.report_job.get_article_urls", return_value=(candidates, [])), patch(
            "backend.workers.report_job.fetch_article_dispatch", side_effect=fake_fetch_article_dispatch
        ), patch("backend.workers.report_job.time.sleep"):
            _crawl_sources(db_session, job)

        count = db_session.query(Article).filter_by(job_id=job.job_id).count()
        assert count == 1
    finally:
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()


def test_composite_unique_constraint_blocks_duplicate_within_same_job_at_db_level(db_session):
    """Lưới an toàn dự phòng ở tầng DB — kể cả khi seen_urls (Python) có bug bỏ sót,
    UNIQUE composite (job_id, url_hash) vẫn phải chặn insert trùng trong CÙNG 1 job."""
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test", parsing_rules={})
    db_session.add(source)
    db_session.flush()

    job = Job(source_ids=[source.source_id], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    db_session.add(job)
    db_session.flush()

    url = "https://example.test/bai-trung-trong-cung-job"
    db_session.add(
        Article(job_id=job.job_id, source_id=source.source_id, url=url, url_hash=compute_url_hash(url))
    )
    db_session.commit()

    try:
        with pytest.raises(IntegrityError):
            db_session.add(
                Article(job_id=job.job_id, source_id=source.source_id, url=url, url_hash=compute_url_hash(url))
            )
            db_session.commit()
    finally:
        db_session.rollback()
        db_session.query(Article).filter_by(job_id=job.job_id).delete()
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
