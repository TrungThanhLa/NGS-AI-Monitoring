import uuid
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth.security import decode_token
from backend.db import get_db
from backend.models import Permission, RolePermission, User, UserRole

bearer_scheme = HTTPBearer()

_INVALID_TOKEN_EXC = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ")
_USER_UNUSABLE_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không tồn tại hoặc đã bị vô hiệu hóa"
)


def _is_user_usable(user: User | None) -> bool:
    """Cùng 3 điều kiện login() đã kiểm tra trước khi cấp token — is_active, status,
    locked_until — để không có kẽ hở cho phép token cũ còn hiệu lực khi tài khoản đã
    bị khóa/vô hiệu hóa sau khi token được cấp."""
    if user is None or not user.is_active or user.status != "ACTIVE":
        return False
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        return False
    return True


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise _INVALID_TOKEN_EXC

    if payload.get("type") != "access":
        raise _INVALID_TOKEN_EXC

    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError, AttributeError):
        raise _INVALID_TOKEN_EXC

    # Không tiết lộ lý do cụ thể (không tồn tại/bị khóa/bị vô hiệu hóa) — cùng nguyên tắc
    # chống đoán username ở login(), luôn trả về đúng 1 thông báo chung
    if not _is_user_usable(user):
        raise _USER_UNUSABLE_EXC

    return user


def require_permission(resource: str, action: str):
    code = f"{resource}.{action}"

    def checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        has_permission = (
            db.query(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .filter(UserRole.user_id == user.user_id, Permission.code == code)
            .first()
        )
        if has_permission is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền thực hiện hành động này"
            )
        return user

    return checker
