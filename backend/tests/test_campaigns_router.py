import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Campaign, CampaignKeyword, CampaignSource, Keyword, ReportHistory, Role, Source, User, UserRole
from backend.routers import campaigns


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
            "start_date": "2026-08-01",
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


def test_activate_campaign_requires_source_and_keyword(app_client, admin_user):
    create_response = app_client.post(
        "/api/campaigns", json={"name": "Thiếu source/keyword", "start_date": "2026-08-01", "owner_id": str(admin_user.user_id)}
    )
    campaign_id = create_response.json()["campaign_id"]

    response = app_client.post(f"/api/campaigns/{campaign_id}/activate")

    assert response.status_code == 400  # BR-CAMP-03


def test_activate_campaign_succeeds_with_source_and_keyword(app_client, admin_user, source, keyword):
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


def test_create_campaign_allows_duplicate_source_and_keyword_ids(app_client, admin_user, source, keyword):
    # Payload có ID trùng lặp (VD FE gửi nhầm 2 lần cùng 1 source_id) vẫn phải được chấp nhận —
    # trước fix, so sánh len(sources) != len(source_ids) sai vì query DB tự dedup theo PK,
    # khiến input hợp lệ bị từ chối oan với lỗi "Có source_id không tồn tại"
    response = app_client.post(
        "/api/campaigns",
        json={
            "name": "Chiến dịch ID trùng lặp",
            "start_date": "2026-08-01",
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
    mock_task.delay.assert_called_once()

    report = db_session.get(ReportHistory, uuid.UUID(body["report_id"]))
    assert report.campaign_id == campaign.campaign_id
    assert report.format == "docx"
    assert report.status == "pending"


def test_create_campaign_report_rejects_invalid_format(app_client, admin_user, db_session):
    campaign = Campaign(name="C", start_date="2026-06-01", status="ACTIVE", owner_id=admin_user.user_id)
    db_session.add(campaign)
    db_session.commit()

    response = app_client.post(
        f"/api/campaigns/{campaign.campaign_id}/reports",
        json={"date_from": "2026-06-01", "date_to": "2026-06-30", "format": "exe"},
    )

    assert response.status_code == 400


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
        name="C", start_date="2026-06-01", status="DRAFT", owner_id=admin_user.user_id, mode="ONE_SHOT"
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


def test_activate_continuous_campaign_does_not_dispatch_chord(app_client, admin_user, source, keyword, db_session):
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
