import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models import Job, Source
from backend.routers import reports


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(reports.router)
    return TestClient(app)


@pytest.fixture
def active_source(db_session):
    source = Source(name="Test Source", domain=f"test-{uuid.uuid4()}.example", group_name="Test", is_active=True)
    db_session.add(source)
    db_session.commit()
    yield source
    db_session.delete(source)
    db_session.commit()


@pytest.fixture
def inactive_source(db_session):
    source = Source(name="Inactive Source", domain=f"inactive-{uuid.uuid4()}.example", group_name="Test", is_active=False)
    db_session.add(source)
    db_session.commit()
    yield source
    db_session.delete(source)
    db_session.commit()


def test_create_returns_400_when_source_id_does_not_exist(app_client):
    response = app_client.post(
        "/api/reports/create",
        json={"source_ids": [str(uuid.uuid4())], "date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert response.status_code == 400


def test_create_returns_400_when_source_is_not_active(app_client, inactive_source):
    response = app_client.post(
        "/api/reports/create",
        json={"source_ids": [str(inactive_source.source_id)], "date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert response.status_code == 400


def test_create_returns_400_when_date_from_not_before_date_to(app_client, active_source):
    response = app_client.post(
        "/api/reports/create",
        json={"source_ids": [str(active_source.source_id)], "date_from": "2026-06-30", "date_to": "2026-06-01"},
    )
    assert response.status_code == 400


def test_create_returns_job_id_and_triggers_celery_task(app_client, active_source, db_session):
    with patch("backend.routers.reports.run_report_job") as mock_task:
        response = app_client.post(
            "/api/reports/create",
            json={"source_ids": [str(active_source.source_id)], "date_from": "2026-06-01", "date_to": "2026-06-30"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert "job_id" in body
    mock_task.delay.assert_called_once_with(body["job_id"])

    job = db_session.get(Job, uuid.UUID(body["job_id"]))
    assert job is not None
    db_session.delete(job)
    db_session.commit()


def test_status_returns_progress_counts(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="running")
    db_session.add(job)
    db_session.commit()

    response = app_client.get(f"/api/reports/{job.job_id}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["progress"] == {"crawled": 0, "analyzed": 0, "total_estimated": 0}

    db_session.delete(job)
    db_session.commit()


def test_download_returns_400_when_job_not_completed(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="running")
    db_session.add(job)
    db_session.commit()

    response = app_client.get(f"/api/reports/{job.job_id}/download")

    assert response.status_code == 400

    db_session.delete(job)
    db_session.commit()


def test_download_returns_404_when_job_does_not_exist(app_client):
    response = app_client.get(f"/api/reports/{uuid.uuid4()}/download")

    assert response.status_code == 404
