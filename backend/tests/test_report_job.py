import uuid
from datetime import date
from unittest.mock import patch

import httpx

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

    def fake_fetch_article(url, parsing_rules, **kwargs):
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
        with patch("backend.workers.report_job.get_article_urls", return_value=candidates), patch(
            "backend.workers.report_job.fetch_article", side_effect=fake_fetch_article
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
        with patch("backend.workers.report_job.get_article_urls", return_value=candidates), patch(
            "backend.workers.report_job.fetch_article", return_value=None
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
        with patch("backend.workers.report_job.analyze_article", side_effect=httpx.ReadTimeout("timed out")):
            _analyze_articles(db_session, job)

        db_session.refresh(article)
        assert article.status == "error"
        assert db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).count() == 0
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.delete(source)
        db_session.commit()
