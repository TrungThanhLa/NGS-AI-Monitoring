import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import users


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.include_router(users.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def admin_role(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def viewer_role(db_session):
    role = db_session.query(Role).filter_by(code="VIEWER").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def admin_user(db_session, admin_role):
    u = User(username=f"admin-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(u)
    db_session.flush()
    db_session.add(UserRole(user_id=u.user_id, role_id=admin_role.role_id))
    db_session.commit()
    return u


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(str(admin_user.user_id))


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_user_requires_role_ids(app_client, admin_token):
    response = app_client.post(
        "/api/users",
        json={"username": "newuser1", "email": "n1@x.com", "full_name": "New User", "password": "Str0ngPass!", "role_ids": []},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 400


def test_create_user_succeeds_with_valid_payload(app_client, admin_token, viewer_role):
    response = app_client.post(
        "/api/users",
        json={
            "username": "newuser2",
            "email": "n2@x.com",
            "full_name": "New User 2",
            "password": "Str0ngPass!",
            "role_ids": [str(viewer_role.role_id)],
        },
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newuser2"
    assert body["roles"] == ["VIEWER"]


def test_create_user_rejects_weak_password(app_client, admin_token, viewer_role):
    response = app_client.post(
        "/api/users",
        json={"username": "newuser3", "email": "n3@x.com", "full_name": "N3", "password": "weak", "role_ids": [str(viewer_role.role_id)]},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 422


def test_list_users_requires_user_manage_permission(app_client, db_session, viewer_role):
    other_user = User(username=f"viewer-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(other_user)
    db_session.flush()
    db_session.add(UserRole(user_id=other_user.user_id, role_id=viewer_role.role_id))
    db_session.commit()
    token = create_access_token(str(other_user.user_id))

    response = app_client.get("/api/users", headers=_auth_headers(token))
    assert response.status_code == 403


def test_list_users_returns_seeded_admin(app_client, admin_token, admin_user):
    response = app_client.get("/api/users", headers=_auth_headers(admin_token))
    assert response.status_code == 200
    usernames = [u["username"] for u in response.json()["users"]]
    assert admin_user.username in usernames


def test_create_user_rejects_duplicate_username(app_client, admin_token, viewer_role):
    payload = {
        "username": "dupuser",
        "email": "dup1@x.com",
        "full_name": "Dup User",
        "password": "Str0ngPass!",
        "role_ids": [str(viewer_role.role_id)],
    }
    response1 = app_client.post("/api/users", json=payload, headers=_auth_headers(admin_token))
    assert response1.status_code == 201

    payload2 = dict(payload, email="dup2@x.com")
    response2 = app_client.post("/api/users", json=payload2, headers=_auth_headers(admin_token))
    assert response2.status_code == 409


def test_create_user_requires_user_manage_permission(app_client, db_session, viewer_role):
    other_user = User(username=f"viewer-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(other_user)
    db_session.flush()
    db_session.add(UserRole(user_id=other_user.user_id, role_id=viewer_role.role_id))
    db_session.commit()
    token = create_access_token(str(other_user.user_id))

    response = app_client.post(
        "/api/users",
        json={
            "username": "newuser4",
            "email": "n4@x.com",
            "full_name": "New User 4",
            "password": "Str0ngPass!",
            "role_ids": [str(viewer_role.role_id)],
        },
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_create_user_rejects_malformed_role_id(app_client, admin_token):
    response = app_client.post(
        "/api/users",
        json={
            "username": "newuser5",
            "email": "n5@x.com",
            "full_name": "New User 5",
            "password": "Str0ngPass!",
            "role_ids": ["not-a-uuid"],
        },
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 400


def test_create_user_rejects_nonexistent_role_id(app_client, admin_token):
    response = app_client.post(
        "/api/users",
        json={
            "username": "newuser6",
            "email": "n6@x.com",
            "full_name": "New User 6",
            "password": "Str0ngPass!",
            "role_ids": [str(uuid.uuid4())],
        },
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 400


def test_get_user_detail(app_client, admin_token, admin_user):
    response = app_client.get(f"/api/users/{admin_user.user_id}", headers=_auth_headers(admin_token))
    assert response.status_code == 200
    assert response.json()["username"] == admin_user.username


def test_update_user_status_to_active_clears_lock(app_client, db_session, admin_token, viewer_role):
    locked_user = User(
        username=f"locked-{uuid.uuid4()}",
        password_hash=hash_password("Str0ngPass!"),
        is_active=False,
        status="LOCKED",
        failed_login_count=5,
    )
    db_session.add(locked_user)
    db_session.flush()
    db_session.add(UserRole(user_id=locked_user.user_id, role_id=viewer_role.role_id))
    db_session.commit()

    response = app_client.put(
        f"/api/users/{locked_user.user_id}", json={"status": "ACTIVE"}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 200
    db_session.refresh(locked_user)
    assert locked_user.status == "ACTIVE"
    assert locked_user.is_active is True
    assert locked_user.failed_login_count == 0
    assert locked_user.locked_until is None


def test_update_user_rejects_empty_role_ids(app_client, admin_token, admin_user):
    response = app_client.put(
        f"/api/users/{admin_user.user_id}", json={"role_ids": []}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 400


def _deactivate_other_admins(db_session, admin_role, keep_user_id):
    # DB dev thật đã seed sẵn 1 tài khoản "admin" ACTIVE (migration 0011) — SAVEPOINT
    # của mỗi test build trên state hiện tại nên tài khoản đó luôn xuất hiện cùng
    # admin_user của fixture. Vô hiệu hóa các ADMIN active khác (trong transaction
    # sẽ rollback cuối test) để test "ADMIN cuối cùng" đúng nghĩa chỉ còn 1 admin active.
    others = (
        db_session.query(User)
        .join(UserRole, UserRole.user_id == User.user_id)
        .filter(UserRole.role_id == admin_role.role_id, User.user_id != keep_user_id, User.status == "ACTIVE")
        .all()
    )
    for u in others:
        u.status = "INACTIVE"
        u.is_active = False
    db_session.commit()


def test_cannot_deactivate_last_active_admin(app_client, db_session, admin_token, admin_user, admin_role):
    _deactivate_other_admins(db_session, admin_role, admin_user.user_id)
    response = app_client.put(
        f"/api/users/{admin_user.user_id}", json={"status": "INACTIVE"}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 400
    assert "ADMIN" in response.json()["detail"]


def test_cannot_remove_admin_role_from_last_active_admin(app_client, db_session, admin_token, admin_user, admin_role, viewer_role):
    _deactivate_other_admins(db_session, admin_role, admin_user.user_id)
    response = app_client.put(
        f"/api/users/{admin_user.user_id}",
        json={"role_ids": [str(viewer_role.role_id)]},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 400


def test_can_deactivate_admin_when_another_active_admin_exists(app_client, db_session, admin_token, admin_user, admin_role):
    second_admin = User(username=f"admin2-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(second_admin)
    db_session.flush()
    db_session.add(UserRole(user_id=second_admin.user_id, role_id=admin_role.role_id))
    db_session.commit()

    response = app_client.put(
        f"/api/users/{admin_user.user_id}", json={"status": "INACTIVE"}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 200


def test_create_user_accepts_optional_phone(app_client, admin_token, viewer_role):
    response = app_client.post(
        "/api/users",
        json={
            "username": "userphone1",
            "email": "p1@x.com",
            "full_name": "P1",
            "phone": "0901234567",
            "password": "Str0ngPass!",
            "role_ids": [str(viewer_role.role_id)],
        },
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 201
    assert response.json()["phone"] == "0901234567"


def test_update_user_phone(app_client, admin_token, admin_user):
    response = app_client.put(
        f"/api/users/{admin_user.user_id}", json={"phone": "0909999999"}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "0909999999"


def test_upload_avatar_rejects_wrong_content_type(app_client, admin_token, admin_user, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    response = app_client.post(
        f"/api/users/{admin_user.user_id}/avatar",
        files={"file": ("test.txt", b"not an image", "text/plain")},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 422


def test_upload_avatar_rejects_oversized_file(app_client, admin_token, admin_user, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    oversized = b"0" * (2 * 1024 * 1024 + 1)
    response = app_client.post(
        f"/api/users/{admin_user.user_id}/avatar",
        files={"file": ("big.jpg", oversized, "image/jpeg")},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 422


def test_upload_and_fetch_avatar(app_client, admin_token, admin_user, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    upload_response = app_client.post(
        f"/api/users/{admin_user.user_id}/avatar",
        files={"file": ("photo.png", b"\x89PNG fake bytes", "image/png")},
        headers=_auth_headers(admin_token),
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["avatar_url"] == f"/api/users/{admin_user.user_id}/avatar"

    get_response = app_client.get(f"/api/users/{admin_user.user_id}/avatar", headers=_auth_headers(admin_token))
    assert get_response.status_code == 200
    assert get_response.content == b"\x89PNG fake bytes"


def test_get_avatar_404_when_not_uploaded(app_client, admin_token, admin_user, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    response = app_client.get(f"/api/users/{admin_user.user_id}/avatar", headers=_auth_headers(admin_token))
    assert response.status_code == 404
