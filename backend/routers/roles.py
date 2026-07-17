from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Permission, Role, RolePermission, User, UserRole

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("")
def list_roles(db: Session = Depends(get_db), _user: User = Depends(require_permission("role", "manage"))):
    role_rows = db.query(Role).order_by(Role.code).all()
    result = []
    for role in role_rows:
        perms = (
            db.query(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
            .filter(RolePermission.role_id == role.role_id)
            .all()
        )
        user_count = db.query(UserRole).filter_by(role_id=role.role_id).count()
        result.append(
            {
                "role_id": str(role.role_id),
                "code": role.code,
                "name": role.name,
                "is_system": role.is_system,
                "permissions": sorted(p[0] for p in perms),
                "user_count": user_count,
            }
        )
    return {"roles": result}
