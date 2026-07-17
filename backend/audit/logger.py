import uuid

from sqlalchemy.orm import Session

from backend.models import AuditLog


def _extract_request_meta(request) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = getattr(getattr(request, "client", None), "host", None)
    user_agent = request.headers.get("user-agent") if hasattr(request, "headers") else None
    return ip, user_agent


def log_action(
    db: Session,
    user_id: uuid.UUID,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    request=None,
) -> None:
    """Ghi 1 dòng audit_logs — không tự commit, dùng chung transaction với route gọi nó."""
    ip_address, user_agent = _extract_request_meta(request)
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
