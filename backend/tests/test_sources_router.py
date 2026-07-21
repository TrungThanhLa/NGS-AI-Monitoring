import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Role, Source, User, UserRole
from backend.routers import sources


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
    app.include_router(sources.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def test_list_sources_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(sources.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/sources")
    assert response.status_code == 403  # HTTPBearer trả 403 khi thiếu header Authorization


def test_list_sources_returns_only_active_sources(app_client, db_session):
    active = Source(name="Active", domain=f"active-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    inactive = Source(name="Inactive", domain=f"inactive-{uuid.uuid4()}.example", group_name="G1", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    try:
        response = app_client.get("/api/sources")

        assert response.status_code == 200
        names = [s["name"] for s in response.json()["sources"]]
        assert "Active" in names
        assert "Inactive" not in names
    finally:
        db_session.delete(active)
        db_session.delete(inactive)
        db_session.commit()


def test_list_sources_returns_expected_fields(app_client, db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test Group", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.get("/api/sources")

        body = next(s for s in response.json()["sources"] if s["name"] == "Test")
        assert body["source_id"] == str(source.source_id)
        assert body["domain"] == source.domain
        assert body["group_name"] == "Test Group"
    finally:
        db_session.delete(source)
        db_session.commit()


def test_list_sources_includes_scheduler_fields(app_client, db_session):
    source = Source(
        name="Scheduled", domain=f"sched-{uuid.uuid4()}.example", group_name="G1",
        is_active=True, source_group="Báo chí", crawl_frequency=900, status="ACTIVE",
    )
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.get("/api/sources")
        body = next(s for s in response.json()["sources"] if s["name"] == "Scheduled")
        assert body["source_group"] == "Báo chí"
        assert body["crawl_frequency"] == 900
        assert body["status"] == "ACTIVE"
    finally:
        db_session.delete(source)
        db_session.commit()


def test_update_source_changes_allowed_fields(app_client, db_session):
    source = Source(name="Editable", domain=f"edit-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.put(
            f"/api/sources/{source.source_id}",
            json={"source_group": "Bộ ngành", "crawl_frequency": 3600, "status": "INACTIVE"},
        )

        assert response.status_code == 200
        assert response.json()["source_group"] == "Bộ ngành"
        assert response.json()["crawl_frequency"] == 3600
        assert response.json()["status"] == "INACTIVE"
    finally:
        db_session.delete(source)
        db_session.commit()


def test_update_source_rejects_error_status(app_client, db_session):
    source = Source(name="NoError", domain=f"noerror-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.put(f"/api/sources/{source.source_id}", json={"status": "ERROR"})

        assert response.status_code == 400
    finally:
        db_session.delete(source)
        db_session.commit()


def test_update_source_returns_404_for_unknown_id(app_client):
    response = app_client.put(f"/api/sources/{uuid.uuid4()}", json={"crawl_frequency": 1000})

    assert response.status_code == 404


def test_update_source_rejects_crawl_frequency_below_minimum(app_client, db_session):
    source = Source(name="TooFast", domain=f"toofast-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.put(f"/api/sources/{source.source_id}", json={"crawl_frequency": 60})

        assert response.status_code == 400
    finally:
        db_session.delete(source)
        db_session.commit()
