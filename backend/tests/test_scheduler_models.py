import uuid

from backend.models import (
    Campaign,
    CampaignArticle,
    CampaignArticleKeyword,
    CrawlQueue,
    Keyword,
    Source,
    SystemSetting,
)


def test_crawl_queue_model_roundtrip(db_session):
    source = Source(name="X", domain=f"x-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.flush()

    row = CrawlQueue(source_id=source.source_id, url="https://x.example/a", url_hash="hash1")
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(CrawlQueue).filter_by(url_hash="hash1").one()
    assert fetched.status == "pending"
    assert fetched.retry_count == 0


def test_system_setting_model_roundtrip(db_session):
    row = db_session.query(SystemSetting).filter_by(setting_key="SCHEDULER_ENABLED").first()
    assert row is not None
    assert row.setting_value == "false"


def test_source_has_scheduler_columns_with_defaults(db_session):
    source = Source(name="Y", domain=f"y-{uuid.uuid4()}.example", group_name="G", is_active=True)
    db_session.add(source)
    db_session.commit()

    assert source.crawl_frequency == 1800
    assert source.status == "ACTIVE"
    assert source.consecutive_error_count == 0
    assert source.last_crawled_at is None


def test_campaign_article_and_keyword_bridge_roundtrip(db_session):
    source = Source(name="Z", domain=f"z-{uuid.uuid4()}.example", group_name="G", is_active=True)
    campaign = Campaign(name="C1", start_date="2026-08-01")
    keyword = Keyword(keyword="lừa đảo")
    db_session.add_all([source, campaign, keyword])
    db_session.flush()

    from backend.models import Article

    article = Article(source_id=source.source_id, url="https://z.example/a", url_hash="hash2")
    db_session.add(article)
    db_session.flush()

    db_session.add(
        CampaignArticle(campaign_id=campaign.campaign_id, article_id=article.article_id, matched_keyword_id=keyword.keyword_id)
    )
    db_session.flush()
    db_session.add(
        CampaignArticleKeyword(campaign_id=campaign.campaign_id, article_id=article.article_id, keyword_id=keyword.keyword_id)
    )
    db_session.commit()

    ca = db_session.query(CampaignArticle).filter_by(campaign_id=campaign.campaign_id).one()
    assert ca.article_id == article.article_id
    cak = db_session.query(CampaignArticleKeyword).filter_by(campaign_id=campaign.campaign_id).one()
    assert cak.keyword_id == keyword.keyword_id
