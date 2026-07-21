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


from backend.models import Article
from backend.workers.continuous_crawl import fetch_pending_urls


def _make_source(db_session, name_prefix: str, **kwargs) -> Source:
    source = Source(
        name=name_prefix, domain=f"{name_prefix.lower()}-{uuid.uuid4()}.example", group_name="G",
        is_active=True, **kwargs,
    )
    db_session.add(source)
    db_session.commit()
    return source


def test_fetch_pending_urls_creates_article_and_resets_error_count(db_session, monkeypatch):
    source = _make_source(db_session, "Fetch1", consecutive_error_count=3)
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://f1.example/a", url_hash="h1", status="pending"))
    db_session.commit()

    monkeypatch.setattr(
        "backend.workers.continuous_crawl.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": "h1", "title": "Tiêu đề", "content_raw": "Nội dung",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")

    fetched = fetch_pending_urls(db_session, source)

    assert len(fetched) == 1
    assert fetched[0].job_id is None
    assert fetched[0].source_id == source.source_id
    row = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).one()
    assert row.status == "fetched"
    db_session.refresh(source)
    assert source.consecutive_error_count == 0
    assert source.last_crawled_at is not None


def test_fetch_pending_urls_increments_retry_then_marks_error(db_session, monkeypatch):
    source = _make_source(db_session, "Fetch2")
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://f2.example/a", url_hash="h2", status="pending", retry_count=3))
    db_session.commit()

    monkeypatch.setattr("backend.workers.continuous_crawl.fetch_article_dispatch", lambda url, rules: None)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setenv("CRAWLER_MAX_RETRIES", "3")

    fetched = fetch_pending_urls(db_session, source)

    assert fetched == []
    row = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).one()
    assert row.retry_count == 4
    assert row.status == "error"  # đã vượt CRAWLER_MAX_RETRIES=3


def test_fetch_pending_urls_leaves_error_count_untouched_when_nothing_pending(db_session):
    source = _make_source(db_session, "Fetch3", consecutive_error_count=5)

    fetched = fetch_pending_urls(db_session, source)

    assert fetched == []
    db_session.refresh(source)
    assert source.consecutive_error_count == 5  # không tăng, không reset — chu kỳ này đơn giản không có gì để fetch


def test_fetch_pending_urls_sets_status_error_after_11_consecutive_failed_cycles(db_session, monkeypatch):
    source = _make_source(db_session, "Fetch4", consecutive_error_count=10)
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://f4.example/a", url_hash="h4", status="pending"))
    db_session.commit()

    monkeypatch.setattr("backend.workers.continuous_crawl.fetch_article_dispatch", lambda url, rules: None)
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")
    monkeypatch.setenv("CRAWLER_MAX_RETRIES", "3")

    fetch_pending_urls(db_session, source)

    db_session.refresh(source)
    assert source.consecutive_error_count == 11
    assert source.status == "ERROR"


