import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Role, User, UserRole
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
