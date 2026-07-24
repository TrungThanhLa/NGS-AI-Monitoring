import uuid
from datetime import datetime, timedelta, timezone

from backend.models import Campaign, CampaignSource, Source
from backend.system_settings import get_setting
from backend.workers.scheduler import check_due_sources, list_due_sources, complete_expired_continuous_campaigns


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


def test_list_due_sources_excludes_source_with_crawl_task_already_running(db_session):
    # Bug thật phát hiện qua smoke test thủ công (2026-07-24, log celery-worker xác nhận
    # 22 crawl_task chồng chất trong 15 phút cho cùng 1 nguồn): nguồn có backlog quá lớn,
    # 1 lượt Fetch chưa xong trong 60s (last_crawled_at vẫn NULL) → Beat cứ mỗi phút lại
    # coi là "đủ điều kiện", dispatch chồng thêm task mới dù task cũ vẫn đang chạy dở.
    # crawl_started_at (đã có sẵn cho cột UI "Trạng thái") chính là cờ cần dùng để chặn.
    campaign = _make_campaign(db_session)
    source = _make_source(
        db_session,
        status="ACTIVE",
        last_crawled_at=None,  # backlog lớn, chưa bao giờ crawl xong 1 lượt trọn vẹn
        crawl_frequency=1800,
        crawl_started_at=datetime.now(timezone.utc),  # đang có 1 task khác chạy dở
    )
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    due = list_due_sources(db_session)

    assert source.source_id not in {s.source_id for s in due}


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


def test_complete_expired_continuous_campaigns_marks_completed(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-10", status="ACTIVE", mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 1
    assert campaign.status == "COMPLETED"


def test_complete_expired_continuous_campaigns_ignores_campaign_without_end_date(db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "ACTIVE"


def test_complete_expired_continuous_campaigns_ignores_campaign_with_future_end_date(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2099-01-01", status="ACTIVE", mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "ACTIVE"


def test_complete_expired_continuous_campaigns_ignores_one_shot_campaign(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-10", status="ACTIVE", mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "ACTIVE"


def test_complete_expired_continuous_campaigns_ignores_already_paused_campaign(db_session):
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-10", status="PAUSED", mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.commit()

    count = complete_expired_continuous_campaigns(db_session, now=now)

    db_session.refresh(campaign)
    assert count == 0
    assert campaign.status == "PAUSED"


def test_check_due_sources_writes_last_beat_tick_at_even_when_scheduler_disabled(db_session, monkeypatch):
    # FE dùng LAST_BEAT_TICK_AT vẽ ring loader đếm theo nhịp Beat — phải được ghi mỗi
    # chu kỳ Beat THẬT SỰ chạy, kể cả khi SCHEDULER_ENABLED=false (Beat vẫn "đập" đúng
    # giờ, chỉ là quyết định không dispatch crawl_task — ring loader phản ánh Beat có
    # sống hay không, không phải "có đang crawl hay không").
    from backend.models import SystemSetting

    db_session.query(SystemSetting).filter_by(setting_key="SCHEDULER_ENABLED").update({"setting_value": "false"})
    db_session.commit()
    monkeypatch.setattr("backend.workers.scheduler.SessionLocal", lambda: db_session)

    before = datetime.now(timezone.utc)
    check_due_sources.run()
    after = datetime.now(timezone.utc)

    raw_value = get_setting(db_session, "LAST_BEAT_TICK_AT")
    assert raw_value is not None
    tick_at = datetime.fromisoformat(raw_value)
    assert before <= tick_at <= after


def test_check_due_sources_claims_source_before_dispatch(db_session, monkeypatch):
    # "Claim" (đánh dấu crawl_started_at) phải xảy ra NGAY lúc check_due_sources quyết
    # định dispatch — không được để tới lúc crawl_task thực sự bắt đầu chạy mới đánh dấu,
    # vì giữa lúc dispatch và lúc task thực sự được 1 worker rảnh nhận (có thể trễ nếu
    # pool đang bận) là 1 khoảng hở đủ để Beat lượt sau (60s) tưởng nhầm "chưa ai xử lý".
    from backend.models import SystemSetting
    from backend.workers import continuous_crawl

    db_session.query(SystemSetting).filter_by(setting_key="SCHEDULER_ENABLED").update({"setting_value": "true"})
    db_session.commit()
    monkeypatch.setattr("backend.workers.scheduler.SessionLocal", lambda: db_session)

    campaign = _make_campaign(db_session)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    dispatched: list[str] = []
    monkeypatch.setattr(continuous_crawl.crawl_task, "delay", lambda sid: dispatched.append(sid))

    source_id = source.source_id  # đọc trước — check_due_sources tự db.close() ở cuối
    check_due_sources.run()

    assert dispatched == [str(source_id)]
    reloaded = db_session.get(Source, source_id)
    assert reloaded.crawl_started_at is not None


def test_check_due_sources_does_not_dispatch_twice_across_two_ticks_for_same_source(db_session, monkeypatch):
    # Regression trực tiếp cho bug thật: 22 crawl_task chồng chất trong 15 phút cho cùng
    # 1 nguồn (VOV.vn, backlog lớn không kịp xong trong 60s). Lượt 2 phải KHÔNG dispatch
    # thêm vì nguồn đã bị claim ở lượt 1 và chưa có ai giải phóng (crawl_task thật chưa
    # chạy xong — ở đây mock .delay nên không tự xóa cờ, mô phỏng đúng "vẫn đang chạy dở").
    from backend.models import SystemSetting
    from backend.workers import continuous_crawl

    db_session.query(SystemSetting).filter_by(setting_key="SCHEDULER_ENABLED").update({"setting_value": "true"})
    db_session.commit()
    monkeypatch.setattr("backend.workers.scheduler.SessionLocal", lambda: db_session)

    campaign = _make_campaign(db_session)
    source = _make_source(db_session, status="ACTIVE", last_crawled_at=None, crawl_frequency=1800)
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    dispatched: list[str] = []
    monkeypatch.setattr(continuous_crawl.crawl_task, "delay", lambda sid: dispatched.append(sid))

    check_due_sources.run()
    check_due_sources.run()

    assert dispatched == [str(source.source_id)]
