import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.auth.security import hash_password
from backend.db import get_db
from backend.models import AuditLog, Role, User, UserRole
from backend.routers import auth


@pytest.fixture
def app_client(db_session):
    # Tắt rate limit khi test — TestClient dùng chung 1 IP giả cho mọi request, nên
    # toàn bộ test trong file này (và test khác gọi /login) sẽ cùng chia sẻ 1 ngân sách
    # 10/phút thật, dễ gây 429 giả (flaky), không phải lỗi logic đang test
    auth.limiter.enabled = False
    app = FastAPI()
    app.state.limiter = auth.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        auth.limiter.enabled = True


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


def test_refresh_rejects_user_locked_after_token_issued(app_client, user, db_session):
    # Refresh token còn hạn tới 7 ngày — nếu tài khoản bị khóa SAU khi refresh token đã
    # phát hành, endpoint /refresh không được phép cấp access token mới
    login_response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    refresh_token = login_response.json()["refresh_token"]

    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
    db_session.commit()

    response = app_client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401


def test_me_returns_current_user(app_client, user):
    login_response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    access_token = login_response.json()["access_token"]

    response = app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["username"] == user.username


def _login_headers(app_client, user, password="Str0ngPass!"):
    login_response = app_client.post("/api/auth/login", json={"username": user.username, "password": password})
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def test_change_password_succeeds_with_correct_current_password(app_client, user):
    headers = _login_headers(app_client, user)
    response = app_client.post(
        "/api/auth/change-password",
        json={"current_password": "Str0ngPass!", "new_password": "NewStr0ngPass!"},
        headers=headers,
    )
    assert response.status_code == 200

    relogin = app_client.post("/api/auth/login", json={"username": user.username, "password": "NewStr0ngPass!"})
    assert relogin.status_code == 200


def test_change_password_rejects_wrong_current_password(app_client, user):
    headers = _login_headers(app_client, user)
    response = app_client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongCurrent!", "new_password": "NewStr0ngPass!"},
        headers=headers,
    )
    assert response.status_code == 400


def test_change_password_rejects_weak_new_password(app_client, user):
    headers = _login_headers(app_client, user)
    response = app_client.post(
        "/api/auth/change-password",
        json={"current_password": "Str0ngPass!", "new_password": "weak"},
        headers=headers,
    )
    assert response.status_code == 422

    # Mật khẩu cũ vẫn phải còn dùng được — request bị từ chối không được làm hỏng state
    relogin = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    assert relogin.status_code == 200


def test_change_password_requires_authentication(app_client):
    response = app_client.post(
        "/api/auth/change-password",
        json={"current_password": "x", "new_password": "NewStr0ngPass!"},
    )
    assert response.status_code in (401, 403)


def test_login_success_writes_audit_log(app_client, user, db_session):
    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    log = db_session.query(AuditLog).filter_by(user_id=user.user_id, action="LOGIN").first()
    assert log is not None


def test_change_password_writes_audit_log(app_client, user, db_session):
    from backend.auth.security import create_access_token

    token = create_access_token(str(user.user_id))
    response = app_client.post(
        "/api/auth/change-password",
        json={"current_password": "Str0ngPass!", "new_password": "NewStr0ngPass!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    log = db_session.query(AuditLog).filter_by(user_id=user.user_id, action="UPDATE", entity_type="user").first()
    assert log is not None
