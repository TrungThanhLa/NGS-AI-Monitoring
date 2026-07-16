import uuid

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user, require_permission
from backend.auth.security import create_access_token
from backend.db import get_db
from backend.models import Permission, Role, RolePermission, User, UserRole


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session

    @app.get("/whoami")
    def whoami(user: User = Depends(get_current_user)):
        return {"username": user.username}

    @app.get("/needs-perm")
    def needs_perm(user: User = Depends(require_permission("test", "view"))):
        return {"username": user.username}

    return TestClient(app)


@pytest.fixture
def user_with_permission(db_session):
    role = Role(code=f"ROLE-{uuid.uuid4()}", name="Test Role")
    permission = Permission(code="test.view", resource="test", action="view")
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash", is_active=True)
    db_session.add_all([role, permission, user])
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    db_session.commit()
    return user


@pytest.fixture
def user_without_permission(db_session):
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash", is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_get_current_user_rejects_missing_token(app_client):
    response = app_client.get("/whoami")
    assert response.status_code == 403  # HTTPBearer trả 403 khi thiếu header Authorization


def test_get_current_user_rejects_invalid_token(app_client):
    response = app_client.get("/whoami", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_get_current_user_accepts_valid_token(app_client, user_with_permission):
    token = create_access_token(str(user_with_permission.user_id))
    response = app_client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == user_with_permission.username


def test_require_permission_allows_user_with_permission(app_client, user_with_permission):
    token = create_access_token(str(user_with_permission.user_id))
    response = app_client.get("/needs-perm", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_require_permission_rejects_user_without_permission(app_client, user_without_permission):
    token = create_access_token(str(user_without_permission.user_id))
    response = app_client.get("/needs-perm", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
