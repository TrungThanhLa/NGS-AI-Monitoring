from sqlalchemy.orm import Session

from backend.auth.schemas import UserResponse
from backend.models import Permission, Role, RolePermission, User, UserRole


def serialize_user(db: Session, user: User) -> UserResponse:
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
        full_name=user.full_name,
        email=user.email,
        status=user.status,
        is_active=user.is_active,
        phone=user.phone,
        avatar_url=f"/api/users/{user.user_id}/avatar" if user.avatar_path else None,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=[r[0] for r in roles],
        permissions=[p[0] for p in permissions],
    )
