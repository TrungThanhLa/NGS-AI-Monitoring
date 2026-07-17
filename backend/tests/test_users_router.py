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
