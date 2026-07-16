import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.auth.security import hash_password
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import auth


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.state.limiter = auth.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def admin_role(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def user(db_session, admin_role):
    u = User(username=f"user-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(u)
    db_session.flush()
    db_session.add(UserRole(user_id=u.user_id, role_id=admin_role.role_id))
    db_session.commit()
    return u


def test_login_succeeds_with_correct_password(app_client, user):
    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["username"] == user.username
    assert "ADMIN" in body["user"]["roles"]


def test_login_fails_with_wrong_password(app_client, user):
    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "WrongPass!"})
    assert response.status_code == 401


def test_login_locks_account_after_5_failed_attempts(app_client, user, db_session):
    for _ in range(5):
        app_client.post("/api/auth/login", json={"username": user.username, "password": "WrongPass!"})

    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    assert response.status_code == 423

    db_session.refresh(user)
    assert user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)


def test_refresh_returns_new_access_token(app_client, user):
    login_response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    refresh_token = login_response.json()["refresh_token"]

    response = app_client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_me_returns_current_user(app_client, user):
    login_response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    access_token = login_response.json()["access_token"]

    response = app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["username"] == user.username
