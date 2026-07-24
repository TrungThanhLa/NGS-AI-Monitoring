import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Campaign, Role, User, UserRole
from backend.routers import system_settings


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
def viewer_user(db_session):
    role = db_session.query(Role).filter_by(code="VIEWER").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"viewer-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(system_settings.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def test_list_settings_returns_seeded_rows(app_client):
    response = app_client.get("/api/system-settings")

    assert response.status_code == 200
    keys = {s["setting_key"] for s in response.json()["settings"]}
    assert {"SCHEDULER_ENABLED", "AI_AUTO_TRIGGER"} <= keys


def test_list_settings_rejects_user_without_permission(db_session, viewer_user):
    app = FastAPI()
    app.include_router(system_settings.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    client = TestClient(app)

    response = client.get("/api/system-settings")

    assert response.status_code == 403


def test_update_setting_changes_value(app_client):
    response = app_client.put("/api/system-settings/AI_AUTO_TRIGGER", json={"setting_value": "true"})

    assert response.status_code == 200
    assert response.json()["setting_value"] == "true"


def test_update_unknown_setting_returns_404(app_client):
    response = app_client.put("/api/system-settings/KHONG_TON_TAI", json={"setting_value": "true"})

    assert response.status_code == 404


def test_disabling_scheduler_pauses_active_continuous_campaigns(app_client, db_session):
    continuous_active = Campaign(name="C1", start_date="2026-06-01", status="ACTIVE", mode="CONTINUOUS")
    continuous_paused = Campaign(name="C2", start_date="2026-06-01", status="PAUSED", mode="CONTINUOUS")
    one_shot_active = Campaign(
        name="C3", start_date="2026-06-01", end_date="2026-06-01", status="ACTIVE", mode="ONE_SHOT"
    )
    db_session.add_all([continuous_active, continuous_paused, one_shot_active])
    db_session.commit()

    response = app_client.put("/api/system-settings/SCHEDULER_ENABLED", json={"setting_value": "false"})

    assert response.status_code == 200
    # Dùng "có chứa" thay vì so khớp tuyệt đối cả danh sách — DB dev thật có thể đã có
    # sẵn Campaign CONTINUOUS ACTIVE khác từ trước (VD do test thủ công qua UI), không
    # liên quan tới 2 campaign test này tạo riêng.
    paused_ids = response.json()["paused_campaign_ids"]
    assert str(continuous_active.campaign_id) in paused_ids
    assert str(continuous_paused.campaign_id) not in paused_ids
    assert str(one_shot_active.campaign_id) not in paused_ids

    db_session.refresh(continuous_active)
    db_session.refresh(continuous_paused)
    db_session.refresh(one_shot_active)
    assert continuous_active.status == "PAUSED"
    assert continuous_paused.status == "PAUSED"  # không đổi, đã PAUSED từ trước
    assert one_shot_active.status == "ACTIVE"  # ONE_SHOT không bị đụng tới


def test_enabling_scheduler_does_not_touch_any_campaign(app_client, db_session):
    continuous_active = Campaign(name="C1", start_date="2026-06-01", status="ACTIVE", mode="CONTINUOUS")
    db_session.add(continuous_active)
    db_session.commit()

    response = app_client.put("/api/system-settings/SCHEDULER_ENABLED", json={"setting_value": "true"})

    assert response.status_code == 200
    assert response.json()["paused_campaign_ids"] == []
    db_session.refresh(continuous_active)
    assert continuous_active.status == "ACTIVE"
