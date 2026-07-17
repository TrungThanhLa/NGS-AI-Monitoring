import uuid

from backend.audit.logger import log_action
from backend.models import AuditLog, User


def test_log_action_inserts_row(db_session):
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash", is_active=True, status="ACTIVE")
    db_session.add(user)
    db_session.flush()

    log_action(
        db_session,
        user_id=user.user_id,
        action="LOGIN",
        entity_type="user",
        entity_id=user.user_id,
    )
    db_session.commit()

    row = db_session.query(AuditLog).filter_by(user_id=user.user_id).first()
    assert row is not None
    assert row.action == "LOGIN"
    assert row.entity_type == "user"
    assert row.entity_id == user.user_id


def test_log_action_captures_ip_and_user_agent_from_request():
    class FakeRequest:
        client = type("Client", (), {"host": "10.0.0.5"})()
        headers = {"user-agent": "pytest-agent"}

    import uuid as uuid_mod
    from backend.audit.logger import _extract_request_meta

    ip, ua = _extract_request_meta(FakeRequest())
    assert ip == "10.0.0.5"
    assert ua == "pytest-agent"
