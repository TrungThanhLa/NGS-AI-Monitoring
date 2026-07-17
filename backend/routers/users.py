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


# Không filter theo keyword/status/role_code ở server — FE tự lọc client-side. Đây là lựa chọn
# có chủ đích phù hợp quy mô dự án (rule 15: "<10 người dùng đồng thời"), không phải thiếu sót.
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

    try:
        role_uuids = [uuid.UUID(rid) for rid in payload.role_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Có role_id không hợp lệ")

    roles = db.query(Role).filter(Role.role_id.in_(role_uuids)).all()
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


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    status: str | None = None
    role_ids: list[str] | None = None


def _get_user_or_404(db: Session, user_id: str) -> User:
    try:
        target = db.get(User, uuid.UUID(user_id))
    except ValueError:
        target = None
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return target


def _is_last_active_admin(db: Session, user_id: uuid.UUID) -> bool:
    # Kiểm tra xem user_id có phải là ADMIN đang active DUY NHẤT còn lại của hệ thống hay không
    # (loại trừ chính user_id khi đếm các ADMIN active khác — BR-USER-05)
    admin_role = db.query(Role).filter_by(code="ADMIN").first()
    if admin_role is None:
        return False
    other_active_admins = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.user_id)
        .filter(
            UserRole.role_id == admin_role.role_id,
            User.status == "ACTIVE",
            User.is_active.is_(True),
            User.user_id != user_id,
        )
        .count()
    )
    return other_active_admins == 0


@router.get("/{user_id}")
def get_user(
    user_id: str, db: Session = Depends(get_db), _user: User = Depends(require_permission("user", "manage"))
):
    target = _get_user_or_404(db, user_id)
    return serialize_user(db, target)


@router.put("/{user_id}")
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("user", "manage")),
):
    target = _get_user_or_404(db, user_id)

    if payload.status is not None and payload.status not in {"ACTIVE", "INACTIVE", "LOCKED"}:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ")

    current_role_codes = {
        r.code for r in db.query(Role).join(UserRole, UserRole.role_id == Role.role_id).filter(UserRole.user_id == target.user_id)
    }
    is_admin_now = "ADMIN" in current_role_codes

    # Nếu payload có role_ids: bắt buộc phải giữ >=1 vai trò (BR-USER-03)
    removing_admin_role = False
    new_roles: list[Role] = []
    if payload.role_ids is not None:
        if not payload.role_ids:
            raise HTTPException(status_code=400, detail="Phải giữ ít nhất 1 vai trò (BR-USER-03)")
        try:
            role_uuids = [uuid.UUID(rid) for rid in payload.role_ids]
        except ValueError:
            raise HTTPException(status_code=400, detail="Có role_id không hợp lệ")
        new_roles = db.query(Role).filter(Role.role_id.in_(role_uuids)).all()
        if len(new_roles) != len(payload.role_ids):
            raise HTTPException(status_code=400, detail="Có role_id không hợp lệ")
        removing_admin_role = is_admin_now and not any(r.code == "ADMIN" for r in new_roles)

    deactivating = is_admin_now and payload.status is not None and payload.status != "ACTIVE"

    # BR-USER-05: không được xóa vai trò ADMIN khỏi, hoặc vô hiệu hóa, ADMIN active cuối cùng
    if (removing_admin_role or deactivating) and _is_last_active_admin(db, target.user_id):
        raise HTTPException(
            status_code=400,
            detail="Không thể xóa vai trò ADMIN/vô hiệu hóa ADMIN cuối cùng của hệ thống (BR-USER-05)",
        )

    old_value = {
        "full_name": target.full_name,
        "email": target.email,
        "status": target.status,
        "roles": list(current_role_codes),
    }

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.email is not None:
        target.email = payload.email
    if payload.status is not None:
        target.status = payload.status
        target.is_active = payload.status == "ACTIVE"
        if payload.status == "ACTIVE":
            # Chuyển về ACTIVE thì gỡ khóa tài khoản (nếu đang bị khóa do đăng nhập sai nhiều lần)
            target.locked_until = None
            target.failed_login_count = 0
    if payload.role_ids is not None:
        db.query(UserRole).filter_by(user_id=target.user_id).delete()
        for role in new_roles:
            db.add(UserRole(user_id=target.user_id, role_id=role.role_id))

    new_value = {
        "full_name": target.full_name,
        "email": target.email,
        "status": target.status,
        "roles": [r.code for r in new_roles] if payload.role_ids is not None else list(current_role_codes),
    }
    log_action(
        db,
        user_id=current_user.user_id,
        action="UPDATE",
        entity_type="user",
        entity_id=target.user_id,
        old_value=old_value,
        new_value=new_value,
        request=request,
    )
    db.commit()
    return serialize_user(db, target)
