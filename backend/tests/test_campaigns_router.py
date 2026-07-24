import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import (
    Article,
    Campaign,
    CampaignArticle,
    CampaignCrawlProgress,
    CampaignKeyword,
    CampaignSource,
    CrawlQueue,
    Keyword,
    ReportHistory,
    Role,
    Source,
    SystemSetting,
    User,
    UserRole,
)
from backend.routers import campaigns, report_history


@pytest.fixture
def admin_user(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"admin-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(campaigns.router)
    app.include_router(report_history.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


@pytest.fixture
def source(db_session):
    s = Source(name="Test Source", domain=f"test-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    db_session.add(s)
    db_session.commit()
    return s


@pytest.fixture
def keyword(db_session):
    k = Keyword(keyword="test-keyword", is_active=True)
    db_session.add(k)
    db_session.commit()
    return k


def test_create_campaign_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(campaigns.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.post("/api/campaigns", json={"name": "X", "start_date": "2026-08-01", "owner_id": str(uuid.uuid4())})
    assert response.status_code == 403


def test_create_campaign_minimal_defaults_to_draft(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={"name": "Chiến dịch test", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["mode"] == "CONTINUOUS"
    assert body["source_ids"] == []
    assert body["keyword_ids"] == []


def test_create_campaign_requires_name(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns", json={"name": "  ", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    assert response.status_code == 400


def test_create_campaign_rejects_unknown_owner(app_client):
    response = app_client.post(
        "/api/campaigns", json={"name": "X", "start_date": "2026-08-01", "owner_id": str(uuid.uuid4())}
    )
    assert response.status_code == 400


def test_create_campaign_with_sources_and_keywords(app_client, admin_user, source, keyword):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Chiến dịch đầy đủ",
            "start_date": "2026-06-01",
            "end_date": "2026-06-01",
            "owner_id": str(admin_user.user_id),
            "mode": "ONE_SHOT",
            "source_ids": [str(source.source_id)],
            "keyword_ids": [str(keyword.keyword_id)],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["mode"] == "ONE_SHOT"
    assert body["source_ids"] == [str(source.source_id)]
    assert body["keyword_ids"] == [str(keyword.keyword_id)]


def test_create_campaign_rejects_unknown_source_id(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "X",
            "start_date": "2026-08-01",
            "owner_id": str(admin_user.user_id),
            "source_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 400


def test_list_campaigns_filters_by_status(app_client, admin_user, db_session):
    draft = Campaign(name="Draft camp", owner_id=admin_user.user_id, status="DRAFT", start_date=date(2026, 8, 1))
    active = Campaign(name="Active camp", owner_id=admin_user.user_id, status="ACTIVE", start_date=date(2026, 8, 1))
    db_session.add_all([draft, active])
    db_session.commit()

    response = app_client.get("/api/campaigns", params={"status": "ACTIVE"})

    names = [c["name"] for c in response.json()["campaigns"]]
    assert "Active camp" in names
    assert "Draft camp" not in names


def test_list_campaigns_filters_by_keyword_substring(app_client, admin_user, db_session):
    matched = Campaign(name="Chống tin giả y tế", owner_id=admin_user.user_id, start_date=date(2026, 8, 1))
    other = Campaign(name="Chiến dịch khác", owner_id=admin_user.user_id, start_date=date(2026, 8, 1))
    db_session.add_all([matched, other])
    db_session.commit()

    response = app_client.get("/api/campaigns", params={"keyword": "tin giả"})

    names = [c["name"] for c in response.json()["campaigns"]]
    assert "Chống tin giả y tế" in names
    assert "Chiến dịch khác" not in names


def test_get_campaign_detail_returns_404_when_missing(app_client):
    response = app_client.get(f"/api/campaigns/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_campaign_detail_returns_full_info(app_client, admin_user, source, keyword):
    create_response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Chi tiết",
            "start_date": "2026-08-01",
            "owner_id": str(admin_user.user_id),
            "source_ids": [str(source.source_id)],
            "keyword_ids": [str(keyword.keyword_id)],
        },
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.get(f"/api/campaigns/{campaign_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Chi tiết"
    assert body["source_ids"] == [str(source.source_id)]
    assert body["keyword_ids"] == [str(keyword.keyword_id)]


def test_update_campaign_changes_fields(app_client, admin_user, source, keyword):
    create_response = app_client.post(
        "/api/campaigns", json={"name": "Trước sửa", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.put(
        f"/api/campaigns/{campaign_id}",
        json={"name": "Sau sửa", "source_ids": [str(source.source_id)], "keyword_ids": [str(keyword.keyword_id)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sau sửa"
    assert body["source_ids"] == [str(source.source_id)]
    assert body["keyword_ids"] == [str(keyword.keyword_id)]


def test_update_campaign_rejects_when_archived(app_client, admin_user, db_session):
    campaign = Campaign(name="Đã archive", owner_id=admin_user.user_id, status="ARCHIVED", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.put(f"/api/campaigns/{campaign.campaign_id}", json={"name": "Sửa sau archive"})

    assert response.status_code == 400  # BR-CAMP-04: ARCHIVED chỉ được xem, không được sửa


def test_delete_campaign_soft_deletes_to_archived(app_client, admin_user):
    create_response = app_client.post(
        "/api/campaigns", json={"name": "Sẽ archive", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.delete(f"/api/campaigns/{campaign_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"

    detail = app_client.get(f"/api/campaigns/{campaign_id}")
    assert detail.json()["status"] == "ARCHIVED"  # BR-CAMP-05: không xóa vật lý


def test_delete_campaign_already_archived_returns_400(app_client, admin_user, db_session):
    campaign = Campaign(name="Archived rồi", owner_id=admin_user.user_id, status="ARCHIVED", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.delete(f"/api/campaigns/{campaign.campaign_id}")

    assert response.status_code == 400


def _enable_scheduler(db_session):
    db_session.query(SystemSetting).filter_by(setting_key="SCHEDULER_ENABLED").update({"setting_value": "true"})
    db_session.commit()


def test_activate_campaign_requires_source_and_keyword(app_client, admin_user):
    create_response = app_client.post(
        "/api/campaigns", json={"name": "Thiếu source/keyword", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.post(f"/api/campaigns/{campaign_id}/activate")

    assert response.status_code == 400  # BR-CAMP-03


def test_activate_campaign_succeeds_with_source_and_keyword(app_client, admin_user, source, keyword, db_session):
    _enable_scheduler(db_session)
    create_response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Đủ điều kiện",
            "start_date": "2026-08-01",
            "owner_id": str(admin_user.user_id),
            "source_ids": [str(source.source_id)],
            "keyword_ids": [str(keyword.keyword_id)],
        },
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.post(f"/api/campaigns/{campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"


def test_activate_campaign_rejects_when_archived(app_client, admin_user, db_session):
    campaign = Campaign(name="Archived", owner_id=admin_user.user_id, status="ARCHIVED", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 400


def test_pause_campaign_requires_active_status(app_client, admin_user, db_session):
    campaign = Campaign(name="Draft chưa activate", owner_id=admin_user.user_id, status="DRAFT", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/pause")

    assert response.status_code == 400


def test_pause_campaign_succeeds_from_active(app_client, admin_user, db_session):
    campaign = Campaign(name="Đang active", owner_id=admin_user.user_id, status="ACTIVE", start_date=date(2026, 8, 1))
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/pause")

    assert response.status_code == 200
    assert response.json()["status"] == "PAUSED"


def test_pause_campaign_revokes_running_crawl_task_for_its_source(app_client, admin_user, db_session, source):
    # Bug thật phát hiện qua smoke test thủ công (2026-07-24): Pause chỉ đổi DB status,
    # không hề tác động tới crawl_task Celery đang chạy dở cho nguồn của Campaign — task
    # đó cứ chạy tiếp tuần tự (1.5s/URL) cho tới hết batch hiện tại dù đã Pause, khiến
    # nút Tạm dừng không có tác dụng "phanh khẩn cấp" ngay lập tức. Sửa bằng cách tra
    # celery_app.control.inspect().active() (không cần thêm cột DB lưu task_id) để tìm
    # đúng task "continuous_crawl.crawl_task" đang chạy cho source_id của Campaign này,
    # rồi revoke(terminate=True) — cùng pattern đã dùng cho Hủy báo cáo (report cancel).
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    with patch("backend.routers.campaigns.celery_app") as mock_celery_app:
        mock_celery_app.control.inspect.return_value.active.return_value = {
            "worker1@host": [
                {
                    "id": "task-xyz",
                    "name": "continuous_crawl.crawl_task",
                    "args": [str(source.source_id)],
                },
                {
                    "id": "task-other-source",
                    "name": "continuous_crawl.crawl_task",
                    "args": [str(uuid.uuid4())],
                },
                {
                    "id": "task-unrelated-name",
                    "name": "scheduler.check_due_sources",
                    "args": [],
                },
            ]
        }
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/pause")

    assert response.status_code == 200
    assert response.json()["status"] == "PAUSED"
    mock_celery_app.control.revoke.assert_called_once_with("task-xyz", terminate=True)


def test_pause_campaign_clears_crawl_started_at_for_revoked_source(app_client, admin_user, db_session, source):
    # Bug thật phát hiện qua smoke test thủ công (2026-07-24, log celery-worker xác nhận):
    # revoke(terminate=True) gửi SIGTERM giết hẳn tiến trình con — code Python trong
    # finally của crawl_task (chỗ xóa crawl_started_at) KHÔNG kịp chạy vì tiến trình đã
    # bị OS kill giữa chừng. Cờ "Đang quét" kẹt vĩnh viễn trên UI. Phải tự xóa cờ ngay
    # tại nơi gọi revoke, không được trông chờ code bên trong task tự dọn dẹp.
    from datetime import datetime, timezone

    source.crawl_started_at = datetime.now(timezone.utc)
    db_session.commit()

    campaign = Campaign(
        name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    with patch("backend.routers.campaigns.celery_app") as mock_celery_app:
        mock_celery_app.control.inspect.return_value.active.return_value = {
            "worker1@host": [
                {"id": "task-xyz", "name": "continuous_crawl.crawl_task", "args": [str(source.source_id)]},
            ]
        }
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/pause")

    assert response.status_code == 200
    db_session.refresh(source)
    assert source.crawl_started_at is None


def test_pause_campaign_does_not_revoke_source_still_watched_by_other_active_campaign(
    app_client, admin_user, db_session, source
):
    # Nếu 1 Nguồn còn được Campaign CONTINUOUS ACTIVE KHÁC theo dõi, không được revoke —
    # sẽ làm gián đoạn crawl hợp lệ của campaign kia (dữ liệu không mất, chỉ trễ tới chu
    # kỳ sau, nhưng không có lý do gì để ngắt ngang task đang phục vụ campaign còn Active).
    campaign_to_pause = Campaign(
        name="C1", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    other_active_campaign = Campaign(
        name="C2", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add_all([campaign_to_pause, other_active_campaign])
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign_to_pause.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=other_active_campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    with patch("backend.routers.campaigns.celery_app") as mock_celery_app:
        mock_celery_app.control.inspect.return_value.active.return_value = {
            "worker1@host": [
                {"id": "task-xyz", "name": "continuous_crawl.crawl_task", "args": [str(source.source_id)]},
            ]
        }
        response = app_client.post(f"/api/campaigns/{campaign_to_pause.campaign_id}/pause")

    assert response.status_code == 200
    mock_celery_app.control.revoke.assert_not_called()


def test_create_campaign_allows_duplicate_source_and_keyword_ids(app_client, admin_user, source, keyword):
    # Payload có ID trùng lặp (VD FE gửi nhầm 2 lần cùng 1 source_id) vẫn phải được chấp nhận —
    # trước fix, so sánh len(sources) != len(source_ids) sai vì query DB tự dedup theo PK,
    # khiến input hợp lệ bị từ chối oan với lỗi "Có source_id không tồn tại"
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Chiến dịch ID trùng lặp",
            "start_date": "2026-06-01",
            "end_date": "2026-06-01",
            "owner_id": str(admin_user.user_id),
            "mode": "ONE_SHOT",
            "source_ids": [str(source.source_id), str(source.source_id)],
            "keyword_ids": [str(keyword.keyword_id), str(keyword.keyword_id)],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_ids"] == [str(source.source_id)]
    assert body["keyword_ids"] == [str(keyword.keyword_id)]


def test_create_campaign_report_dispatches_celery_task_and_returns_pending(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    with patch("backend.routers.campaigns.generate_campaign_report") as mock_task:
        response = app_client.post(
            f"/api/campaigns/{campaign.campaign_id}/reports",
            json={"date_from": "2026-06-01", "date_to": "2026-06-30", "format": "docx"},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    mock_task.apply_async.assert_called_once()

    report = db_session.get(ReportHistory, uuid.UUID(body["report_id"]))
    assert report.campaign_id == campaign.campaign_id
    assert report.format == "docx"
    assert report.status == "pending"
    assert report.celery_task_id is not None


def test_create_campaign_report_rejects_invalid_format(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(
        f"/api/campaigns/{campaign.campaign_id}/reports",
        json={"date_from": "2026-06-01", "date_to": "2026-06-30", "format": "exe"},
    )

    assert response.status_code == 400


def test_cancel_campaign_report_revokes_task_and_sets_cancelled(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    report = ReportHistory(
        campaign_id=campaign.campaign_id, file_path="", format="docx", status="pending", celery_task_id="task-abc"
    )
    db_session.add(report)
    db_session.commit()

    with patch("backend.routers.campaigns.celery_app") as mock_celery_app:
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/reports/{report.report_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    mock_celery_app.control.revoke.assert_called_once_with("task-abc", terminate=True)

    db_session.refresh(report)
    assert report.status == "cancelled"


def test_cancel_campaign_report_rejects_already_completed_report(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    report = ReportHistory(campaign_id=campaign.campaign_id, file_path="/x.docx", format="docx", status="completed")
    db_session.add(report)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/reports/{report.report_id}/cancel")

    assert response.status_code == 400
    db_session.refresh(report)
    assert report.status == "completed"


def test_cancel_campaign_report_returns_404_for_unknown_report(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/reports/{uuid.uuid4()}/cancel")

    assert response.status_code == 404


def test_get_campaign_report_status_returns_report_row(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    report = ReportHistory(campaign_id=campaign.campaign_id, file_path="", status="running", format="pdf")
    db_session.add(report)
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/reports/{report.report_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_list_campaign_reports_sorted_newest_first(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    # created_at đặt tay (không dùng server_default=func.now()) — NOW() của Postgres cố định
    # trong suốt 1 transaction, mà db_session test chạy trong 1 transaction ngoài duy nhất
    # (SAVEPOINT lồng, xem conftest.py), nên để mặc định sẽ làm r1/r2 trùng created_at, thứ
    # tự không xác định — cùng pattern đã dùng ở test_reports_router.py::test_history_orders_by_created_at_desc
    r1 = ReportHistory(
        campaign_id=campaign.campaign_id, file_path="a", status="completed", format="docx", created_at=date(2026, 1, 1)
    )
    db_session.add(r1)
    db_session.commit()
    r2 = ReportHistory(
        campaign_id=campaign.campaign_id, file_path="b", status="completed", format="pdf", created_at=date(2026, 1, 2)
    )
    db_session.add(r2)
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/reports")

    ids = [r["report_id"] for r in response.json()["reports"]]
    assert ids == [str(r2.report_id), str(r1.report_id)]


def test_activate_one_shot_campaign_dispatches_chord(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    mock_chord.assert_called_once()


def test_activate_one_shot_campaign_creates_progress_rows(app_client, admin_user, source, keyword, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert progress.status == "pending"


def test_activate_one_shot_campaign_after_pause_does_not_crash(app_client, admin_user, source, keyword, db_session):
    # Tái hiện bug thật: activate ONE_SHOT -> pause giữa chừng -> activate lại từng bị 500
    # (IntegrityError trùng PRIMARY KEY (campaign_id, source_id) của campaign_crawl_progress)
    # vì code cũ luôn INSERT mà không xóa dòng tiến độ cũ trước đó.
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        first_response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")
    assert first_response.status_code == 200

    # Giả lập crawl CHƯA xong (còn dở, VD đang discovering) lúc bị Pause
    progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    progress.total_urls = None
    progress.done_urls = 0
    progress.status = "discovering"
    db_session.commit()

    pause_response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/pause")
    assert pause_response.status_code == 200

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        reactivate_response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["status"] == "ACTIVE"
    mock_chord.assert_called_once()

    # Nguồn CHƯA done -> dòng tiến độ cũ bị xóa, tạo lại mới (reset), vì không có cách
    # nào "tiếp tục" đúng chỗ dở dang (Discover không lưu trạng thái từng phần)
    refreshed = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert refreshed.total_urls is None
    assert refreshed.done_urls == 0
    assert refreshed.status == "pending"


def test_activate_one_shot_campaign_skips_sources_already_done(app_client, admin_user, source, keyword, db_session):
    # Nguồn đã done từ lượt trước -> kích hoạt lại KHÔNG được đụng vào (không xóa, không
    # đưa vào chord crawl lại) — tránh lãng phí Discover + matching lại 1 lượt vô ích
    # (phát hiện qua smoke test thật 2026-07-23, VD VTV News 320/320 done bị crawl lại
    # oan mỗi lần Tạm dừng/Kích hoạt lại)
    other_source = Source(name="Other", domain=f"other-{uuid.uuid4()}.example", group_name="G")
    db_session.add(other_source)
    db_session.flush()

    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=other_source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.add(
        CampaignCrawlProgress(
            campaign_id=campaign.campaign_id, source_id=source.source_id,
            total_urls=320, done_urls=320, status="done",
        )
    )
    db_session.commit()
    campaign.status = "PAUSED"
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    mock_chord.assert_called_once()
    # Verify qua kết quả DB (đáng tin cậy hơn suy luận args nội bộ generator đã truyền cho mock):
    done_progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=source.source_id
    ).one()
    assert done_progress.total_urls == 320
    assert done_progress.done_urls == 320
    assert done_progress.status == "done"  # không bị đụng vào

    other_progress = db_session.query(CampaignCrawlProgress).filter_by(
        campaign_id=campaign.campaign_id, source_id=other_source.source_id
    ).one()
    assert other_progress.status == "pending"  # dòng mới tạo cho Nguồn chưa done


def test_activate_one_shot_campaign_completes_immediately_when_all_sources_already_done(
    app_client, admin_user, source, keyword, db_session
):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="PAUSED", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.add(
        CampaignCrawlProgress(
            campaign_id=campaign.campaign_id, source_id=source.source_id,
            total_urls=10, done_urls=10, status="done",
        )
    )
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    mock_chord.assert_not_called()


def test_activate_continuous_campaign_does_not_dispatch_chord(app_client, admin_user, source, keyword, db_session):
    _enable_scheduler(db_session)
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    mock_chord.assert_not_called()


def test_activate_continuous_campaign_rejects_when_scheduler_disabled(app_client, admin_user, source, keyword, db_session):
    # CONTINUOUS phụ thuộc Celery Beat để thực sự crawl; nếu công tắc đang tắt, kích hoạt
    # "thành công" (status=ACTIVE) nhưng không có gì được crawl cho tới khi Admin bật lại —
    # dễ gây hiểu nhầm. Chặn hẳn ở đây thay vì chỉ cảnh báo UI. Set tường minh 'false' thay
    # vì trông cậy giá trị seed mặc định — DB dev thật có thể đã bị đổi qua UI/API trước đó.
    db_session.query(SystemSetting).filter_by(setting_key="SCHEDULER_ENABLED").update({"setting_value": "false"})
    db_session.commit()
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 400
    assert "SCHEDULER_ENABLED" in response.json()["detail"]
    db_session.refresh(campaign)
    assert campaign.status == "DRAFT"


def test_activate_one_shot_campaign_ignores_scheduler_disabled(app_client, admin_user, source, keyword, db_session):
    # ONE_SHOT không phụ thuộc SCHEDULER_ENABLED (crawl ngay qua chord riêng) — SCHEDULER_ENABLED
    # mặc định 'false' và KHÔNG được chặn ở đây, khác hẳn CONTINUOUS.
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    with patch("backend.routers.campaigns.chord") as mock_chord:
        mock_chord.return_value.return_value = MagicMock()
        response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    mock_chord.assert_called_once()


def test_list_all_reports_history_includes_campaign_name(app_client, admin_user, db_session):
    campaign = Campaign(name="Chiến dịch ABC", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.flush()
    db_session.add(ReportHistory(campaign_id=campaign.campaign_id, file_path="a.docx", format="docx", status="completed"))
    db_session.commit()

    response = app_client.get("/api/reports-history")

    assert response.status_code == 200
    rows = response.json()["history"]
    assert len(rows) > 0
    assert rows[0]["campaign_name"] == "Chiến dịch ABC"
    assert rows[0]["format"] == "docx"


def test_create_one_shot_campaign_requires_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01", "mode": "ONE_SHOT"},
    )
    assert response.status_code == 400
    assert "Ngày kết thúc" in response.json()["detail"]


def test_create_one_shot_campaign_rejects_future_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01",
            "end_date": "2099-01-01", "mode": "ONE_SHOT",
        },
    )
    assert response.status_code == 400
    assert "quá khứ" in response.json()["detail"]


def test_create_one_shot_campaign_accepts_past_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01",
            "end_date": "2026-06-05", "mode": "ONE_SHOT",
        },
    )
    assert response.status_code == 201


def test_create_continuous_campaign_does_not_require_end_date(app_client, admin_user):
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": "2026-06-01", "mode": "CONTINUOUS"},
    )
    assert response.status_code == 201


def test_update_campaign_to_one_shot_without_end_date_rejected(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.commit()

    response = app_client.put(f"/api/campaigns/{campaign.campaign_id}", json={"mode": "ONE_SHOT"})

    assert response.status_code == 400


def test_activate_one_shot_campaign_without_end_date_rejected(app_client, admin_user, source, keyword, db_session):
    # Campaign cũ tạo trước khi có validate này (ORM thẳng, bỏ qua create endpoint) —
    # activate vẫn phải chặn (defense-in-depth)
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 400


def test_crawl_progress_one_shot_returns_percent_from_progress_rows(app_client, admin_user, source, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="ACTIVE",
        owner_id=admin_user.user_id, mode="ONE_SHOT",
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignCrawlProgress(
        campaign_id=campaign.campaign_id, source_id=source.source_id,
        total_urls=10, done_urls=4, status="fetching",
    ))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "ONE_SHOT"
    assert body["overall_percent"] == 40.0
    assert body["sources"][0]["total_urls"] == 10
    assert body["sources"][0]["done_urls"] == 4
    assert body["sources"][0]["status"] == "fetching"


def test_crawl_progress_one_shot_source_without_progress_row_shows_pending(app_client, admin_user, source, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", end_date="2026-06-01", status="ACTIVE",
        owner_id=admin_user.user_id, mode="ONE_SHOT",
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")

    body = response.json()
    assert body["sources"][0]["status"] == "pending"
    assert body["sources"][0]["total_urls"] is None
    assert body["overall_percent"] == 0.0


def test_crawl_progress_continuous_returns_source_activity(app_client, admin_user, source, db_session):
    campaign = Campaign(
        name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS",
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CrawlQueue(source_id=source.source_id, url="https://x.example/p", url_hash="hp", status="pending"))
    article = Article(source_id=source.source_id, url="https://x.example/a", url_hash="ha")
    db_session.add(article)
    db_session.flush()
    db_session.add(CampaignArticle(campaign_id=campaign.campaign_id, article_id=article.article_id))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "CONTINUOUS"
    assert body["sources"][0]["pending_count"] == 1
    assert body["sources"][0]["matched_last_24h"] == 1


def test_crawl_progress_continuous_orders_never_crawled_sources_first_then_oldest(
    app_client, admin_user, db_session
):
    # UI yêu cầu (2026-07-24): Nguồn chưa từng crawl lên đầu bảng, còn lại xếp theo
    # lần crawl gần nhất xa -> gần. Trước đây query không có ORDER BY, Postgres không
    # đảm bảo thứ tự ổn định giữa 2 lần gọi API (đã quan sát thật trên UI).
    from datetime import datetime, timezone

    never_crawled = Source(name="Never", domain=f"never-{uuid.uuid4()}.example", group_name="G", is_active=True)
    crawled_recent = Source(
        name="Recent",
        domain=f"recent-{uuid.uuid4()}.example",
        group_name="G",
        is_active=True,
        last_crawled_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    crawled_old = Source(
        name="Old",
        domain=f"old-{uuid.uuid4()}.example",
        group_name="G",
        is_active=True,
        last_crawled_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([never_crawled, crawled_recent, crawled_old])
    db_session.flush()

    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.flush()
    for s in (crawled_recent, never_crawled, crawled_old):  # cố ý thêm không theo thứ tự mong đợi
        db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=s.source_id))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")

    assert response.status_code == 200
    names = [s["source_name"] for s in response.json()["sources"]]
    assert names == ["Never", "Old", "Recent"]


def test_crawl_progress_continuous_includes_scan_status_per_source(app_client, admin_user, source, db_session):
    from datetime import datetime, timezone

    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")
    assert response.json()["sources"][0]["scan_status"] == "IDLE"

    source.crawl_started_at = datetime.now(timezone.utc)
    db_session.commit()

    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")
    assert response.json()["sources"][0]["scan_status"] == "SCANNING"


def test_crawl_progress_continuous_includes_last_beat_tick_at(app_client, admin_user, source, db_session):
    from backend.system_settings import set_setting

    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id, mode="CONTINUOUS")
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.commit()

    # Không assert giá trị ban đầu là None — DB dev thật có thể đã có Celery Beat chạy
    # thật từ trước, ghi sẵn LAST_BEAT_TICK_AT (ambient state, không liên quan tới test
    # này). Chỉ cần xác nhận field tồn tại và phản ánh đúng giá trị vừa ghi.
    set_setting(db_session, "LAST_BEAT_TICK_AT", "2026-07-24T01:47:00+00:00")
    response = app_client.get(f"/api/campaigns/{campaign.campaign_id}/crawl-progress")
    assert response.json()["last_beat_tick_at"] == "2026-07-24T01:47:00+00:00"


def test_create_continuous_campaign_rejects_start_date_older_than_180_days(app_client, admin_user):
    too_old = (date.today() - timedelta(days=200)).isoformat()
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": too_old, "mode": "CONTINUOUS"},
    )
    assert response.status_code == 400
    assert "180" in response.json()["detail"]


def test_create_continuous_campaign_accepts_start_date_within_180_days(app_client, admin_user):
    ok_date = (date.today() - timedelta(days=170)).isoformat()
    response = app_client.post(
        "/api/campaigns",
        json={"name": "C", "owner_id": str(admin_user.user_id), "start_date": ok_date, "mode": "CONTINUOUS"},
    )
    assert response.status_code == 201


def test_update_campaign_to_continuous_with_old_start_date_rejected(app_client, admin_user, db_session):
    too_old = date.today() - timedelta(days=200)
    campaign = Campaign(
        name="C", start_date=too_old, end_date=too_old, status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
    )
    db_session.add(campaign)
    db_session.commit()

    response = app_client.put(f"/api/campaigns/{campaign.campaign_id}", json={"mode": "CONTINUOUS"})

    assert response.status_code == 400
    assert "180" in response.json()["detail"]


def test_activate_continuous_campaign_with_old_start_date_rejected(app_client, admin_user, source, keyword, db_session):
    # Campaign cũ tạo trước khi có validate này (ORM thẳng, bỏ qua create endpoint) —
    # activate vẫn phải chặn (defense-in-depth, đúng pattern _validate_one_shot_date_range)
    too_old = date.today() - timedelta(days=200)
    campaign = Campaign(
        name="C", start_date=too_old, status="DRAFT", owner_id=admin_user.user_id, mode="CONTINUOUS"
    )
    db_session.add(campaign)
    db_session.flush()
    db_session.add(CampaignSource(campaign_id=campaign.campaign_id, source_id=source.source_id))
    db_session.add(CampaignKeyword(campaign_id=campaign.campaign_id, keyword_id=keyword.keyword_id))
    db_session.commit()

    response = app_client.post(f"/api/campaigns/{campaign.campaign_id}/activate")

    assert response.status_code == 400
    assert "180" in response.json()["detail"]
