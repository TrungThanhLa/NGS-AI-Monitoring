# Phase 1 Auth & RBAC — Hoàn thiện phần còn thiếu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thiện Phase 1 (Auth & RBAC) — thêm `/api/users` CRUD, `/api/roles` (read-only), `audit_logs` (bảng + API + ghi log), và gắn `PermissionGuard`/route-permission thật vào UI — để có thể tạo user với role khác ADMIN và verify RBAC matrix hoạt động đúng.

**Architecture:** Backend thêm 3 router mới (`users.py`, `roles.py`, `audit_logs.py`) theo đúng pattern `require_permission()` đã có ở `sources.py`/`reports.py`; audit log ghi qua 1 helper dùng chung, gọi tại các điểm Auth/RBAC (login, đổi mật khẩu, tạo/sửa user). Frontend viết lại 3 trang mock (`Users`, `Roles`, `AuditLogs`) nối API thật, mở rộng `ProtectedRoute` để gate theo permission ở cấp route, và bọc `PermissionGuard` quanh nút hành động thật (báo cáo).

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), React + AntD + React Router (frontend). Không thêm thư viện mới.

## Global Constraints

- Không tạo permission mới ngoài 25 permission đã seed ở migration `0011`/`0013` — mọi endpoint mới dùng permission đã có sẵn (`user.manage`, `role.manage`, `audit_log.view`).
- Không tạo `POST/PUT/DELETE /api/roles` — chỉ `GET`. Không cho sửa `username`/mật khẩu người khác qua `/api/users`.
- Không ghi audit log cho Source/Report CRUD trong đợt này — chỉ ghi cho hành động Auth/RBAC (`LOGIN`, đổi mật khẩu, tạo/sửa user).
- `status` (`ACTIVE|LOCKED|INACTIVE`) là nguồn sự thật khi admin thao tác qua `/api/users`; `is_active` tự đồng bộ theo `status` (`is_active = (status == "ACTIVE")`) để không phá `_is_user_usable()` hiện có.
- Trang `System/Roles`: nút "Thêm mới" + modal tạo role (kèm checkbox chọn permission thật) **giữ lại ở mức giao diện tĩnh**, phủ overlay "Đang phát triển", **không gọi API thật** (chưa có `POST /api/roles`).
- Mọi migration mới nối tiếp từ `0014` (head hiện tại) → bắt đầu từ `0015`.

---

## Backend

### Task 1: Migration `audit_logs` + model `AuditLog`

**Files:**
- Create: `backend/alembic/versions/0015_add_audit_logs_table.py`
- Create: `backend/models/audit_log.py`
- Modify: `backend/models/__init__.py`

**Interfaces:**
- Produces: `AuditLog` model (import từ `backend.models`), bảng `audit_logs` trong DB test/dev.

- [ ] **Step 1: Viết migration**

```python
# backend/alembic/versions/0015_add_audit_logs_table.py
"""thêm bảng audit_logs — bất biến, không soft-delete (BR-SYS-01 ngoại lệ)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_logs",
        sa.Column("audit_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("old_value", JSONB),
        sa.Column("new_value", JSONB),
        sa.Column("ip_address", sa.String(100)),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("audit_logs")
```

- [ ] **Step 2: Chạy migration lên DB dev để verify không lỗi**

Run: `cd backend && alembic upgrade head`
Expected: log in ra `Running upgrade 0014 -> 0015`, không lỗi.

- [ ] **Step 3: Viết model**

```python
# backend/models/audit_log.py
import uuid

from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from backend.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100))
    entity_id = Column(UUID(as_uuid=True))
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    ip_address = Column(String(100))
    user_agent = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
```

- [ ] **Step 4: Đăng ký model trong `backend/models/__init__.py`**

```python
# backend/models/__init__.py — thêm import + export
from backend.models.article_analysis import ArticleAnalysis
from backend.models.articles import Article
from backend.models.audit_log import AuditLog
from backend.models.jobs import Job
from backend.models.permissions import Permission
from backend.models.report_history import ReportHistory
from backend.models.role_permissions import RolePermission
from backend.models.roles import Role
from backend.models.sources import Source
from backend.models.user_roles import UserRole
from backend.models.users import User

__all__ = [
    "Source",
    "Job",
    "Article",
    "ArticleAnalysis",
    "ReportHistory",
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "AuditLog",
]
```

- [ ] **Step 5: Verify import không lỗi**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -c "from backend.models import AuditLog; print(AuditLog.__tablename__)"`
Expected: in ra `audit_logs`, không traceback.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0015_add_audit_logs_table.py backend/models/audit_log.py backend/models/__init__.py
git commit -m "feat: add audit_logs table + AuditLog model"
```

---

### Task 2: `backend/audit/logger.py` — helper ghi audit log

**Files:**
- Create: `backend/audit/__init__.py` (rỗng)
- Create: `backend/audit/logger.py`
- Test: `backend/tests/test_audit_logger.py`

**Interfaces:**
- Consumes: `AuditLog` model (Task 1).
- Produces: `log_action(db, user_id, action, entity_type=None, entity_id=None, old_value=None, new_value=None, request=None)` — dùng bởi Task 6 (`auth.py`) và Task 4 (`users.py`).

- [ ] **Step 1: Viết test trước**

```python
# backend/tests/test_audit_logger.py
import uuid

from backend.audit.logger import log_action
from backend.models import AuditLog, User


def test_log_action_inserts_row(db_session):
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash", is_active=True, status="ACTIVE")
    db_session.add(user)
    db_session.flush()

    log_action(
        db_session,
        user_id=user.user_id,
        action="LOGIN",
        entity_type="user",
        entity_id=user.user_id,
    )
    db_session.commit()

    row = db_session.query(AuditLog).filter_by(user_id=user.user_id).first()
    assert row is not None
    assert row.action == "LOGIN"
    assert row.entity_type == "user"
    assert row.entity_id == user.user_id


def test_log_action_captures_ip_and_user_agent_from_request():
    class FakeRequest:
        client = type("Client", (), {"host": "10.0.0.5"})()
        headers = {"user-agent": "pytest-agent"}

    import uuid as uuid_mod
    from backend.audit.logger import _extract_request_meta

    ip, ua = _extract_request_meta(FakeRequest())
    assert ip == "10.0.0.5"
    assert ua == "pytest-agent"
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_audit_logger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.audit'`

- [ ] **Step 3: Viết implementation**

```python
# backend/audit/__init__.py
```

```python
# backend/audit/logger.py
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_audit_logger.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/audit/__init__.py backend/audit/logger.py backend/tests/test_audit_logger.py
git commit -m "feat: add audit log helper (log_action)"
```

---

### Task 3: Gộp `_serialize_user` thành hàm dùng chung + mở rộng `UserResponse`

**Files:**
- Create: `backend/auth/serializers.py`
- Modify: `backend/auth/schemas.py`
- Modify: `backend/routers/auth.py:1-46` (bỏ `_serialize_user` cục bộ, import từ `serializers.py`)
- Test: `backend/tests/test_auth_router.py` (test hiện có phải vẫn pass — không sửa)

**Interfaces:**
- Produces: `serialize_user(db: Session, user: User) -> UserResponse` — dùng bởi Task 4/5 (`users.py`) và `auth.py`.

