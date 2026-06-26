import uuid
from datetime import date
from unittest.mock import patch

from backend.models import Article, Job, Source
from backend.workers.report_job import _crawl_sources


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

    with patch("backend.workers.report_job.get_article_urls", return_value=candidates), patch(
        "backend.workers.report_job.fetch_article", side_effect=fake_fetch_article
    ), patch("backend.workers.report_job.time.sleep"):
        _crawl_sources(db_session, job)

    count = db_session.query(Article).filter_by(job_id=job.job_id).count()
    assert count == 2

    db_session.query(Article).filter_by(job_id=job.job_id).delete()
    db_session.delete(job)
    db_session.delete(source)
    db_session.commit()
