import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai.prompts.v1 import TOPIC_GROUPS
from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import topic_groups


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
    app.include_router(topic_groups.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def test_list_topic_groups_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(topic_groups.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/topic-groups")
    assert response.status_code == 403


def test_list_topic_groups_returns_exactly_the_prompt_constant(app_client):
    # Endpoint chỉ đọc — không có POST/PUT/DELETE nào tồn tại cho router này (cố ý,
    # xem comment trong topic_groups.py)
    response = app_client.get("/api/topic-groups")

    assert response.status_code == 200
    assert response.json()["topic_groups"] == TOPIC_GROUPS
