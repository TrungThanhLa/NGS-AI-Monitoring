import uuid
from datetime import datetime, timedelta, timezone

from backend.models import Campaign, CampaignSource, Source
from backend.workers.scheduler import list_due_sources


def _make_campaign(db_session, status="ACTIVE"):
    campaign = Campaign(name=f"C-{uuid.uuid4()}", start_date="2026-08-01", status=status)
    db_session.add(campaign)
    db_session.flush()
    return campaign


def _make_source(db_session, **kwargs):
    source = Source(name=f"S-{uuid.uuid4()}", domain=f"s-{uuid.uuid4()}.example", group_name="G", is_active=True, **kwargs)
    db_session.add(source)
    db_session.flush()
    return source


def test_list_due_sources_includes_never_crawled_source(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id in {s.source_id for s in due}


def test_list_due_sources_excludes_recently_crawled_source(db_session):
    campaign = _make_campaign(db_session)
    now = datetime.now(timezone.utc)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=now, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session, now=now + timedelta(seconds=60))

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_excludes_inactive_source_status(db_session):
    campaign = _make_campaign(db_session)
    source = _make_source(db_session, status="ERROR", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_excludes_source_of_non_active_campaign(db_session):
    campaign = _make_campaign(db_session, status="DRAFT")
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_deduplicates_source_watched_by_two_active_campaigns(db_session):
    campaign_a = _make_campaign(db_session)
    campaign_b = _make_campaign(db_session)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign_a.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=campaign_b.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert [s.source_id for s in due].count(source.source_id) == 1


def test_list_due_sources_excludes_source_only_watched_by_one_shot_campaign(db_session):
    campaign = _make_campaign(db_session)
    campaign.mode = "ONE_SHOT"
    db_session.commit()
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id not in {s.source_id for s in due}


def test_list_due_sources_includes_source_watched_by_continuous_campaign_even_if_also_one_shot(db_session):
    continuous = _make_campaign(db_session)
    one_shot = _make_campaign(db_session)
    one_shot.mode = "ONE_SHOT"
    db_session.commit()
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=continuous.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=one_shot.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id in {s.source_id for s in due}