- [ ] **Step 1: Mở rộng `UserResponse` trong `backend/auth/schemas.py`**

```python
# backend/auth/schemas.py — thay class UserResponse hiện có bằng bản mở rộng
from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    full_name: str | None = None
    email: str | None = None
    status: str
    is_active: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    roles: list[str]
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserResponse
```

- [ ] **Step 2: Tạo `backend/auth/serializers.py`**

```python
# backend/auth/serializers.py
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
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=[r[0] for r in roles],
        permissions=[p[0] for p in permissions],
    )
```

- [ ] **Step 3: Sửa `backend/routers/auth.py` dùng hàm dùng chung**

Xóa hẳn định nghĩa `_serialize_user` cục bộ (dòng 29–46 hiện tại) và import từ `serializers.py`:

```python
# backend/routers/auth.py — phần import, thêm dòng:
from backend.auth.serializers import serialize_user
```

Thay mọi lời gọi `_serialize_user(db, user)` trong file này thành `serialize_user(db, user)` (3 chỗ: `login()`, `me()`).

- [ ] **Step 4: Chạy lại test auth hiện có, xác nhận vẫn pass (không có regression)**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_auth_router.py -v`
Expected: tất cả PASS như trước (refactor thuần, không đổi hành vi API).

- [ ] **Step 5: Commit**

```bash
git add backend/auth/schemas.py backend/auth/serializers.py backend/routers/auth.py
git commit -m "refactor: extract serialize_user helper, extend UserResponse with status/is_active/created_at/last_login_at"
```

---

### Task 4: `backend/routers/users.py` — `GET /api/users`, `POST /api/users`

**Files:**
- Create: `backend/routers/users.py`
- Test: `backend/tests/test_users_router.py`

**Interfaces:**
- Consumes: `serialize_user()` (Task 3), `log_action()` (Task 2), `require_permission()` (đã có), `is_password_strong()`/`hash_password()` (đã có ở `backend/auth/security.py`).
- Produces: router `users.router` (prefix `/api/users`) — dùng bởi Task 8 (đăng ký `main.py`).

- [ ] **Step 1: Viết test cho `POST /api/users`**

```python
# backend/tests/test_users_router.py
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import users


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.include_router(users.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def admin_role(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def viewer_role(db_session):
    role = db_session.query(Role).filter_by(code="VIEWER").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def admin_user(db_session, admin_role):
    u = User(username=f"admin-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(u)
    db_session.flush()
    db_session.add(UserRole(user_id=u.user_id, role_id=admin_role.role_id))
    db_session.commit()
    return u


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(str(admin_user.user_id))


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_user_requires_role_ids(app_client, admin_token):
    response = app_client.post(
        "/api/users",
        json={"username": "newuser1", "email": "n1@x.com", "full_name": "New User", "password": "Str0ngPass!", "role_ids": []},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 400


def test_create_user_succeeds_with_valid_payload(app_client, admin_token, viewer_role):
    response = app_client.post(
        "/api/users",
        json={
            "username": "newuser2",
            "email": "n2@x.com",
            "full_name": "New User 2",
            "password": "Str0ngPass!",
            "role_ids": [str(viewer_role.role_id)],
        },
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newuser2"
    assert body["roles"] == ["VIEWER"]


def test_create_user_rejects_weak_password(app_client, admin_token, viewer_role):
    response = app_client.post(
        "/api/users",
        json={"username": "newuser3", "email": "n3@x.com", "full_name": "N3", "password": "weak", "role_ids": [str(viewer_role.role_id)]},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 422


def test_list_users_requires_user_manage_permission(app_client, db_session, viewer_role):
    other_user = User(username=f"viewer-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(other_user)
    db_session.flush()
    db_session.add(UserRole(user_id=other_user.user_id, role_id=viewer_role.role_id))
    db_session.commit()
    token = create_access_token(str(other_user.user_id))

    response = app_client.get("/api/users", headers=_auth_headers(token))
    assert response.status_code == 403


def test_list_users_returns_seeded_admin(app_client, admin_token, admin_user):
    response = app_client.get("/api/users", headers=_auth_headers(admin_token))
    assert response.status_code == 200
    usernames = [u["username"] for u in response.json()["users"]]
    assert admin_user.username in usernames
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_users_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routers.users'`

- [ ] **Step 3: Viết implementation**

```python
# backend/routers/users.py
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_users_router.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/users.py backend/tests/test_users_router.py
git commit -m "feat: add GET/POST /api/users"
```

---

### Task 5: `users.py` — `GET /api/users/{id}`, `PUT /api/users/{id}` (BR-USER-03/05)

**Files:**
- Modify: `backend/routers/users.py`
- Test: `backend/tests/test_users_router.py` (thêm test)

**Interfaces:**
- Consumes: mọi thứ Task 4 đã import.
- Produces: không có API mới cho task khác dùng — hoàn thiện router `users.py`.

- [ ] **Step 1: Viết test trước**

```python
# backend/tests/test_users_router.py — thêm cuối file

def test_get_user_detail(app_client, admin_token, admin_user):
    response = app_client.get(f"/api/users/{admin_user.user_id}", headers=_auth_headers(admin_token))
    assert response.status_code == 200
    assert response.json()["username"] == admin_user.username


def test_update_user_status_to_active_clears_lock(app_client, db_session, admin_token, viewer_role):
    locked_user = User(
        username=f"locked-{uuid.uuid4()}",
        password_hash=hash_password("Str0ngPass!"),
        is_active=False,
        status="LOCKED",
        failed_login_count=5,
    )
    db_session.add(locked_user)
    db_session.flush()
    db_session.add(UserRole(user_id=locked_user.user_id, role_id=viewer_role.role_id))
    db_session.commit()

    response = app_client.put(
        f"/api/users/{locked_user.user_id}", json={"status": "ACTIVE"}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 200
    db_session.refresh(locked_user)
    assert locked_user.status == "ACTIVE"
    assert locked_user.is_active is True
    assert locked_user.failed_login_count == 0
    assert locked_user.locked_until is None


def test_update_user_rejects_empty_role_ids(app_client, admin_token, admin_user):
    response = app_client.put(
        f"/api/users/{admin_user.user_id}", json={"role_ids": []}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 400


def test_cannot_deactivate_last_active_admin(app_client, admin_token, admin_user):
    response = app_client.put(
        f"/api/users/{admin_user.user_id}", json={"status": "INACTIVE"}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 400
    assert "ADMIN" in response.json()["detail"]


def test_cannot_remove_admin_role_from_last_active_admin(app_client, admin_token, admin_user, viewer_role):
    response = app_client.put(
        f"/api/users/{admin_user.user_id}",
        json={"role_ids": [str(viewer_role.role_id)]},
        headers=_auth_headers(admin_token),
    )
    assert response.status_code == 400


def test_can_deactivate_admin_when_another_active_admin_exists(app_client, db_session, admin_token, admin_user, admin_role):
    second_admin = User(username=f"admin2-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(second_admin)
    db_session.flush()
    db_session.add(UserRole(user_id=second_admin.user_id, role_id=admin_role.role_id))
    db_session.commit()

    response = app_client.put(
        f"/api/users/{admin_user.user_id}", json={"status": "INACTIVE"}, headers=_auth_headers(admin_token)
    )
    assert response.status_code == 200
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_users_router.py -v -k "get_user_detail or update_user or deactivate or remove_admin"`
Expected: FAIL — 404 (chưa có route `GET/PUT /api/users/{id}`)

- [ ] **Step 3: Viết implementation — thêm vào cuối `backend/routers/users.py`**

```python
# backend/routers/users.py — thêm vào cuối file

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

    current_role_codes = {r.code for r in db.query(Role).join(UserRole, UserRole.role_id == Role.role_id).filter(UserRole.user_id == target.user_id)}
    is_admin_now = "ADMIN" in current_role_codes

    removing_admin_role = False
    new_roles: list[Role] = []
    if payload.role_ids is not None:
        if not payload.role_ids:
            raise HTTPException(status_code=400, detail="Phải giữ ít nhất 1 vai trò (BR-USER-03)")
        new_roles = db.query(Role).filter(Role.role_id.in_([uuid.UUID(rid) for rid in payload.role_ids])).all()
        if len(new_roles) != len(payload.role_ids):
            raise HTTPException(status_code=400, detail="Có role_id không hợp lệ")
        removing_admin_role = is_admin_now and not any(r.code == "ADMIN" for r in new_roles)

    deactivating = is_admin_now and payload.status is not None and payload.status != "ACTIVE"

    if (removing_admin_role or deactivating) and _is_last_active_admin(db, target.user_id):
        raise HTTPException(status_code=400, detail="Không thể xóa vai trò ADMIN/vô hiệu hóa ADMIN cuối cùng của hệ thống (BR-USER-05)")

    old_value = {"full_name": target.full_name, "email": target.email, "status": target.status, "roles": list(current_role_codes)}

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.email is not None:
        target.email = payload.email
    if payload.status is not None:
        target.status = payload.status
        target.is_active = payload.status == "ACTIVE"
        if payload.status == "ACTIVE":
            target.locked_until = None
            target.failed_login_count = 0
    if payload.role_ids is not None:
        db.query(UserRole).filter_by(user_id=target.user_id).delete()
        for role in new_roles:
            db.add(UserRole(user_id=target.user_id, role_id=role.role_id))

    new_value = {"full_name": target.full_name, "email": target.email, "status": target.status, "roles": payload.role_ids}
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
```

- [ ] **Step 4: Chạy toàn bộ test file, xác nhận pass**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_users_router.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/users.py backend/tests/test_users_router.py
git commit -m "feat: add GET/PUT /api/users/{id} with BR-USER-03/05 enforcement"
```

---

### Task 6: Gọi `log_action` tại login/change-password (`auth.py`)

**Files:**
- Modify: `backend/routers/auth.py`
- Test: `backend/tests/test_auth_router.py` (thêm test)

**Interfaces:**
- Consumes: `log_action()` (Task 2).

- [ ] **Step 1: Viết test trước**

```python
# backend/tests/test_auth_router.py — thêm cuối file
from backend.models import AuditLog


def test_login_success_writes_audit_log(app_client, user, db_session):
    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    log = db_session.query(AuditLog).filter_by(user_id=user.user_id, action="LOGIN").first()
    assert log is not None


def test_change_password_writes_audit_log(app_client, user, db_session):
    from backend.auth.security import create_access_token

    token = create_access_token(str(user.user_id))
    response = app_client.post(
        "/api/auth/change-password",
        json={"current_password": "Str0ngPass!", "new_password": "NewStr0ngPass!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    log = db_session.query(AuditLog).filter_by(user_id=user.user_id, action="UPDATE", entity_type="user").first()
    assert log is not None
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_auth_router.py -v -k audit_log`
Expected: FAIL — không tìm thấy row `AuditLog` (chưa gọi `log_action`)

- [ ] **Step 3: Sửa `backend/routers/auth.py`**

Thêm import và 2 lời gọi `log_action`:

```python
# backend/routers/auth.py — thêm vào phần import
from backend.audit.logger import log_action
```

Trong `login()`, ngay trước `return TokenResponse(...)`:

```python
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    log_action(db, user_id=user.user_id, action="LOGIN", entity_type="user", entity_id=user.user_id, request=request)
    db.commit()
```

Trong `change_password()`, trước `return {"detail": "Đổi mật khẩu thành công"}`:

```python
    user.password_hash = hash_password(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)
    log_action(db, user_id=user.user_id, action="UPDATE", entity_type="user", entity_id=user.user_id, new_value={"password_changed": True})
    db.commit()
    return {"detail": "Đổi mật khẩu thành công"}
```

Lưu ý: `change_password()` hiện không nhận `Request` — thêm tham số `request: Request` vào chữ ký hàm để dùng cho `log_action` (giống `login()` đã có sẵn).

- [ ] **Step 4: Chạy lại toàn bộ test auth, xác nhận pass và không regression**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_auth_router.py -v`
Expected: tất cả PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_auth_router.py
git commit -m "feat: write audit log on login and change-password"
```

---

### Task 7: `backend/routers/roles.py` — `GET /api/roles`

**Files:**
- Create: `backend/routers/roles.py`
- Test: `backend/tests/test_roles_router.py`

**Interfaces:**
- Produces: router `roles.router` (prefix `/api/roles`) — dùng bởi Task 8.

- [ ] **Step 1: Viết test trước**

```python
# backend/tests/test_roles_router.py
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import roles


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.include_router(roles.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def admin_role(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def viewer_role(db_session):
    role = db_session.query(Role).filter_by(code="VIEWER").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


def _make_user_with_role(db_session, role):
    u = User(username=f"user-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(u)
    db_session.flush()
    db_session.add(UserRole(user_id=u.user_id, role_id=role.role_id))
    db_session.commit()
    return u


def test_list_roles_requires_role_manage_permission(app_client, db_session, viewer_role):
    user = _make_user_with_role(db_session, viewer_role)
    token = create_access_token(str(user.user_id))
    response = app_client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_list_roles_returns_5_roles_with_permissions(app_client, db_session, admin_role):
    user = _make_user_with_role(db_session, admin_role)
    token = create_access_token(str(user.user_id))
    response = app_client.get("/api/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()["roles"]
    codes = {r["code"] for r in body}
    assert codes == {"ADMIN", "MANAGER", "ANALYST", "OPERATOR", "VIEWER"}
    admin_row = next(r for r in body if r["code"] == "ADMIN")
    assert "user.manage" in admin_row["permissions"]
    assert admin_row["user_count"] >= 1
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_roles_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routers.roles'`

- [ ] **Step 3: Viết implementation**

```python
# backend/routers/roles.py
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_roles_router.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/roles.py backend/tests/test_roles_router.py
git commit -m "feat: add GET /api/roles (read-only)"
```

---

### Task 8: `backend/routers/audit_logs.py` — `GET /api/audit-logs`

**Files:**
- Create: `backend/routers/audit_logs.py`
- Test: `backend/tests/test_audit_logs_router.py`

**Interfaces:**
- Produces: router `audit_logs.router` (prefix `/api/audit-logs`) — dùng bởi Task 9.

- [ ] **Step 1: Viết test trước**

```python
# backend/tests/test_audit_logs_router.py
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_db
from backend.models import AuditLog, Role, User, UserRole
from backend.routers import audit_logs


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.include_router(audit_logs.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def admin_role(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def viewer_role(db_session):
    role = db_session.query(Role).filter_by(code="VIEWER").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


def _make_user_with_role(db_session, role):
    u = User(username=f"user-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(u)
    db_session.flush()
    db_session.add(UserRole(user_id=u.user_id, role_id=role.role_id))
    db_session.commit()
    return u


def test_list_audit_logs_requires_permission(app_client, db_session, viewer_role):
    user = _make_user_with_role(db_session, viewer_role)
    token = create_access_token(str(user.user_id))
    response = app_client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_list_audit_logs_filters_by_action_and_date(app_client, db_session, admin_role):
    admin = _make_user_with_role(db_session, admin_role)
    token = create_access_token(str(admin.user_id))

    db_session.add(AuditLog(user_id=admin.user_id, action="LOGIN", created_at=datetime.now(timezone.utc)))
    db_session.add(
        AuditLog(
            user_id=admin.user_id,
            action="CREATE",
            entity_type="user",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )
    db_session.commit()

    response = app_client.get(
        "/api/audit-logs",
        params={"action": "LOGIN", "date_from": date.today().isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()["audit_logs"]
    assert len(body) == 1
    assert body[0]["action"] == "LOGIN"
    assert body[0]["username"] == admin.username
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_audit_logs_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.routers.audit_logs'`

- [ ] **Step 3: Viết implementation**

```python
# backend/routers/audit_logs.py
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

    rows = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for row in rows:
        actor = db.get(User, row.user_id) if row.user_id else None
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
    return {"audit_logs": result}
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/test_audit_logs_router.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/audit_logs.py backend/tests/test_audit_logs_router.py
git commit -m "feat: add GET /api/audit-logs with filters"
```

---

### Task 9: Đăng ký 3 router mới vào `backend/main.py`

**Files:**
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `users.router`, `roles.router`, `audit_logs.router` (Task 4/7/8).

- [ ] **Step 1: Sửa import + đăng ký**

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from backend.db import engine
from backend.routers import audit_logs, auth, reports, roles, sources, users
from backend.routers.auth import limiter

app = FastAPI(title="NGS Monitor API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(sources.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(audit_logs.router)


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
```

- [ ] **Step 2: Verify app khởi động không lỗi**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -c "from backend.main import app; print([r.path for r in app.routes])"`
Expected: liệt kê thấy `/api/users`, `/api/roles`, `/api/audit-logs` trong danh sách path.

- [ ] **Step 3: Chạy toàn bộ test suite backend, xác nhận không regression**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring && python -m pytest backend/tests/ -v`
Expected: tất cả PASS (trừ test bị skip do thiếu seed, đã có từ trước).

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: register users/roles/audit-logs routers"
```

---

## Frontend

### Task 10: Xóa `UserForm.tsx` + 2 route orphan

**Files:**
- Delete: `frontend/src/pages/System/Users/UserForm.tsx`
- Modify: `frontend/src/App.tsx:22-23,66-67`

**Interfaces:**
- Không ảnh hưởng task khác — `UsersPage`/`UserModal` không import `UserForm`.

- [ ] **Step 1: Xóa file**

Run: `rm /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend/src/pages/System/Users/UserForm.tsx`

- [ ] **Step 2: Sửa `App.tsx` — bỏ import + 2 route**

```tsx
// frontend/src/App.tsx — xóa dòng import UserForm (dòng 23) và 2 Route (dòng 66-67)
import UsersPage from "@/pages/System/Users";
// import UserForm from "@/pages/System/Users/UserForm";  ← XÓA dòng này
import RolesPage from "@/pages/System/Roles";
```

```tsx
          <Route path="/system/users" element={<UsersPage />} />
          {/* <Route path="/system/users/new" element={<UserForm />} />        ← XÓA */}
          {/* <Route path="/system/users/:id/edit" element={<UserForm />} />   ← XÓA */}
          <Route path="/system/roles" element={<RolesPage />} />
```

- [ ] **Step 3: Verify build không lỗi (không còn import chết)**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend && npx tsc --noEmit`
Expected: không có lỗi `Cannot find module '@/pages/System/Users/UserForm'`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git rm frontend/src/pages/System/Users/UserForm.tsx
git commit -m "chore: remove orphan UserForm.tsx + unused /system/users/new,:id/edit routes"
```

---

### Task 11: Viết lại `UserModal.tsx` — gọn theo schema thật

**Files:**
- Modify: `frontend/src/pages/System/Users/UserModal.tsx` (viết lại toàn bộ)

**Interfaces:**
- Consumes: `authFetch()` (`@/lib/api`), `GET /api/roles` (Task 7), `POST /api/users`/`PUT /api/users/{id}` (Task 4/5).
- Produces: `<UserModal open editId onClose onSaved />` — `onSaved` (mới, thay `onSavedAndNew`) báo cho `UsersPage` (Task 12) load lại danh sách sau khi lưu thành công.

- [ ] **Step 1: Viết lại toàn bộ file**

```tsx
// frontend/src/pages/System/Users/UserModal.tsx
import { useEffect, useState } from 'react'
import { App, Modal, Form, Input, Select, Switch, Row, Col, Typography, Space, Button } from 'antd'
import { authFetch } from '@/lib/api'

const { Text } = Typography

const PASSWORD_RULES = [
  { required: true, message: 'Vui lòng nhập mật khẩu' },
  { min: 8, message: 'Tối thiểu 8 ký tự' },
  {
    validator: (_: unknown, value: string) => {
      if (!value) return Promise.resolve()
      if (!/[A-Z]/.test(value)) return Promise.reject('Cần ít nhất 1 chữ hoa (A-Z)')
      if (!/[a-z]/.test(value)) return Promise.reject('Cần ít nhất 1 chữ thường (a-z)')
      if (!/\d/.test(value)) return Promise.reject('Cần ít nhất 1 chữ số (0-9)')
      return Promise.resolve()
    },
  },
]

type RoleOption = { role_id: string; code: string; name: string }

type UserDetail = {
  user_id: string
  username: string
  full_name: string | null
  email: string | null
  status: string
  roles: string[]
}

interface Props {
  open: boolean
  editId?: string | null
  onClose: () => void
  onSaved: () => void
}

export default function UserModal({ open, editId, onClose, onSaved }: Props) {
  const isEdit = !!editId
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [roleOptions, setRoleOptions] = useState<RoleOption[]>([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    authFetch('/api/roles')
      .then((res) => (res.ok ? res.json() : { roles: [] }))
      .then((data) => setRoleOptions(data.roles ?? []))
      .catch(() => message.error('Không tải được danh sách vai trò'))
  }, [open])

  useEffect(() => {
    if (!open) return
    if (isEdit && editId) {
      authFetch(`/api/users/${editId}`)
        .then((res) => res.json())
        .then((u: UserDetail) => {
          form.setFieldsValue({
            full_name: u.full_name,
            username: u.username,
            email: u.email,
            status: u.status === 'ACTIVE',
            role_ids: roleOptions.filter((r) => u.roles.includes(r.code)).map((r) => r.role_id),
          })
        })
        .catch(() => message.error('Không tải được thông tin người dùng'))
    } else {
      form.resetFields()
      form.setFieldsValue({ status: true })
    }
  }, [open, editId, isEdit, form, roleOptions.length])

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)

      const payload = isEdit
        ? {
            full_name: values.full_name,
            email: values.email,
            status: values.status ? 'ACTIVE' : 'INACTIVE',
            role_ids: values.role_ids,
          }
        : {
            username: values.username,
            email: values.email,
            full_name: values.full_name,
            password: values.password,
            role_ids: values.role_ids,
          }

      const res = await authFetch(isEdit ? `/api/users/${editId}` : '/api/users', {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: 'Lưu thất bại' }))
        message.error(body.detail ?? 'Lưu thất bại')
        return
      }

      message.success(isEdit ? 'Cập nhật thành công' : 'Thêm người dùng thành công')
      onSaved()
      onClose()
    } catch {
      // validateFields() reject — lỗi đã hiện trên form, không cần message thêm
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={640}
      title={
        <Text strong style={{ fontSize: 18, color: '#0A1D55' }}>
          {isEdit ? 'Chỉnh sửa người dùng' : 'Thêm mới người dùng'}
        </Text>
      }
      destroyOnClose
      footer={
        <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
          <Button onClick={onClose}>Hủy</Button>
          <Button type="primary" loading={submitting} onClick={handleSave}>
            Lưu
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" scrollToFirstError>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="full_name" label={<>Họ và tên <Text type="danger">*</Text></>} rules={[{ required: true, message: 'Bắt buộc nhập họ tên' }]}>
              <Input placeholder="Nhập họ và tên" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="username"
              label={<>Tên đăng nhập <Text type="danger">*</Text></>}
              rules={[
                { required: true, message: 'Bắt buộc nhập tên đăng nhập' },
                { min: 4, message: 'Tối thiểu 4 ký tự' },
                { pattern: /^[a-z0-9_.]+$/, message: 'Chỉ dùng chữ thường, số, dấu chấm, gạch dưới' },
              ]}
            >
              <Input placeholder="Nhập tên đăng nhập" disabled={isEdit} />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item name="email" label={<>Email <Text type="danger">*</Text></>} rules={[{ required: true }, { type: 'email', message: 'Email không hợp lệ' }]}>
          <Input placeholder="Nhập email" />
        </Form.Item>

        {!isEdit && (
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="password" label={<>Mật khẩu <Text type="danger">*</Text></>} rules={PASSWORD_RULES}>
                <Input.Password placeholder="Nhập mật khẩu" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="confirm_password"
                label={<>Xác nhận mật khẩu <Text type="danger">*</Text></>}
                dependencies={['password']}
                rules={[
                  { required: true, message: 'Vui lòng xác nhận' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) return Promise.resolve()
                      return Promise.reject('Mật khẩu không khớp')
                    },
                  }),
                ]}
              >
                <Input.Password placeholder="Nhập lại mật khẩu" />
              </Form.Item>
            </Col>
          </Row>
        )}

        <Form.Item
          name="role_ids"
          label={<>Vai trò <Text type="danger">*</Text></>}
          rules={[{ required: true, message: 'Chọn ít nhất 1 vai trò' }]}
        >
          <Select mode="multiple" placeholder="Chọn vai trò" options={roleOptions.map((r) => ({ value: r.role_id, label: r.name }))} />
        </Form.Item>

        {isEdit && (
          <Form.Item label="Trạng thái tài khoản">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Form.Item name="status" valuePropName="checked" noStyle>
                <Switch />
              </Form.Item>
              <Text style={{ fontSize: 13 }}>Kích hoạt</Text>
            </div>
          </Form.Item>
        )}
      </Form>
    </Modal>
  )
}
```

- [ ] **Step 2: Verify type-check**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend && npx tsc --noEmit`
Expected: không lỗi type trong `UserModal.tsx` (lỗi ở `index.tsx` do đổi prop `onSaved` sẽ sửa ở Task 12 ngay sau).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/System/Users/UserModal.tsx
git commit -m "feat: rewrite UserModal to match real schema (no avatar/dept/expiry/per-user override, real roles from API)"
```

---

### Task 12: Viết lại `System/Users/index.tsx` — nối API thật

**Files:**
- Modify: `frontend/src/pages/System/Users/index.tsx` (viết lại toàn bộ)

**Interfaces:**
- Consumes: `authFetch()`, `GET /api/users` (Task 4), `PUT /api/users/{id}` (Task 5), `<UserModal onSaved />` (Task 11).

- [ ] **Step 1: Viết lại toàn bộ file**

```tsx
// frontend/src/pages/System/Users/index.tsx
import { useEffect, useState, useCallback } from 'react'
import { App, Avatar, Button, Input, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { PlusOutlined, SearchOutlined, EditOutlined, LockOutlined, UnlockOutlined, ReloadOutlined } from '@ant-design/icons'
import { authFetch } from '@/lib/api'
import UserModal from './UserModal'
import dayjs from 'dayjs'

const { Title, Text } = Typography

type UserRow = {
  user_id: string
  username: string
  full_name: string | null
  email: string | null
  status: string
  roles: string[]
  last_login_at: string | null
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  ACTIVE: { color: 'success', label: 'Đang hoạt động' },
  INACTIVE: { color: 'default', label: 'Không hoạt động' },
  LOCKED: { color: 'warning', label: 'Tạm khóa' },
}

export default function UsersPage() {
  const { message } = App.useApp()
  const [data, setData] = useState<UserRow[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)

  const loadUsers = useCallback(() => {
    setLoading(true)
    authFetch('/api/users')
      .then((res) => (res.ok ? res.json() : { users: [] }))
      .then((body) => setData(body.users ?? []))
      .catch(() => message.error('Không tải được danh sách người dùng'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadUsers() }, [loadUsers])

  const filtered = data.filter((u) =>
    (!keyword ||
      (u.full_name ?? '').toLowerCase().includes(keyword.toLowerCase()) ||
      (u.email ?? '').toLowerCase().includes(keyword.toLowerCase()) ||
      u.username.toLowerCase().includes(keyword.toLowerCase())) &&
    (!statusFilter || u.status === statusFilter),
  )

  const toggleLock = async (row: UserRow) => {
    const nextStatus = row.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    const res = await authFetch(`/api/users/${row.user_id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: nextStatus }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: 'Không thể cập nhật trạng thái' }))
      message.error(body.detail ?? 'Không thể cập nhật trạng thái')
      return
    }
    message.success('Cập nhật trạng thái thành công')
    loadUsers()
  }

  const columns = [
    {
      title: 'Họ và tên', key: 'full_name',
      render: (_: unknown, r: UserRow) => (
        <Space size={10}>
          <Avatar size={32} style={{ background: '#00859A', fontSize: 13, fontWeight: 600 }}>
            {(r.full_name ?? r.username).slice(0, 2).toUpperCase()}
          </Avatar>
          <Text strong style={{ fontSize: 13 }}>{r.full_name ?? '—'}</Text>
        </Space>
      ),
    },
    { title: 'Tên đăng nhập', dataIndex: 'username', key: 'username' },
    { title: 'Email', dataIndex: 'email', key: 'email', render: (v: string | null) => v ?? '—' },
    {
      title: 'Vai trò', key: 'roles',
      render: (_: unknown, r: UserRow) => r.roles.map((code) => <Tag key={code}>{code}</Tag>),
    },
    {
      title: 'Trạng thái', dataIndex: 'status', key: 'status', width: 140,
      render: (v: string) => {
        const cfg = STATUS_CONFIG[v] ?? STATUS_CONFIG.INACTIVE
        return <Tag color={cfg.color}>{cfg.label}</Tag>
      },
    },
    {
      title: 'Lần đăng nhập cuối', dataIndex: 'last_login_at', key: 'last_login_at', width: 155,
      render: (v: string | null) => (v ? dayjs(v).format('DD/MM/YYYY HH:mm') : <Text type="secondary">Chưa đăng nhập</Text>),
    },
    {
      title: 'Thao tác', key: 'actions', width: 80,
      render: (_: unknown, r: UserRow) => (
        <Space size={2}>
          <Tooltip title="Chỉnh sửa">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => { setEditId(r.user_id); setModalOpen(true) }} />
          </Tooltip>
          <Tooltip title={r.status === 'ACTIVE' ? 'Vô hiệu hóa' : 'Kích hoạt lại'}>
            <Button
              type="text" size="small"
              icon={r.status === 'ACTIVE' ? <LockOutlined /> : <UnlockOutlined />}
              onClick={() => toggleLock(r)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Quản lý người dùng</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>Quản lý tài khoản người dùng và phân quyền truy cập hệ thống.</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditId(null); setModalOpen(true) }}>
          Thêm mới
        </Button>
      </div>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #f0f0f0', padding: 16 }}>
        <Space style={{ marginBottom: 16 }}>
          <Input
            prefix={<SearchOutlined />}
            placeholder="Tìm kiếm theo tên, email, tên đăng nhập..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            allowClear
            style={{ width: 320 }}
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 180 }}
            options={[
              { value: '', label: 'Trạng thái: Tất cả' },
              { value: 'ACTIVE', label: 'Đang hoạt động' },
              { value: 'INACTIVE', label: 'Không hoạt động' },
            ]}
          />
          <Tooltip title="Làm mới">
            <Button icon={<ReloadOutlined />} onClick={loadUsers} />
          </Tooltip>
        </Space>

        <Table columns={columns} dataSource={filtered} rowKey="user_id" loading={loading} pagination={{ pageSize: 20 }} />
      </div>

      <UserModal
        open={modalOpen}
        editId={editId}
        onClose={() => { setModalOpen(false); setEditId(null) }}
        onSaved={loadUsers}
      />
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check toàn bộ frontend**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend && npx tsc --noEmit`
Expected: 0 lỗi liên quan tới `pages/System/Users/`.

- [ ] **Step 3: Test thật tối thiểu — chạy dev server, thao tác trên UI**

Run backend (`uvicorn backend.main:app --reload`) + frontend (`npm run dev`), đăng nhập bằng `admin`, vào `/system/users`:
- Tạo 1 user mới với role `VIEWER` → xác nhận xuất hiện trong bảng.
- Bấm nút khóa (icon Lock) → xác nhận trạng thái đổi thành "Không hoạt động".
Expected: cả 2 thao tác thành công, không lỗi console.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/System/Users/index.tsx
git commit -m "feat: wire System/Users page to real GET/POST/PUT /api/users"
```

---

### Task 13: Viết lại `System/Roles/index.tsx` — read-only + modal tĩnh có overlay

**Files:**
- Modify: `frontend/src/pages/System/Roles/index.tsx` (viết lại toàn bộ)

**Interfaces:**
- Consumes: `authFetch()`, `GET /api/roles` (Task 7). Không gọi `POST/PUT/DELETE` nào (chưa tồn tại).

- [ ] **Step 1: Viết lại toàn bộ file**

```tsx
// frontend/src/pages/System/Roles/index.tsx
import { useEffect, useState } from 'react'
import { Button, Checkbox, Form, Input, Modal, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { PlusOutlined, LockOutlined } from '@ant-design/icons'
import { authFetch } from '@/lib/api'

const { Title, Text } = Typography

type RoleRow = {
  role_id: string
  code: string
  name: string
  is_system: boolean
  permissions: string[]
  user_count: number
}

// 25 permission thật (migration 0011/0013) — dùng cho checkbox tĩnh minh họa ở modal
// "Đang phát triển", KHÔNG phải nguồn dữ liệu để tạo role thật
const ALL_PERMISSIONS = [
  'dashboard.view',
  'campaign.view', 'campaign.create', 'campaign.update', 'campaign.archive',
  'source.view', 'source.create', 'source.update', 'source.delete',
  'content.view', 'content.review',
  'alert.view', 'alert.acknowledge', 'alert.update', 'alert.close',
  'case.view', 'case.create', 'case.update', 'case.close',
  'report.view', 'report.create',
  'user.manage', 'role.manage', 'audit_log.view', 'system.configure',
]

// ─── Modal tạo role — GIAO DIỆN TĨNH, phủ overlay "Đang phát triển" (xem
// docs/superpowers/specs/2026-07-17-phase1-auth-rbac-completion-design.md
// mục "Ghi chú roadmap — Custom Role" + ROADMAP_CONTINUOUS_MONITORING.md Phase 10).
// Không gọi API thật — POST /api/roles chưa tồn tại.
function StaticRoleFormModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [form] = Form.useForm()
  return (
    <Modal open={open} onCancel={onClose} footer={null} width={640} destroyOnClose title="Thêm nhóm quyền mới">
      <div style={{ position: 'relative' }}>
        <div
          style={{
            position: 'absolute', inset: 0, zIndex: 10,
            background: 'rgba(255,255,255,0.75)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8,
            borderRadius: 8,
          }}
        >
          <LockOutlined style={{ fontSize: 28, color: '#8C95A0' }} />
          <Text strong style={{ fontSize: 16, color: '#374151' }}>Đang phát triển</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>Tính năng tạo nhóm quyền tùy chỉnh sẽ mở ở giai đoạn sau</Text>
        </div>

        <Form form={form} layout="vertical" disabled>
          <Form.Item name="code" label="Mã nhóm quyền">
            <Input placeholder="VD: CONTENT_REVIEWER" />
          </Form.Item>
          <Form.Item name="name" label="Tên nhóm quyền">
            <Input placeholder="VD: Người kiểm duyệt nội dung" />
          </Form.Item>
          <Form.Item label="Chọn quyền">
            <Checkbox.Group options={ALL_PERMISSIONS} style={{ display: 'flex', flexDirection: 'column', gap: 4 }} />
          </Form.Item>
        </Form>
      </div>
    </Modal>
  )
}

export default function RolesPage() {
  const [roles, setRoles] = useState<RoleRow[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    authFetch('/api/roles')
      .then((res) => (res.ok ? res.json() : { roles: [] }))
      .then((body) => setRoles(body.roles ?? []))
      .finally(() => setLoading(false))
  }, [])

  const columns = [
    { title: 'Mã', dataIndex: 'code', key: 'code', render: (v: string) => <Tag>{v}</Tag> },
    { title: 'Tên nhóm quyền', dataIndex: 'name', key: 'name' },
    { title: 'Số người dùng', dataIndex: 'user_count', key: 'user_count', width: 130, align: 'center' as const },
    {
      title: 'Quyền', key: 'permissions',
      render: (_: unknown, r: RoleRow) => (
        <Space size={[4, 4]} wrap>
          {r.permissions.map((p) => <Tag key={p} style={{ fontSize: 11 }}>{p}</Tag>)}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <Title level={3} style={{ margin: '0 0 4px', color: '#0A1D55' }}>Quản lý nhóm quyền</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>5 vai trò hệ thống cố định — không tạo/sửa/xóa được qua giao diện.</Text>
        </div>
        <Tooltip title="Tính năng tạo nhóm quyền tùy chỉnh đang phát triển">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Thêm mới</Button>
        </Tooltip>
      </div>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #f0f0f0', padding: 16 }}>
        <Table columns={columns} dataSource={roles} rowKey="role_id" loading={loading} pagination={false} />
      </div>

      <StaticRoleFormModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend && npx tsc --noEmit`
Expected: 0 lỗi liên quan `pages/System/Roles/`.

- [ ] **Step 3: Test thật — vào `/system/roles` bằng tài khoản admin**

Expected: thấy đúng 5 role (ADMIN/MANAGER/ANALYST/OPERATOR/VIEWER) kèm permission thật; bấm "Thêm mới" → thấy modal với overlay mờ "Đang phát triển" phủ lên, không tương tác được với form bên dưới.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/System/Roles/index.tsx
git commit -m "feat: wire System/Roles to real GET /api/roles, freeze create-role UI behind 'Đang phát triển' overlay"
```

---

### Task 14: Viết lại `System/AuditLogs/index.tsx` — nối API thật

**Files:**
- Modify: `frontend/src/pages/System/AuditLogs/index.tsx` (viết lại toàn bộ)

**Interfaces:**
- Consumes: `authFetch()`, `GET /api/audit-logs` (Task 8).

- [ ] **Step 1: Viết lại toàn bộ file**

```tsx
// frontend/src/pages/System/AuditLogs/index.tsx
import { Card, DatePicker, Select, Space, Table } from 'antd'
import { useEffect, useState } from 'react'
import PageHeader from '@/components/common/PageHeader'
import { authFetch } from '@/lib/api'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

type LogRow = {
  audit_id: string
  action: string
  entity_type: string | null
  entity_id: string | null
  username: string | null
  full_name: string | null
  ip_address: string | null
  created_at: string | null
}

const ACTION_COLORS: Record<string, string> = {
  LOGIN: '#1890FF',
  CREATE: '#52C41A',
  UPDATE: '#FAAD14',
}

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<LogRow[]>([])
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState<string | undefined>()
  const [dateRange, setDateRange] = useState<[string, string] | null>(null)

  useEffect(() => {
    const params = new URLSearchParams()
    if (action) params.set('action', action)
    if (dateRange) {
      params.set('date_from', dateRange[0])
      params.set('date_to', dateRange[1])
    }
    setLoading(true)
    authFetch(`/api/audit-logs?${params.toString()}`)
      .then((res) => (res.ok ? res.json() : { audit_logs: [] }))
      .then((body) => setLogs(body.audit_logs ?? []))
      .finally(() => setLoading(false))
  }, [action, dateRange])

  const columns = [
    { title: 'Người dùng', key: 'user', render: (_: unknown, r: LogRow) => r.full_name ?? r.username ?? '—' },
    {
      title: 'Hành động', dataIndex: 'action', key: 'action',
      render: (v: string) => <span style={{ color: ACTION_COLORS[v] ?? '#1890FF', fontWeight: 500 }}>{v}</span>,
    },
    { title: 'Đối tượng', dataIndex: 'entity_type', key: 'entity_type', render: (v: string | null) => v ?? '—' },
    { title: 'IP', dataIndex: 'ip_address', key: 'ip_address', render: (v: string | null) => v ?? '—' },
    {
      title: 'Thời gian', dataIndex: 'created_at', key: 'created_at',
      render: (v: string | null) => (v ? dayjs(v).format('DD/MM/YYYY HH:mm') : '—'),
    },
  ]

  return (
    <div>
      <PageHeader
        title="Nhật ký hoạt động"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Cấu hình hệ thống' }, { title: 'Nhật ký' }]}
      />

      <Card style={{ borderRadius: 12 }}>
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="Loại hành động"
            allowClear
            value={action}
            onChange={setAction}
            style={{ width: 160 }}
            options={[
              { value: 'LOGIN', label: 'Đăng nhập' },
              { value: 'CREATE', label: 'Tạo mới' },
              { value: 'UPDATE', label: 'Cập nhật' },
            ]}
          />
          <RangePicker
            format="DD/MM/YYYY"
            onChange={(_, dateStrings) => {
              if (!dateStrings[0] || !dateStrings[1]) { setDateRange(null); return }
              setDateRange([dayjs(dateStrings[0], 'DD/MM/YYYY').format('YYYY-MM-DD'), dayjs(dateStrings[1], 'DD/MM/YYYY').format('YYYY-MM-DD')])
            }}
          />
        </Space>

        <Table columns={columns} dataSource={logs} rowKey="audit_id" loading={loading} pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Verify type-check**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend && npx tsc --noEmit`
Expected: 0 lỗi liên quan `pages/System/AuditLogs/`.

- [ ] **Step 3: Test thật — vào `/system/audit-logs` sau khi đã login/tạo user ở Task 12**

Expected: thấy ít nhất 1 dòng `LOGIN` (từ lúc đăng nhập admin) và 1 dòng `CREATE` (từ lúc tạo user test ở Task 12).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/System/AuditLogs/index.tsx
git commit -m "feat: wire System/AuditLogs to real GET /api/audit-logs"
```

---

### Task 15: `ProtectedRoute` — thêm gate theo permission ở cấp route

**Files:**
- Modify: `frontend/src/components/common/ProtectedRoute.tsx`
- Create: `frontend/src/pages/Forbidden.tsx`

**Interfaces:**
- Produces: `<ProtectedRoute permission?: string />` — dùng bởi Task 16 (`App.tsx`).

- [ ] **Step 1: Tạo trang 403 đơn giản**

```tsx
// frontend/src/pages/Forbidden.tsx
import { Result } from "antd";

export default function ForbiddenPage() {
  return (
    <Result
      status="403"
      title="403"
      subTitle="Bạn không có quyền truy cập trang này."
    />
  );
}
```

- [ ] **Step 2: Sửa `ProtectedRoute.tsx`**

```tsx
// frontend/src/components/common/ProtectedRoute.tsx
import { Spin } from "antd";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import ForbiddenPage from "@/pages/Forbidden";

export default function ProtectedRoute({ permission }: { permission?: string }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (permission && !user.permissions.includes(permission)) {
    return <ForbiddenPage />;
  }

  return <Outlet />;
}
```

- [ ] **Step 3: Verify type-check**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend && npx tsc --noEmit`
Expected: 0 lỗi.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/common/ProtectedRoute.tsx frontend/src/pages/Forbidden.tsx
git commit -m "feat: add optional permission gate to ProtectedRoute + 403 page"
```

---

### Task 16: Áp `permission` cho route + bọc `PermissionGuard` quanh nút "Tạo báo cáo" + lọc menu Sider

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/Reports/ReportCreate.tsx:246-248`
- Modify: `frontend/src/layouts/MainLayout.tsx`

**Interfaces:**
- Consumes: `<ProtectedRoute permission />` (Task 15), `<PermissionGuard permission />` (đã có sẵn), `useAuth()` (đã có sẵn).

- [ ] **Step 1: Sửa `App.tsx` — tách các route cần gate riêng theo permission**

Route `/system/users`, `/system/roles`, `/system/audit-logs` và 3 trang mock còn lại trong "Cấu hình hệ thống" cần `<ProtectedRoute permission="...">` riêng — khác route chung hiện có (không cần permission). Cấu trúc lại phần `<Route element={<ProtectedRoute />}>` thành nhiều nhóm:

```tsx
// frontend/src/App.tsx — thay toàn bộ khối <Route element={<ProtectedRoute />}>...</Route> bằng:
      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />

          <Route path="/campaigns" element={<CampaignsPage />} />
          <Route path="/campaigns/new" element={<CampaignForm />} />
          <Route path="/campaigns/:id" element={<CampaignDetail />} />
          <Route path="/campaigns/:id/edit" element={<CampaignForm />} />

          <Route path="/sources" element={<SourcesPage />} />

          <Route path="/contents" element={<ContentsPage />} />
          <Route path="/contents/:id" element={<ContentDetail />} />

          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/alerts/:id" element={<AlertDetail />} />

          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/new" element={<CaseForm />} />
          <Route path="/cases/:id" element={<CaseDetail />} />
          <Route path="/cases/:id/edit" element={<CaseForm />} />

          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/create" element={<ReportCreate />} />

          <Route path="/jobs" element={<JobsPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute permission="user.manage" />}>
        <Route element={<MainLayout />}>
          <Route path="/system/users" element={<UsersPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute permission="role.manage" />}>
        <Route element={<MainLayout />}>
          <Route path="/system/roles" element={<RolesPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute permission="audit_log.view" />}>
        <Route element={<MainLayout />}>
          <Route path="/system/audit-logs" element={<AuditLogsPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute permission="system.configure" />}>
        <Route element={<MainLayout />}>
          <Route path="/system/master-data" element={<MasterDataPage />} />
          <Route path="/system/settings" element={<SystemSettings />} />
          <Route path="/system/connectors" element={<ConnectorsPage />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
```

(Bỏ import + route cũ của `UserForm`/`/system/users/new`/`/system/users/:id/edit` đã xóa ở Task 10 — không thêm lại.)

- [ ] **Step 2: Bọc `PermissionGuard` quanh nút "Tạo báo cáo" ở `ReportCreate.tsx`**

```tsx
// frontend/src/pages/Reports/ReportCreate.tsx — thêm import
import PermissionGuard from "@/components/common/PermissionGuard";
```

```tsx
// frontend/src/pages/Reports/ReportCreate.tsx:246-248 — bọc lại
<PermissionGuard permission="report.create">
  <Button type="primary" disabled={disabled} loading={submitting} onClick={handleSubmit}>
    Tạo báo cáo
  </Button>
</PermissionGuard>
```

- [ ] **Step 3: Lọc menu Sider theo permission trong `MainLayout.tsx`**

```tsx
// frontend/src/layouts/MainLayout.tsx — thêm hàm lọc + áp dụng trước khi truyền vào <Menu items>
const SYSTEM_SUBMENU_PERMISSION: Record<string, string> = {
  "/system/users": "user.manage",
  "/system/roles": "role.manage",
  "/system/audit-logs": "audit_log.view",
  "/system/master-data": "system.configure",
  "/system/settings": "system.configure",
  "/system/connectors": "system.configure",
}

function filterMenuByPermission(items: typeof MENU_ITEMS, permissions: string[]): typeof MENU_ITEMS {
  return items
    .map((item) => {
      if (item.children) {
        const children = filterMenuByPermission(item.children as typeof MENU_ITEMS, permissions)
        if (children.length === 0) return null
        return { ...item, children }
      }
      const required = SYSTEM_SUBMENU_PERMISSION[item.key]
      if (required && !permissions.includes(required)) return null
      return item
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)
}
```

Trong component `MainLayout`, ngay sau khai báo `const { user, logout } = useAuth();`:

```tsx
  const visibleMenuItems = filterMenuByPermission(MENU_ITEMS, user?.permissions ?? [])
```

Đổi `<Menu items={MENU_ITEMS} ...>` thành `<Menu items={visibleMenuItems} ...>`.

- [ ] **Step 4: Verify type-check**

Run: `cd /home/lathanh/Documents/Project/NGS-AI-Monitoring/frontend && npx tsc --noEmit`
Expected: 0 lỗi.

- [ ] **Step 5: Test thật — verify RBAC hoạt động đầu-cuối (mục tiêu chính của cả đợt)**

1. Login `admin` → tạo 1 user mới với role `VIEWER` (qua `/system/users`, Task 12 đã làm).
2. Đăng xuất, đăng nhập bằng user `VIEWER` vừa tạo.
3. Xác nhận: menu Sider **không hiện** mục "Người dùng & phân quyền" (`user.manage`), "Nhóm quyền" (`role.manage`), "Nhật ký hoạt động" (`audit_log.view`), và 3 mục con "Cấu hình hệ thống" khác.
4. Gõ thẳng URL `/system/users` → xác nhận hiện trang 403 (không phải màn hình trắng hay crash).
5. Vào `/reports/create` → xác nhận nút "Tạo báo cáo" **không hiện** (VIEWER không có `report.create`).

Expected: cả 5 bước đúng như mô tả — đây là bằng chứng RBAC matrix hoạt động thật với ≥2 role khác nhau, mục tiêu ban đầu của cả đợt việc.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/Reports/ReportCreate.tsx frontend/src/layouts/MainLayout.tsx
git commit -m "feat: gate System routes by permission, guard report-create button, filter Sider menu by user permissions"
```

---

## Self-Review Notes (đã tự kiểm tra trước khi giao)

- **Spec coverage:** Cả 4 mảng trong `Phạm vi` của spec (`users`, `roles`, `audit_logs`, `PermissionGuard`) đều có task tương ứng (Task 1–9 backend, Task 10–16 frontend). Mục "Ngoài phạm vi" của spec (system_settings, audit log Source/Report, đổi mật khẩu người khác) — không có task nào làm việc này, đúng như spec.
- **Điều chỉnh so với spec khi implement:** spec có nhắc bọc `PermissionGuard` quanh nút Thêm/Sửa/Xóa nguồn ở trang Sources — nhưng khi đọc code thật (`frontend/src/pages/Sources/index.tsx:47-58`), 2 nút đó đã `disabled` cứng kèm tooltip "Chưa triển khai" (CRUD nguồn thuộc Slice 6, chưa code) — không có gì để gate. Task 16 vì vậy chỉ gate nút "Tạo báo cáo" (nút thật, có tác dụng thật) — không đụng Sources.
- **Placeholder scan:** không còn "TBD"/"tương tự Task N" nào trong các step — mọi step code đều viết đủ.
- **Type consistency:** `UserResponse` (Task 3) dùng field `status`/`is_active`/`created_at`/`last_login_at` xuyên suốt Task 4/5/11/12. `RoleRow`/`LogRow` ở frontend khớp đúng field trả về từ Task 7/8.
