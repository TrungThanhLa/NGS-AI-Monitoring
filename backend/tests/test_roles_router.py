import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import roles


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.include_router(roles.router)
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


def _make_user_with_role(db_session, role):
    u = User(username=f"user-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(u)
    db_session.flush()
    db_session.add(UserRole(user_id=u.user_id, role_id=role.role_id))
    db_session.commit()
    return u


def test_list_roles_requires_role_manage_permission(app_client, db_session, viewer_role):
    user = _make_user_with_role(db_session, viewer_role)
    token = create_access_token(str(user.user_id))
    response = app_client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_list_roles_returns_5_roles_with_permissions(app_client, db_session, admin_role):
    user = _make_user_with_role(db_session, admin_role)
    token = create_access_token(str(user.user_id))
    response = app_client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()["roles"]
    codes = {r["code"] for r in body}
    assert codes == {"ADMIN", "MANAGER", "ANALYST", "OPERATOR", "VIEWER"}
    admin_row = next(r for r in body if r["code"] == "ADMIN")
    assert "user.manage" in admin_row["permissions"]
    assert admin_row["user_count"] >= 1
