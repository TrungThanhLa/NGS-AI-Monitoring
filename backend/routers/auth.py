import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserResponse
from backend.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from backend.db import get_db
from backend.models import Permission, Role, RolePermission, User, UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 30


def _serialize_user(db: Session, user: User) -> UserResponse:
    roles = (
        db.query(Role.code)
        .join(UserRole, UserRole.role_id == Role.role_id)
        .filter(UserRole.user_id == user.user_id)
        .all()
    )
    permissions = (
        db.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(UserRole.user_id == user.user_id)
        .distinct()
        .all()
    )
    return UserResponse(
        user_id=str(user.user_id),
        username=user.username,
        roles=[r[0] for r in roles],
        permissions=[p[0] for p in permissions],
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=payload.username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(status_code=423, detail="Tài khoản đang bị khóa tạm thời, thử lại sau")

    if not user.is_active or user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
            user.failed_login_count = 0
        db.commit()
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.user_id)),
        refresh_token=create_refresh_token(str(user.user_id)),
        user=_serialize_user(db, user),
    )


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    user = db.get(User, uuid.UUID(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại hoặc đã bị vô hiệu hóa")

    return {"access_token": create_access_token(str(user.user_id))}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize_user(db, user)
