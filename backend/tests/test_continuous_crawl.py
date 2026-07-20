import uuid
from datetime import date

from backend.crawler.article import compute_url_hash
from backend.models import CrawlQueue, Source
from backend.workers.continuous_crawl import discover_source_urls


def test_discover_source_urls_inserts_new_pending_rows(db_session, monkeypatch):
    source = Source(name="X", domain=f"x-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()

    fake_candidates = [{"url": "https://x.example/a", "lastmod": date(2026, 1, 1)}]
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: (fake_candidates, []),
    )

    inserted = discover_source_urls(db_session, source)

    assert inserted == 1
    rows = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"


def test_discover_source_urls_skips_already_known_url(db_session, monkeypatch):
    source = Source(name="X2", domain=f"x2-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()
    existing_hash = compute_url_hash("https://x.example/a")
    db_session.add(
        CrawlQueue(source_id=source.source_id, url="https://x.example/a", url_hash=existing_hash, status="fetched")
    )
    db_session.commit()

    fake_candidates = [{"url": "https://x.example/a", "lastmod": date(2026, 1, 1)}]
    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: (fake_candidates, []),
    )

    inserted = discover_source_urls(db_session, source)

    assert inserted == 0
    rows = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).all()
    assert len(rows) == 1
    assert rows[0].status == "fetched"  # không bị ghi đè


def test_discover_source_urls_returns_zero_when_no_candidates(db_session, monkeypatch):
    source = Source(name="X3", domain=f"x3-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()

    monkeypatch.setattr(
        "backend.workers.continuous_crawl._get_candidates",
        lambda src, date_from, date_to: ([], []),
    )

    assert discover_source_urls(db_session, source) == 0