def test_fetch_pending_urls_skips_gracefully_on_concurrent_duplicate_insert(db_session, monkeypatch):
    # Tái hiện race điều kiện thật đã gặp lúc smoke test (2026-07-21): 2 crawl_task cho
    # CÙNG source_id chạy chồng lấn (crawl_frequency ngắn hơn thời gian 1 chu kỳ Fetch
    # hoàn tất, VD nguồn có backlog lớn) → cả 2 cùng fetch trùng 1 URL, tiến trình kia
    # "thắng" insert trước — partial unique index (source_id, url_hash) chặn tiến trình
    # này bằng IntegrityError. Phải rollback + đánh dấu crawl_queue 'fetched' + tiếp tục
    # xử lý các URL còn lại, KHÔNG crash cả task (mất tiến độ batch).
    source = _make_source(db_session, "Fetch5")
    same_url = "https://f5.example/already-fetched-elsewhere"
    same_hash = compute_url_hash(same_url)
    db_session.add(
        Article(job_id=None, source_id=source.source_id, url=same_url, url_hash=same_hash, title="Đã có rồi")
    )
    db_session.add(CrawlQueue(source_id=source.source_id, url=same_url, url_hash=same_hash, status="pending"))
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://f5.example/b", url_hash="h5b", status="pending"))
    db_session.commit()

    monkeypatch.setattr(
        "backend.workers.continuous_crawl.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": same_hash if url == same_url else "h5b", "title": "X", "content_raw": "Y",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")

    fetched = fetch_pending_urls(db_session, source)  # không được raise IntegrityError

    assert len(fetched) == 1  # chỉ bài KHÔNG đụng độ được tính
    assert fetched[0].url == "https://f5.example/b"
    rows = db_session.query(CrawlQueue).filter_by(source_id=source.source_id).all()
    assert all(r.status == "fetched" for r in rows)  # cả 2 URL đều đánh dấu xong, kể cả URL đụng độ
    assert db_session.query(Article).filter_by(source_id=source.source_id, url_hash=same_hash).count() == 1  # không trùng


def test_fetch_pending_urls_all_duplicate_cycle_does_not_count_as_error(db_session, monkeypatch):
    # Bug thật phát hiện lúc final review (2026-07-21): nếu CẢ chu kỳ chỉ toàn bài bị
    # IntegrityError (race với tiến trình khác, không phải site lỗi thật), fetched_articles
    # rỗng — nếu dùng fetched_articles để quyết định BR-SRC-03 thì consecutive_error_count
    # sẽ tăng oan, dù thực chất fetch THÀNH CÔNG (chỉ là tiến trình kia lưu trước). Phải dùng
    # handled_count (đếm cả bài IntegrityError) để reset đúng.
    source = _make_source(db_session, "Fetch6", consecutive_error_count=5)
    same_url = "https://f6.example/already-fetched-elsewhere"
    same_hash = compute_url_hash(same_url)
    db_session.add(
        Article(job_id=None, source_id=source.source_id, url=same_url, url_hash=same_hash, title="Đã có rồi")
    )
    db_session.add(CrawlQueue(source_id=source.source_id, url=same_url, url_hash=same_hash, status="pending"))
    db_session.commit()

    monkeypatch.setattr(
        "backend.workers.continuous_crawl.fetch_article_dispatch",
        lambda url, rules: {
            "url": url, "url_hash": same_hash, "title": "X", "content_raw": "Y",
            "author": None, "published_at": None, "crawl_duration_seconds": 0.1,
        },
    )
    monkeypatch.setenv("CRAWLER_DELAY_SECONDS", "0")

    fetched = fetch_pending_urls(db_session, source)

    assert fetched == []  # không có bài MỚI nào (đúng — bài này đã có sẵn)
    db_session.refresh(source)
    assert source.consecutive_error_count == 0  # KHÔNG được tăng — chu kỳ này fetch thành công thật


from backend.models import (
    Campaign,
    CampaignArticle,
    CampaignArticleKeyword,
    CampaignKeyword,
    CampaignSource,
    Keyword,
)
from backend.workers.continuous_crawl import match_campaigns_for_article


def test_match_campaigns_for_article_creates_bridge_rows_for_all_matched_keywords(db_session):
    source = _make_source(db_session, "Match1")
    campaign = Campaign(name="Chống lừa đảo", start_date="2026-08-01", status="ACTIVE")
    kw_match_1 = Keyword(keyword="lừa đảo")
    kw_match_2 = Keyword(keyword="Zalo")
    kw_no_match = Keyword(keyword="Facebook")
    db_session.add_all([campaign, kw_match_1, kw_match_2, kw_no_match])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw_match_1.keyword_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw_match_2.keyword_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw_no_match.keyword_id))
    article = Article(source_id=source.source_id, url="https://m1.example/a", url_hash="hm1",
                       title="Cảnh báo lừa đảo qua Zalo", content_raw="Nội dung chi tiết")
    db_session.add(article)
    db_session.commit()

    match_campaigns_for_article(db_session, article)

    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id, article_id=article.article_id).one()
    expected_first = min([kw_match_1.keyword_id, kw_match_2.keyword_id])
    assert ca.matched_keyword_id == expected_first

    matched_keyword_ids = {
        row.keyword_id
        for row in db_session.query(CampaignArticleKeyword).filter_by(
            campaign_id=campaign.campaign_id, article_id=article.article_id
        ).all()
    }
    assert matched_keyword_ids == {kw_match_1.keyword_id, kw_match_2.keyword_id}


def test_match_campaigns_for_article_skips_when_no_keyword_matches(db_session):
    source = _make_source(db_session, "Match2")
    campaign = Campaign(name="Không liên quan", start_date="2026-08-01", status="ACTIVE")
    kw = Keyword(keyword="an ninh mạng")
    db_session.add_all([campaign, kw])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw.keyword_id))
    article = Article(source_id=source.source_id, url="https://m2.example/a", url_hash="hm2",
                       title="Tin tức thể thao", content_raw="Không liên quan gì")
    db_session.add(article)
    db_session.commit()

    match_campaigns_for_article(db_session, article)

    assert db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id).count() == 0


def test_match_campaigns_for_article_ignores_non_active_campaign(db_session):
    source = _make_source(db_session, "Match3")
    campaign = Campaign(name="Còn nháp", start_date="2026-08-01", status="DRAFT")
    kw = Keyword(keyword="lừa đảo")
    db_session.add_all([campaign, kw])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=kw.keyword_id))
    article = Article(source_id=source.source_id, url="https://m3.example/a", url_hash="hm3",
                       title="Cảnh báo lừa đảo", content_raw="Nội dung")
    db_session.add(article)
    db_session.commit()

    match_campaigns_for_article(db_session, article)

    assert db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id).count() == 0

