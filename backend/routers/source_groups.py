import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import SourceGroup, User

router = APIRouter(prefix="/api/source-groups", tags=["source-groups"])


@router.get("")
def list_source_groups(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("source", "view")),
):
    query = db.query(SourceGroup)
    if not include_inactive:
        query = query.filter_by(is_active=True)
    rows = query.order_by(SourceGroup.name).all()
    return {
        "source_groups": [
            {"group_id": str(g.group_id), "name": g.name, "is_active": g.is_active}
            for g in rows
        ]
    }


class SourceGroupCreateRequest(BaseModel):
    name: str


@router.post("", status_code=201)
def create_source_group(
    payload: SourceGroupCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("source", "create")),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tên nhóm nguồn không được để trống")

    group = SourceGroup(name=name)
    db.add(group)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tên nhóm nguồn đã tồn tại")

    log_action(
        db,
        user_id=current_user.user_id,
        action="CREATE",
        entity_type="source_group",
        entity_id=group.group_id,
        new_value={"name": name},
        request=request,
    )
    db.commit()

    return {"group_id": str(group.group_id), "name": group.name, "is_active": group.is_active}


class SourceGroupUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


@router.put("/{group_id}")
def update_source_group(
    group_id: str,
    payload: SourceGroupUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("source", "update")),
):
    try:
        group = db.get(SourceGroup, uuid.UUID(group_id))
    except ValueError:
        group = None
    if group is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm nguồn")

    if payload.name is not None and not payload.name.strip():
        raise HTTPException(status_code=400, detail="Tên nhóm nguồn không được để trống")

    old_value = {"name": group.name, "is_active": group.is_active}

    if payload.name is not None:
        group.name = payload.name.strip()
    if payload.is_active is not None:
        group.is_active = payload.is_active

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tên nhóm nguồn đã tồn tại")

    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="source_group",
        entity_id=group.group_id,
        old_value=old_value,
        new_value={"name": group.name, "is_active": group.is_active},
        request=request,
    )
    db.commit()

    return {"group_id": str(group.group_id), "name": group.name, "is_active": group.is_active}
