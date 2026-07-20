import uuid
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Campaign, Keyword, Role, Source, User, UserRole
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
