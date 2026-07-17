from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import AuditLog, User

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])


@router.get("")
def list_audit_logs(
    user_id: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("audit_log", "view")),
):
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at < date_to + timedelta(days=1))

    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    # Gộp lookup User thành 1 query duy nhất thay vì N+1 (audit_logs có thể rất lớn)
    user_ids = {row.user_id for row in rows if row.user_id}
    users_by_id = {u.user_id: u for u in db.query(User).filter(User.user_id.in_(user_ids)).all()} if user_ids else {}

    result = []
    for row in rows:
        actor = users_by_id.get(row.user_id) if row.user_id else None
        result.append(
            {
                "audit_id": str(row.audit_id),
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": str(row.entity_id) if row.entity_id else None,
                "username": actor.username if actor else None,
                "full_name": actor.full_name if actor else None,
                "ip_address": row.ip_address,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return {"audit_logs": result, "total": total}
