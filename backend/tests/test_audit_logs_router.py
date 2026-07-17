import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_db
from backend.models import AuditLog, Role, User, UserRole
from backend.routers import audit_logs


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.include_router(audit_logs.router)
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


def test_list_audit_logs_requires_permission(app_client, db_session, viewer_role):
    user = _make_user_with_role(db_session, viewer_role)
    token = create_access_token(str(user.user_id))
    response = app_client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_list_audit_logs_filters_by_action_and_date(app_client, db_session, admin_role):
    admin = _make_user_with_role(db_session, admin_role)
    token = create_access_token(str(admin.user_id))

    db_session.add(AuditLog(user_id=admin.user_id, action="LOGIN", created_at=datetime.now(timezone.utc)))
    db_session.add(
        AuditLog(
            user_id=admin.user_id,
            action="CREATE",
            entity_type="user",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )
    db_session.commit()

    response = app_client.get(
        "/api/audit-logs",
        params={"action": "LOGIN", "date_from": date.today().isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()["audit_logs"]
    assert len(body) == 1
    assert body[0]["action"] == "LOGIN"
    assert body[0]["username"] == admin.username


def test_list_audit_logs_date_to_is_inclusive_of_whole_day(app_client, db_session, admin_role):
    admin = _make_user_with_role(db_session, admin_role)
    token = create_access_token(str(admin.user_id))

    db_session.add(
        AuditLog(
            user_id=admin.user_id,
            action="LATE_ON_DAY",
            created_at=datetime(2026, 6, 15, 23, 59, tzinfo=timezone.utc),
        )
    )
    db_session.add(
        AuditLog(
            user_id=admin.user_id,
            action="JUST_AFTER_MIDNIGHT_NEXT_DAY",
            created_at=datetime(2026, 6, 16, 0, 1, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = app_client.get(
        "/api/audit-logs",
        params={"date_to": "2026-06-15"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()["audit_logs"]
    assert len(body) == 1
    assert body[0]["action"] == "LATE_ON_DAY"
