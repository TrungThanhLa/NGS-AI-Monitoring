import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from backend.auth.dependencies import _is_user_usable, get_current_user
from backend.auth.schemas import ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse, UserResponse
from backend.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_password_strong,
    verify_password,
)
from backend.auth.serializers import serialize_user
from backend.db import get_db
from backend.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 30


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=payload.username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

    # Check khóa tạm thời TRƯỚC khi check mật khẩu — tài khoản đang bị khóa thì dù gõ
    # đúng mật khẩu cũng phải chặn, không để lộ việc mật khẩu đúng qua status code khác nhau
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(status_code=423, detail="Tài khoản đang bị khóa tạm thời, thử lại sau")

    if not user.is_active or user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= _MAX_FAILED_ATTEMPTS:
            # Reset counter về 0 ngay khi khóa — `locked_until` mới là cái thực sự chặn
            # đăng nhập tiếp theo, không cần giữ counter cao sau khi đã khóa
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
        user=serialize_user(db, user),
    )


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    try:
        user = db.get(User, uuid.UUID(decoded["sub"]))
    except (KeyError, ValueError, AttributeError):
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    # Kiểm tra cùng 3 điều kiện login() đã kiểm tra (is_active/status/locked_until) —
    # tránh kẽ hở cấp access token mới cho tài khoản vừa bị khóa/vô hiệu hóa sau khi
    # refresh token đã phát hành (refresh token sống tới 7 ngày)
    if not _is_user_usable(user):
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại hoặc đã bị vô hiệu hóa")

    return {"access_token": create_access_token(str(user.user_id))}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_user(db, user)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        # 400 (không phải 401) — token vẫn hợp lệ, chỉ sai mật khẩu hiện tại; tránh trùng
        # với 401 mà authFetch() FE hiểu là "token hết hạn" và tự động thử refresh + gọi lại
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")

    if not is_password_strong(payload.new_password):
        raise HTTPException(
            status_code=422,
            detail="Mật khẩu mới phải có tối thiểu 8 ký tự, gồm chữ hoa, chữ thường và số",
        )

    user.password_hash = hash_password(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Đổi mật khẩu thành công"}
