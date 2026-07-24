import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Role, SourceGroup, User, UserRole
from backend.routers import source_groups


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
    app.include_router(source_groups.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def test_list_source_groups_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(source_groups.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/source-groups")
    assert response.status_code == 403


def test_list_source_groups_includes_seeded_groups(app_client):
    # Migration 0027 seed sẵn 3 nhóm mẫu theo đúng ví dụ ở BR-SRC-01
    response = app_client.get("/api/source-groups")

    assert response.status_code == 200
    names = [g["name"] for g in response.json()["source_groups"]]
    assert "Chính phủ" in names
    assert "Bộ ngành" in names
    assert "Báo chí" in names


def test_create_and_list_source_group(app_client):
    response = app_client.post("/api/source-groups", json={"name": "Trung tâm xử lý tin giả"})

    assert response.status_code == 201
    assert response.json()["name"] == "Trung tâm xử lý tin giả"

    list_response = app_client.get("/api/source-groups")
    names = [g["name"] for g in list_response.json()["source_groups"]]
    assert "Trung tâm xử lý tin giả" in names


def test_create_source_group_requires_nonempty_name(app_client):
    response = app_client.post("/api/source-groups", json={"name": "  "})
    assert response.status_code == 400


def test_create_source_group_rejects_duplicate_name(app_client):
    app_client.post("/api/source-groups", json={"name": "Nhóm trùng"})
    response = app_client.post("/api/source-groups", json={"name": "Nhóm trùng"})
    assert response.status_code == 400


def test_list_source_groups_excludes_inactive_by_default(app_client, db_session):
    inactive = SourceGroup(name="Nhóm ngừng dùng", is_active=False)
    db_session.add(inactive)
    db_session.commit()

    response = app_client.get("/api/source-groups")
    names = [g["name"] for g in response.json()["source_groups"]]
    assert "Nhóm ngừng dùng" not in names

    response_all = app_client.get("/api/source-groups?include_inactive=true")
    names_all = [g["name"] for g in response_all.json()["source_groups"]]
    assert "Nhóm ngừng dùng" in names_all


def test_update_source_group_rename_and_deactivate(app_client, db_session):
    group = SourceGroup(name="Nhóm sẽ sửa")
    db_session.add(group)
    db_session.commit()

    response = app_client.put(f"/api/source-groups/{group.group_id}", json={"name": "Nhóm đã sửa", "is_active": False})

    assert response.status_code == 200
    assert response.json()["name"] == "Nhóm đã sửa"
    assert response.json()["is_active"] is False


def test_update_source_group_404_when_not_found(app_client):
    response = app_client.put(f"/api/source-groups/{uuid.uuid4()}", json={"is_active": False})
    assert response.status_code == 404
