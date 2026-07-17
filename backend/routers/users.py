import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.audit.logger import log_action
from backend.auth.dependencies import require_permission
from backend.auth.security import hash_password, is_password_strong
from backend.auth.serializers import serialize_user
from backend.db import get_db
from backend.models import Role, User, UserRole

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreateRequest(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    password: str
    role_ids: list[str]


@router.get("")
def list_users(db: Session = Depends(get_db), _user: User = Depends(require_permission("user", "manage"))):
    rows = db.query(User).order_by(User.username).all()
    return {"users": [serialize_user(db, u) for u in rows]}


@router.post("", status_code=201)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user", "manage")),
):
    if not payload.role_ids:
        raise HTTPException(status_code=400, detail="Phải chọn ít nhất 1 vai trò (BR-USER-03)")

    if not is_password_strong(payload.password):
        raise HTTPException(
            status_code=422, detail="Mật khẩu phải có tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và số"
        )

    if db.query(User).filter_by(username=payload.username).first() is not None:
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")

    roles = db.query(Role).filter(Role.role_id.in_([uuid.UUID(rid) for rid in payload.role_ids])).all()
    if len(roles) != len(payload.role_ids):
        raise HTTPException(status_code=400, detail="Có role_id không hợp lệ")

    new_user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        status="ACTIVE",
        is_active=True,
    )
    db.add(new_user)
    db.flush()
    for role in roles:
        db.add(UserRole(user_id=new_user.user_id, role_id=role.role_id))

    log_action(
        db,
        user_id=current_user.user_id,
        action="CREATE",
        entity_type="user",
        entity_id=new_user.user_id,
        new_value={"username": new_user.username, "role_ids": payload.role_ids},
        request=request,
    )
    db.commit()
    return serialize_user(db, new_user)
