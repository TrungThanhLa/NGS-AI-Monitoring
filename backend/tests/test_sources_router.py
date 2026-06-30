import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models import Source
from backend.routers import sources


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(sources.router)
    return TestClient(app)


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
