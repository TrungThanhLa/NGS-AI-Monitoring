import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models import Article, ArticleAnalysis, Job, Source
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
    job_id = None
    try:
        with patch("backend.routers.reports.run_report_job") as mock_task:
            response = app_client.post(
                "/api/reports/create",
                json={"source_ids": [str(active_source.source_id)], "date_from": "2026-06-01", "date_to": "2026-06-30"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending"
        assert "job_id" in body
        job_id = body["job_id"]

        job = db_session.get(Job, uuid.UUID(job_id))
        assert job is not None
        assert job.celery_task_id is not None

        mock_task.apply_async.assert_called_once_with(args=[job_id], task_id=job.celery_task_id)
    finally:
        if job_id is not None:
            job = db_session.get(Job, uuid.UUID(job_id))
            if job is not None:
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


def test_articles_returns_list_with_durations(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="running")
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        url="https://vtv.vn/bai-1",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Bài 1",
        status="analyzed",
        crawl_duration_seconds=1.5,
    )
    db_session.add(article)
    db_session.flush()

    db_session.add(
        ArticleAnalysis(
            article_id=article.article_id,
            job_id=job.job_id,
            topics=["A"],
            sentiment="negative",
            emotion="Fear",
            confidence=0.9,
            prompt_version=1,
            analysis_duration_seconds=67.0,
        )
    )
    db_session.commit()

    try:
        response = app_client.get(f"/api/reports/{job.job_id}/articles")

        assert response.status_code == 200
        body = response.json()["articles"]
        assert len(body) == 1
        assert body[0]["title"] == "Bài 1"
        assert body[0]["crawl_duration_seconds"] == 1.5
        assert body[0]["analysis_duration_seconds"] == 67.0
        assert body[0]["total_duration_seconds"] == 68.5
    finally:
        db_session.query(ArticleAnalysis).filter_by(article_id=article.article_id).delete()
        db_session.delete(article)
        db_session.delete(job)
        db_session.commit()


def test_articles_shows_null_durations_when_not_yet_analyzed(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="running")
    db_session.add(job)
    db_session.flush()

    article = Article(
        job_id=job.job_id,
        url="https://vtv.vn/bai-2",
        url_hash=f"hash-{uuid.uuid4()}",
        title="Bài 2",
        status="pending_analysis",
        crawl_duration_seconds=2.0,
    )
    db_session.add(article)
    db_session.commit()

    try:
        response = app_client.get(f"/api/reports/{job.job_id}/articles")

        body = response.json()["articles"]
        assert body[0]["crawl_duration_seconds"] == 2.0
        assert body[0]["analysis_duration_seconds"] is None
        assert body[0]["total_duration_seconds"] is None
    finally:
        db_session.delete(article)
        db_session.delete(job)
        db_session.commit()


def test_articles_returns_404_when_job_does_not_exist(app_client):
    response = app_client.get(f"/api/reports/{uuid.uuid4()}/articles")

    assert response.status_code == 404


def test_cancel_revokes_celery_task_and_sets_cancelled(app_client, db_session):
    job = Job(
        source_ids=[],
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        status="running",
        celery_task_id="fake-task-id",
    )
    db_session.add(job)
    db_session.commit()

    try:
        with patch("backend.routers.reports.celery_app") as mock_celery_app:
            response = app_client.post(f"/api/reports/{job.job_id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        mock_celery_app.control.revoke.assert_called_once_with("fake-task-id", terminate=True)

        db_session.refresh(job)
        assert job.status == "cancelled"
    finally:
        db_session.delete(job)
        db_session.commit()


def test_cancel_returns_400_when_job_already_completed(app_client, db_session):
    job = Job(
        source_ids=[],
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        status="completed",
        celery_task_id="fake-task-id",
    )
    db_session.add(job)
    db_session.commit()

    try:
        with patch("backend.routers.reports.celery_app") as mock_celery_app:
            response = app_client.post(f"/api/reports/{job.job_id}/cancel")

        assert response.status_code == 400
        mock_celery_app.control.revoke.assert_not_called()
    finally:
        db_session.delete(job)
        db_session.commit()


def test_cancel_returns_404_when_job_does_not_exist(app_client):
    response = app_client.post(f"/api/reports/{uuid.uuid4()}/cancel")

    assert response.status_code == 404


def test_cancel_skips_revoke_when_celery_task_id_is_none(app_client, db_session):
    job = Job(source_ids=[], date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), status="pending")
    db_session.add(job)
    db_session.commit()

    try:
        with patch("backend.routers.reports.celery_app") as mock_celery_app:
            response = app_client.post(f"/api/reports/{job.job_id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        mock_celery_app.control.revoke.assert_not_called()
    finally:
        db_session.delete(job)
        db_session.commit()
