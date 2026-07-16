# Phase 1 — Auth & RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT-based authentication + RBAC authorization to NGS Monitor, so every existing API (`/api/sources`, `/api/reports/*`) requires a logged-in user with the correct permission, and the FE has a working `/login` flow.

**Architecture:** 5 new tables (`users, roles, permissions, user_roles, role_permissions`) seeded via Alembic migrations with the RBAC matrix from `.claude/rules/15-auth-rbac.md`. A `backend/auth/` package provides password hashing (bcrypt), JWT issue/verify (PyJWT), and two FastAPI dependencies: `get_current_user` and `require_permission(resource, action)`. Existing routers get `Depends(require_permission(...))` added to every endpoint. FE gets a `AuthContext` (React Context, no new state library) storing the access/refresh token pair in `localStorage`, a `/login` page, `ProtectedRoute`, and a `PermissionGuard` component.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (existing), PyJWT (new), bcrypt (new), slowapi (new, rate limiting), React + AntD + react-router-dom (existing, no new libs).

**Scope decision (confirmed with user 2026-07-16):** Phase 1 covers Auth **core** only — the 5 tables, JWT, `require_permission` middleware, `/login` page. It does **not** include `/api/users` / `/api/roles` CRUD or wiring the existing mock `/system/users` and `/system/roles` pages to real APIs — the only ADMIN account is seeded via migration. Full User Management CRUD is deferred to a later phase.

## Global Constraints

- `SECRET_KEY` (JWT signing) — read via `os.environ["SECRET_KEY"]`, **no fallback default in code** (BR-SEC-02, `.claude/rules/15-auth-rbac.md`).
- Access token expiry: **60 minutes**. Refresh token expiry: **7 days** (BR-USER-07).
- Password hashing: **BCrypt** (BR-USER-07).
- Login lockout: **5 failed attempts → lock 30 minutes** (BR-USER-07).
- Rate limiting required on `/api/auth/login` (Bảo mật section, rule 15).
- `require_permission(resource, action)` must apply to **every** router, including the already-existing `/api/sources` and `/api/reports/*` (rule 05, rule 15).
- Do not create permission codes beyond the RBAC matrix already defined in `.claude/rules/15-auth-rbac.md`.
- FE: no new state library (`@tanstack/react-query`/`zustand`/`msw` explicitly not used per `.claude/rules/09-frontend-ui.md`) — plain `fetch` + React state/Context only.
- Every new backend module needs a Pytest test using the existing `db_session` fixture pattern (`backend/tests/conftest.py` — per-test transaction rollback, never leaks into the dev DB).
- Comment style: short Vietnamese comments only where the WHY is non-obvious, matching existing files (`backend/routers/sources.py`, `backend/models/sources.py`).

---

## File Structure

```
backend/
├── auth/                          # NEW package
│   ├── __init__.py
│   ├── security.py                # password hash/verify, JWT create/decode
│   ├── schemas.py                 # Pydantic request/response models
│   └── dependencies.py            # get_current_user, require_permission
├── models/
│   ├── users.py                   # NEW
│   ├── roles.py                   # NEW
│   ├── permissions.py             # NEW
│   ├── user_roles.py              # NEW
│   ├── role_permissions.py        # NEW
│   └── __init__.py                # MODIFY — register new models
├── routers/
│   ├── auth.py                    # NEW — /api/auth/login, /refresh, /me
│   ├── sources.py                 # MODIFY — add require_permission
│   └── reports.py                 # MODIFY — add require_permission
├── alembic/versions/
│   ├── 0010_add_auth_rbac_tables.py        # NEW
│   ├── 0011_seed_roles_permissions.py      # NEW
│   └── 0012_seed_admin_user.py              # NEW
├── main.py                        # MODIFY — mount auth router + rate limiter
├── requirements.txt                # MODIFY — add bcrypt, pyjwt, slowapi
└── tests/
    ├── test_auth_security.py       # NEW
    ├── test_auth_dependencies.py    # NEW
    ├── test_auth_router.py          # NEW
    ├── test_sources_router.py       # MODIFY — inject authenticated user
    └── test_reports_router.py       # MODIFY — inject authenticated user

frontend/src/
├── lib/
│   ├── api.ts                     # MODIFY — add authFetch()
│   └── AuthContext.tsx            # NEW
├── components/common/
│   ├── ProtectedRoute.tsx          # NEW
│   └── PermissionGuard.tsx         # NEW
├── pages/Login/index.tsx           # NEW
├── layouts/MainLayout.tsx          # MODIFY — real user + logout
├── pages/Sources/index.tsx         # MODIFY — use authFetch
├── pages/Reports/index.tsx         # MODIFY — use authFetch
├── pages/Reports/ReportCreate.tsx  # MODIFY — use authFetch
├── App.tsx                        # MODIFY — /login route + ProtectedRoute wrap
└── main.tsx                       # MODIFY — wrap App in AuthProvider

.env.example                       # MODIFY — add SECRET_KEY, SEED_ADMIN_PASSWORD
```

---

### Task 1: Add auth dependencies to `requirements.txt`

**Files:**
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `bcrypt`, `pyjwt`, `slowapi` importable in the venv for all later tasks.

- [ ] **Step 1: Add the 3 new lines**

Append to `backend/requirements.txt`:
```
bcrypt==4.2.0
pyjwt==2.9.0
slowapi==0.1.9
```

- [ ] **Step 2: Install into the venv**

Run: `.venv/bin/python -m pip install bcrypt==4.2.0 pyjwt==2.9.0 slowapi==0.1.9`
Expected: all 3 install without error.

- [ ] **Step 3: Verify imports**

Run: `.venv/bin/python -c "import bcrypt, jwt, slowapi; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add bcrypt/pyjwt/slowapi for Phase 1 Auth & RBAC"
```

---

### Task 2: SQLAlchemy models — `users, roles, permissions, user_roles, role_permissions`

**Files:**
- Create: `backend/models/users.py`
- Create: `backend/models/roles.py`
- Create: `backend/models/permissions.py`
- Create: `backend/models/user_roles.py`
- Create: `backend/models/role_permissions.py`
- Modify: `backend/models/__init__.py`
- Test: `backend/tests/test_auth_models.py`

**Interfaces:**
- Produces: `User`, `Role`, `Permission`, `UserRole`, `RolePermission` classes, importable from `backend.models`. Columns exactly per `.claude/rules/03-database-schema.md` (Auth/RBAC section).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth_models.py
import uuid

from backend.models import Permission, Role, RolePermission, User, UserRole


def test_user_role_permission_roundtrip(db_session):
    role = Role(code=f"TESTROLE-{uuid.uuid4()}", name="Test Role")
    permission = Permission(code=f"test.view-{uuid.uuid4()}", resource="test", action="view")
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash")
    db_session.add_all([role, permission, user])
    db_session.flush()

    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    db_session.commit()

    linked_role = (
        db_session.query(Role)
        .join(UserRole, UserRole.role_id == Role.role_id)
        .filter(UserRole.user_id == user.user_id)
        .one()
    )
    assert linked_role.role_id == role.role_id

    linked_permission = (
        db_session.query(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
        .filter(RolePermission.role_id == role.role_id)
        .one()
    )
    assert linked_permission.permission_id == permission.permission_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_auth_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'Permission' from 'backend.models'`.

- [ ] **Step 3: Write the models**

```python
# backend/models/users.py
import uuid

from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), unique=True)
    full_name = Column(String(255))
    password_hash = Column(String, nullable=False)
    status = Column(String(30), server_default="ACTIVE")
    failed_login_count = Column(Integer, server_default="0")
    locked_until = Column(TIMESTAMP)
    last_login_at = Column(TIMESTAMP)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP)
    deleted_at = Column(TIMESTAMP)
```

```python
# backend/models/roles.py
import uuid

from sqlalchemy import Boolean, Column, String
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    is_system = Column(Boolean, server_default="true")
    is_active = Column(Boolean, server_default="true")
```

```python
# backend/models/permissions.py
import uuid

from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class Permission(Base):
    __tablename__ = "permissions"

    permission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(100), nullable=False, unique=True)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(Text)
```

```python
# backend/models/user_roles.py
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True)
```

```python
# backend/models/role_permissions.py
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True)
    permission_id = Column(
        UUID(as_uuid=True), ForeignKey("permissions.permission_id", ondelete="RESTRICT"), primary_key=True
    )
```

Update `backend/models/__init__.py`:
```python
from backend.models.article_analysis import ArticleAnalysis
from backend.models.articles import Article
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
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest backend/tests/test_auth_models.py -v`
Expected: still FAIL — tables don't exist in DB yet (`relation "users" does not exist`). This is expected; Task 3 creates the tables. Leave this test uncommitted-but-written; it will pass after Task 3, Step 4.

- [ ] **Step 5: Commit**

```bash
git add backend/models/users.py backend/models/roles.py backend/models/permissions.py \
        backend/models/user_roles.py backend/models/role_permissions.py \
        backend/models/__init__.py backend/tests/test_auth_models.py
git commit -m "feat: add SQLAlchemy models for users/roles/permissions (Phase 1 Auth & RBAC)"
```

---

### Task 3: Migration 0010 — create Auth/RBAC tables

**Files:**
- Create: `backend/alembic/versions/0010_add_auth_rbac_tables.py`

**Interfaces:**
- Consumes: `backend.models` (Task 2) — table shapes must match exactly.
- Produces: `users, roles, permissions, user_roles, role_permissions` tables in the DB, so Task 2's test can pass.

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/0010_add_auth_rbac_tables.py
"""thêm bảng users/roles/permissions/user_roles/role_permissions cho Phase 1 Auth & RBAC

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("full_name", sa.String(255)),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("status", sa.String(30), server_default="ACTIVE"),
        sa.Column("failed_login_count", sa.Integer, server_default="0"),
        sa.Column("locked_until", sa.TIMESTAMP),
        sa.Column("last_login_at", sa.TIMESTAMP),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP),
        sa.Column("deleted_at", sa.TIMESTAMP),
    )

    op.create_table(
        "roles",
        sa.Column("role_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_system", sa.Boolean, server_default="true"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )

    op.create_table(
        "permissions",
        sa.Column(
            "permission_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column(
            "permission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("permissions.permission_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
```

- [ ] **Step 2: Run the migration**

Run: `.venv/bin/python -m alembic -c backend/alembic.ini upgrade head`
Expected: `Running upgrade 0009 -> 0010, thêm bảng users/roles/permissions...` with no errors.

- [ ] **Step 3: Verify tables exist**

Run: `.venv/bin/python -c "
from backend.db import engine
from sqlalchemy import inspect
insp = inspect(engine)
for t in ('users','roles','permissions','user_roles','role_permissions'):
    assert t in insp.get_table_names(), t
print('ok')
"`
Expected: prints `ok`.

- [ ] **Step 4: Run Task 2's test — now it should pass**

Run: `.venv/bin/python -m pytest backend/tests/test_auth_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0010_add_auth_rbac_tables.py
git commit -m "feat: migration 0010 — create users/roles/permissions/user_roles/role_permissions tables"
```

---

### Task 4: Migration 0011 — seed 5 roles + RBAC matrix permissions + role_permissions

**Files:**
- Create: `backend/alembic/versions/0011_seed_roles_permissions.py`

**Interfaces:**
- Produces: 5 rows in `roles` (codes `ADMIN, MANAGER, ANALYST, OPERATOR, VIEWER`), 24 rows in `permissions` (exact codes from `.claude/rules/15-auth-rbac.md` RBAC matrix), and the full `role_permissions` mapping (Y cells in that matrix).

- [ ] **Step 1: Write the migration**

```python
# backend/alembic/versions/0011_seed_roles_permissions.py
"""seed 5 role hệ thống + toàn bộ permission theo RBAC matrix rút gọn ở
.claude/rules/15-auth-rbac.md — is_system=true, không cho xóa qua UI

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-16
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# Namespace cố định — sinh UUID5 deterministic từ code, để upgrade/downgrade
# không cần lưu trạng thái ngoài và chạy lại (ON CONFLICT DO NOTHING) an toàn.
_NAMESPACE = uuid.UUID("6fbb1d60-7b1a-4e9a-9c1a-000000000000")

ROLES = [
    ("ADMIN", "Quản trị viên"),
    ("MANAGER", "Quản lý"),
    ("ANALYST", "Chuyên viên phân tích"),
    ("OPERATOR", "Vận hành viên"),
    ("VIEWER", "Người xem"),
]

# (code, resource, action) — đúng theo bảng RBAC matrix rút gọn, rule 15
PERMISSIONS = [
    ("dashboard.view", "dashboard", "view"),
    ("campaign.view", "campaign", "view"),
    ("campaign.create", "campaign", "create"),
    ("campaign.update", "campaign", "update"),
    ("campaign.archive", "campaign", "archive"),
    ("source.view", "source", "view"),
    ("source.create", "source", "create"),
    ("source.update", "source", "update"),
    ("source.delete", "source", "delete"),
    ("content.view", "content", "view"),
    ("content.review", "content", "review"),
    ("alert.view", "alert", "view"),
    ("alert.acknowledge", "alert", "acknowledge"),
    ("alert.update", "alert", "update"),
    ("alert.close", "alert", "close"),
    ("case.view", "case", "view"),
    ("case.create", "case", "create"),
    ("case.update", "case", "update"),
    ("case.close", "case", "close"),
    ("report.view", "report", "view"),
    ("report.create", "report", "create"),
    ("user.manage", "user", "manage"),
    ("role.manage", "role", "manage"),
    ("audit_log.view", "audit_log", "view"),
    ("system.configure", "system", "configure"),
]

# role_code -> set(permission_code) — copy trực tiếp cột Y của bảng RBAC matrix
ROLE_PERMISSIONS = {
    "ADMIN": {code for code, _, _ in PERMISSIONS},  # ADMIN luôn Y toàn bộ
    "MANAGER": {
        "dashboard.view", "campaign.view", "campaign.create", "campaign.update", "campaign.archive",
        "source.view", "content.view", "content.review", "alert.view", "alert.acknowledge", "alert.update",
        "alert.close", "case.view", "case.create", "case.update", "report.view", "report.create",
    },
    "ANALYST": {
        "dashboard.view", "campaign.view", "source.view", "content.view", "content.review",
        "alert.view", "alert.acknowledge", "alert.update", "case.view", "case.create", "case.update",
        "report.view", "report.create",
    },
    "OPERATOR": {
        "dashboard.view", "campaign.view", "source.view", "source.create", "source.update", "content.view",
        "alert.view",
    },
    "VIEWER": {
        "dashboard.view", "campaign.view", "source.view", "content.view", "alert.view", "case.view", "report.view",
    },
}


def _role_id(code: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"role:{code}"))


def _permission_id(code: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"permission:{code}"))


def upgrade():
    conn = op.get_bind()

    for code, name in ROLES:
        conn.execute(
            sa.text(
                "INSERT INTO roles (role_id, code, name, is_system, is_active) "
                "VALUES (:role_id, :code, :name, true, true) ON CONFLICT (code) DO NOTHING"
            ),
            {"role_id": _role_id(code), "code": code, "name": name},
        )

    for code, resource, action in PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (permission_id, code, resource, action) "
                "VALUES (:permission_id, :code, :resource, :action) ON CONFLICT (code) DO NOTHING"
            ),
            {"permission_id": _permission_id(code), "code": code, "resource": resource, "action": action},
        )

    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        for permission_code in permission_codes:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :permission_id) ON CONFLICT DO NOTHING"
                ),
                {"role_id": _role_id(role_code), "permission_id": _permission_id(permission_code)},
            )


def downgrade():
    conn = op.get_bind()
    role_ids = [_role_id(code) for code, _ in ROLES]
    permission_ids = [_permission_id(code) for code, _, _ in PERMISSIONS]
    conn.execute(
        sa.text("DELETE FROM role_permissions WHERE role_id = ANY(:role_ids)"),
        {"role_ids": role_ids},
    )
    conn.execute(sa.text("DELETE FROM permissions WHERE permission_id = ANY(:ids)"), {"ids": permission_ids})
    conn.execute(sa.text("DELETE FROM roles WHERE role_id = ANY(:ids)"), {"ids": role_ids})
```

- [ ] **Step 2: Run the migration**

Run: `.venv/bin/python -m alembic -c backend/alembic.ini upgrade head`
Expected: `Running upgrade 0010 -> 0011, seed 5 role hệ thống...` no errors.

- [ ] **Step 3: Verify seed data**

Run: `.venv/bin/python -c "
from backend.db import SessionLocal
from backend.models import Role, Permission, RolePermission
db = SessionLocal()
assert db.query(Role).count() == 5
assert db.query(Permission).count() == 24
admin = db.query(Role).filter_by(code='ADMIN').one()
assert db.query(RolePermission).filter_by(role_id=admin.role_id).count() == 24
print('ok')
"`
Expected: prints `ok`.

- [ ] **Step 4: Re-run upgrade to confirm idempotency**

Run: `.venv/bin/python -m alembic -c backend/alembic.ini upgrade head` (should be a no-op since already at head) then run Step 3's script again — same counts, no duplicate-key errors.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0011_seed_roles_permissions.py
git commit -m "feat: migration 0011 — seed 5 roles + RBAC matrix permissions"
```

---

### Task 5: Migration 0012 — seed 1 ADMIN user

**Files:**
- Create: `backend/alembic/versions/0012_seed_admin_user.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `bcrypt` (Task 1), `roles`/`user_roles` tables (Tasks 3–4).
- Produces: exactly one row in `users` with username `admin`, assigned the `ADMIN` role — the only way to log in until a later phase adds self-service user management.

- [ ] **Step 1: Add env var placeholder**

Add to `.env.example` (near the other config, before `VITE_API_BASE_URL`):
```env
# Bắt buộc set trước khi chạy `alembic upgrade head` lần đầu — migration 0012 seed
# user ADMIN dùng mật khẩu này (hash bằng BCrypt, không lưu plaintext). Không có giá
# trị mặc định trong code (BR-SEC-02) — đổi mật khẩu qua DB trực tiếp sau khi có
# User Management UI (phase sau).
SEED_ADMIN_PASSWORD=

# Ký JWT access/refresh token — sinh bằng `openssl rand -hex 32`, không có giá trị
# mặc định trong code (BR-SEC-02).
SECRET_KEY=
```

- [ ] **Step 2: Write the migration**

```python
# backend/alembic/versions/0012_seed_admin_user.py
"""seed 1 user ADMIN duy nhất — mật khẩu đọc từ env SEED_ADMIN_PASSWORD (bắt buộc,
không có giá trị mặc định trong code, BR-SEC-02). Đây là cách duy nhất để có tài
khoản đăng nhập cho tới khi có User Management CRUD (phase sau) — Phase 1 chỉ làm
hạ tầng Auth core, không làm CRUD user (quyết định 2026-07-16).

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-16
"""

import os
import uuid

import bcrypt
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_ADMIN_ROLE_ID = uuid.uuid5(uuid.UUID("6fbb1d60-7b1a-4e9a-9c1a-000000000000"), "role:ADMIN")


def upgrade():
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD chưa được set trong .env — bắt buộc phải có để seed "
            "user ADMIN đầu tiên (migration 0012), không có giá trị mặc định trong code"
        )

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = op.get_bind()

    result = conn.execute(
        sa.text(
            "INSERT INTO users (username, password_hash, status, is_active) "
            "VALUES ('admin', :password_hash, 'ACTIVE', true) "
            "ON CONFLICT (username) DO NOTHING RETURNING user_id"
        ),
        {"password_hash": password_hash},
    )
    row = result.fetchone()
    if row is None:
        return  # user 'admin' đã tồn tại (rerun migration) — không tạo lại, không đổi role gán

    user_id = row[0]
    conn.execute(
        sa.text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
        {"user_id": user_id, "role_id": str(_ADMIN_ROLE_ID)},
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM user_roles WHERE user_id = (SELECT user_id FROM users WHERE username = 'admin')"
        )
    )
    conn.execute(sa.text("DELETE FROM users WHERE username = 'admin'"))
```

- [ ] **Step 3: Run the migration**

Run: `SEED_ADMIN_PASSWORD='Admin@12345' .venv/bin/python -m alembic -c backend/alembic.ini upgrade head`
Expected: no errors. If `SEED_ADMIN_PASSWORD` is unset, expect `RuntimeError: SEED_ADMIN_PASSWORD chưa được set...` — verify this failure path too:
Run: `unset SEED_ADMIN_PASSWORD; .venv/bin/python -m alembic -c backend/alembic.ini upgrade head` (only if 0012 hasn't been applied yet in a scratch DB — otherwise skip this negative check, it's already at head)

- [ ] **Step 4: Verify seed user**

Run: `.venv/bin/python -c "
from backend.db import SessionLocal
from backend.models import User, UserRole, Role
db = SessionLocal()
user = db.query(User).filter_by(username='admin').one()
role = db.query(Role).join(UserRole, UserRole.role_id == Role.role_id).filter(UserRole.user_id == user.user_id).one()
assert role.code == 'ADMIN'
print('ok')
"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0012_seed_admin_user.py .env.example
git commit -m "feat: migration 0012 — seed ADMIN user from SEED_ADMIN_PASSWORD env var"
```

---

### Task 6: `backend/auth/security.py` — password hashing + JWT

**Files:**
- Create: `backend/auth/__init__.py` (empty)
- Create: `backend/auth/security.py`
- Test: `backend/tests/test_auth_security.py`

**Interfaces:**
- Consumes: `SECRET_KEY` env var (Task 5, Step 1 already added the `.env.example` placeholder — export it in the shell for tests too).
- Produces: `hash_password(plain) -> str`, `verify_password(plain, hash) -> bool`, `create_access_token(user_id: str) -> str`, `create_refresh_token(user_id: str) -> str`, `decode_token(token: str) -> dict` — used by Tasks 8–9.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth_security.py
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.auth.security import (
    SECRET_KEY,
    JWT_ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_roundtrip():
    hashed = hash_password("Str0ngPass!")
    assert hashed != "Str0ngPass!"
    assert verify_password("Str0ngPass!", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("Str0ngPass!")
    assert verify_password("WrongPass!", hashed) is False


def test_create_access_token_has_type_access():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_create_refresh_token_has_type_refresh():
    token = create_refresh_token("user-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_decode_token_rejects_expired_token():
    expired_payload = {
        "sub": "user-123",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_auth_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.auth'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/auth/__init__.py
```

```python
# backend/auth/security.py
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

SECRET_KEY = os.environ["SECRET_KEY"]
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_auth_security.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth/__init__.py backend/auth/security.py backend/tests/test_auth_security.py
git commit -m "feat: backend/auth/security.py — bcrypt password hashing + JWT access/refresh tokens"
```

---

### Task 7: `backend/auth/schemas.py` — Pydantic request/response models

**Files:**
- Create: `backend/auth/schemas.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `LoginRequest`, `RefreshRequest`, `UserResponse`, `TokenResponse` — used by Task 9's router.

- [ ] **Step 1: Write the schemas (no test — pure Pydantic models, exercised via Task 9's router tests)**

```python
# backend/auth/schemas.py
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    roles: list[str]
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserResponse
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `.venv/bin/python -c "from backend.auth.schemas import LoginRequest, RefreshRequest, UserResponse, TokenResponse; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/auth/schemas.py
git commit -m "feat: backend/auth/schemas.py — Pydantic models for login/refresh/me"
```

---

### Task 8: `backend/auth/dependencies.py` — `get_current_user` + `require_permission`

**Files:**
- Create: `backend/auth/dependencies.py`
- Test: `backend/tests/test_auth_dependencies.py`

**Interfaces:**
- Consumes: `decode_token` (Task 6), `User/Role/Permission/UserRole/RolePermission` models (Task 2), `get_db` (`backend/db.py`, existing).
- Produces: `get_current_user(credentials, db) -> User` and `require_permission(resource: str, action: str) -> Callable` — a FastAPI dependency factory. Used by Task 9 and Tasks 11–12.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth_dependencies.py
import uuid

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user, require_permission
from backend.auth.security import create_access_token
from backend.db import get_db
from backend.models import Permission, Role, RolePermission, User, UserRole


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session

    @app.get("/whoami")
    def whoami(user: User = Depends(get_current_user)):
        return {"username": user.username}

    @app.get("/needs-perm")
    def needs_perm(user: User = Depends(require_permission("test", "view"))):
        return {"username": user.username}

    return TestClient(app)


@pytest.fixture
def user_with_permission(db_session):
    role = Role(code=f"ROLE-{uuid.uuid4()}", name="Test Role")
    permission = Permission(code="test.view", resource="test", action="view")
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash", is_active=True)
    db_session.add_all([role, permission, user])
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    db_session.commit()
    return user


@pytest.fixture
def user_without_permission(db_session):
    user = User(username=f"user-{uuid.uuid4()}", password_hash="hash", is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def test_get_current_user_rejects_missing_token(app_client):
    response = app_client.get("/whoami")
    assert response.status_code == 403  # HTTPBearer trả 403 khi thiếu header Authorization


def test_get_current_user_rejects_invalid_token(app_client):
    response = app_client.get("/whoami", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_get_current_user_accepts_valid_token(app_client, user_with_permission):
    token = create_access_token(str(user_with_permission.user_id))
    response = app_client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == user_with_permission.username


def test_require_permission_allows_user_with_permission(app_client, user_with_permission):
    token = create_access_token(str(user_with_permission.user_id))
    response = app_client.get("/needs-perm", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_require_permission_rejects_user_without_permission(app_client, user_without_permission):
    token = create_access_token(str(user_without_permission.user_id))
    response = app_client.get("/needs-perm", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_auth_dependencies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.auth.dependencies'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/auth/dependencies.py
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.auth.security import decode_token
from backend.db import get_db
from backend.models import Permission, RolePermission, User, UserRole

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ")

    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không tồn tại hoặc đã bị vô hiệu hóa"
        )

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_auth_dependencies.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/auth/dependencies.py backend/tests/test_auth_dependencies.py
git commit -m "feat: backend/auth/dependencies.py — get_current_user + require_permission FastAPI dependencies"
```

---

### Task 9: `backend/routers/auth.py` — login / refresh / me + rate limiting

**Files:**
- Create: `backend/routers/auth.py`
- Test: `backend/tests/test_auth_router.py`

**Interfaces:**
- Consumes: `hash_password/verify_password/create_access_token/create_refresh_token/decode_token` (Task 6), `LoginRequest/RefreshRequest/TokenResponse/UserResponse` (Task 7), `get_current_user` (Task 8).
- Produces: `router` (FastAPI `APIRouter`), `limiter` (slowapi `Limiter`) — both consumed by Task 10 (`main.py`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_auth_router.py
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.auth.security import hash_password
from backend.db import get_db
from backend.models import Role, User, UserRole
from backend.routers import auth


@pytest.fixture
def app_client(db_session):
    app = FastAPI()
    app.state.limiter = auth.limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def admin_role(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    return role


@pytest.fixture
def user(db_session, admin_role):
    u = User(username=f"user-{uuid.uuid4()}", password_hash=hash_password("Str0ngPass!"), is_active=True, status="ACTIVE")
    db_session.add(u)
    db_session.flush()
    db_session.add(UserRole(user_id=u.user_id, role_id=admin_role.role_id))
    db_session.commit()
    return u


def test_login_succeeds_with_correct_password(app_client, user):
    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["username"] == user.username
    assert "ADMIN" in body["user"]["roles"]


def test_login_fails_with_wrong_password(app_client, user):
    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "WrongPass!"})
    assert response.status_code == 401


def test_login_locks_account_after_5_failed_attempts(app_client, user, db_session):
    for _ in range(5):
        app_client.post("/api/auth/login", json={"username": user.username, "password": "WrongPass!"})

    response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    assert response.status_code == 423

    db_session.refresh(user)
    assert user.locked_until > datetime.now(timezone.utc)


def test_refresh_returns_new_access_token(app_client, user):
    login_response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    refresh_token = login_response.json()["refresh_token"]

    response = app_client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_me_returns_current_user(app_client, user):
    login_response = app_client.post("/api/auth/login", json={"username": user.username, "password": "Str0ngPass!"})
    access_token = login_response.json()["access_token"]

    response = app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["username"] == user.username
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_auth_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.routers.auth'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/routers/auth.py
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
```

Note: `locked_until` is stored naive (no tz) by Postgres `TIMESTAMP` (not `TIMESTAMPTZ`) — the `.replace(tzinfo=timezone.utc)` guard in `login()` assumes the DB always stores UTC, consistent with `func.now()` / `now()` used elsewhere in this schema (rule 03 uses plain `TIMESTAMP` everywhere, not `TIMESTAMPTZ`).

- [ ] **Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_auth_router.py -v`
Expected: 5 passed. (If skipped with "Chưa chạy migration 0011" — run `alembic upgrade head` on the test DB first.)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/auth.py backend/tests/test_auth_router.py
git commit -m "feat: POST /api/auth/login, /refresh, GET /api/auth/me with lockout + rate limiting"
```

---

### Task 10: Wire auth router + rate limiter into `main.py`

**Files:**
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `auth.router`, `auth.limiter` (Task 9).

- [ ] **Step 1: Update `main.py`**

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from backend.db import engine
from backend.routers import auth, reports, sources
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


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
```

- [ ] **Step 2: Start the app and hit `/api/auth/login` manually**

Run (in a terminal with `SECRET_KEY` and `DATABASE_URL` exported):
```bash
SECRET_KEY=test-secret .venv/bin/python -m uvicorn backend.main:app --port 8001 &
sleep 1
curl -s -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@12345"}'
kill %1
```
Expected: JSON with `access_token`, `refresh_token`, `user.roles == ["ADMIN"]` (assuming Task 5 was seeded with password `Admin@12345`).

- [ ] **Step 3: Run full backend test suite to check nothing else broke**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests -v`
Expected: all pass except `test_sources_router.py`/`test_reports_router.py`, which will start failing at Task 11–12 once permission checks are added — at this point (before Task 11–12) they should still pass since those routers are unmodified.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: mount /api/auth router + slowapi rate limiter in main.py"
```

---

### Task 11: Apply `require_permission` to `sources.py`

**Files:**
- Modify: `backend/routers/sources.py`
- Modify: `backend/tests/test_sources_router.py`

**Interfaces:**
- Consumes: `require_permission` (Task 8), `get_current_user` (Task 8).

- [ ] **Step 1: Update the failing test first — inject an authenticated admin user**

```python
# backend/tests/test_sources_router.py
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models import Role, Source, User, UserRole
from backend.routers import sources


@pytest.fixture
def admin_user(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"admin-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(sources.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def test_list_sources_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(sources.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get("/api/sources")
    assert response.status_code == 403  # HTTPBearer trả 403 khi thiếu header Authorization


def test_list_sources_returns_only_active_sources(app_client, db_session):
    active = Source(name="Active", domain=f"active-{uuid.uuid4()}.example", group_name="G1", is_active=True)
    inactive = Source(name="Inactive", domain=f"inactive-{uuid.uuid4()}.example", group_name="G1", is_active=False)
    db_session.add_all([active, inactive])
    db_session.commit()

    try:
        response = app_client.get("/api/sources")

        assert response.status_code == 200
        names = [s["name"] for s in response.json()["sources"]]
        assert "Active" in names
        assert "Inactive" not in names
    finally:
        db_session.delete(active)
        db_session.delete(inactive)
        db_session.commit()


def test_list_sources_returns_expected_fields(app_client, db_session):
    source = Source(name="Test", domain=f"test-{uuid.uuid4()}.example", group_name="Test Group", is_active=True)
    db_session.add(source)
    db_session.commit()

    try:
        response = app_client.get("/api/sources")

        body = next(s for s in response.json()["sources"] if s["name"] == "Test")
        assert body["source_id"] == str(source.source_id)
        assert body["domain"] == source.domain
        assert body["group_name"] == "Test Group"
    finally:
        db_session.delete(source)
        db_session.commit()
```

- [ ] **Step 2: Run test to verify the new negative test fails (permission not enforced yet)**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_sources_router.py -v`
Expected: `test_list_sources_rejects_unauthenticated_request` FAILS (currently returns 200, not 403) — the other 2 tests should already pass since `app_client` still works without permission checks in place.

- [ ] **Step 3: Add `require_permission` to the router**

```python
# backend/routers/sources.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth.dependencies import require_permission
from backend.db import get_db
from backend.models import Source

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def list_sources(db: Session = Depends(get_db), _user=Depends(require_permission("source", "view"))):
    # Chỉ trả nguồn active — FE dùng để render sidebar chọn nguồn (Slice 2)
    rows = db.query(Source).filter_by(is_active=True).order_by(Source.group_name, Source.name).all()
    return {
        "sources": [
            {
                "source_id": str(s.source_id),
                "name": s.name,
                "domain": s.domain,
                "group_name": s.group_name,
            }
            for s in rows
        ]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_sources_router.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/sources.py backend/tests/test_sources_router.py
git commit -m "feat: require source.view permission on GET /api/sources"
```

---

### Task 12: Apply `require_permission` to `reports.py`

**Files:**
- Modify: `backend/routers/reports.py`
- Modify: `backend/tests/test_reports_router.py`

**Interfaces:**
- Consumes: `require_permission` (Task 8).
- Permission mapping: `POST /create` → `report.create`; `GET /history`, `GET /{job_id}/status`, `GET /{job_id}/articles`, `GET /{job_id}/download` → `report.view`; `POST /{job_id}/cancel` → `report.create` (no dedicated "cancel" permission in the RBAC matrix — cancelling is part of managing a report run, same gate as creating one).

- [ ] **Step 1: Add auth fixtures to the test file (same pattern as Task 11)**

At the top of `backend/tests/test_reports_router.py`, add:
```python
from backend.auth.dependencies import get_current_user
from backend.models import Role, User, UserRole
```

Change the `app_client` fixture to:
```python
@pytest.fixture
def admin_user(db_session):
    role = db_session.query(Role).filter_by(code="ADMIN").first()
    if role is None:
        pytest.skip("Chưa chạy migration 0011 (seed roles) trên DB test")
    user = User(username=f"admin-{uuid.uuid4()}", password_hash="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db_session.commit()
    return user


@pytest.fixture
def app_client(db_session, admin_user):
    app = FastAPI()
    app.include_router(reports.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)
```

(Leave every other fixture/test in the file unchanged — they already use `app_client`, so they automatically become authenticated.)

- [ ] **Step 2: Run test to verify existing tests still pass with the fixture change (no permission enforcement yet)**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_reports_router.py -v`
Expected: all pass (auth override makes every call act as ADMIN, which already has all permissions once Task 12 Step 3 below adds the checks — but even before that, this step should be a no-op pass since nothing is enforced yet).

- [ ] **Step 3: Add `require_permission` to every endpoint**

```python
# backend/routers/reports.py — add this import
from backend.auth.dependencies import require_permission
```

Then update each handler signature (keep all existing bodies unchanged):
```python
@router.post("/create")
def create_report(
    payload: CreateReportRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_permission("report", "create")),
):
    ...


@router.get("/history")
def get_report_history(db: Session = Depends(get_db), _user=Depends(require_permission("report", "view"))):
    ...


@router.get("/{job_id}/status")
def get_report_status(
    job_id: UUID, db: Session = Depends(get_db), _user=Depends(require_permission("report", "view"))
):
    ...


@router.get("/{job_id}/articles")
def get_report_articles(
    job_id: UUID, db: Session = Depends(get_db), _user=Depends(require_permission("report", "view"))
):
    ...


@router.post("/{job_id}/cancel")
def cancel_report(
    job_id: UUID, db: Session = Depends(get_db), _user=Depends(require_permission("report", "create"))
):
    ...


@router.get("/{job_id}/download")
def download_report(
    job_id: UUID, db: Session = Depends(get_db), _user=Depends(require_permission("report", "view"))
):
    ...
```

- [ ] **Step 4: Add one negative test + run full file**

Add to `backend/tests/test_reports_router.py`:
```python
def test_create_report_rejects_unauthenticated_request(db_session):
    app = FastAPI()
    app.include_router(reports.router)
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.post("/api/reports/create", json={"source_ids": [], "date_from": "2026-01-01", "date_to": "2026-01-02"})
    assert response.status_code == 403
```

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests/test_reports_router.py -v`
Expected: all pass, including the new negative test.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/reports.py backend/tests/test_reports_router.py
git commit -m "feat: require report.create/report.view permissions on all /api/reports endpoints"
```

---

### Task 13: Run the full backend suite + lint

**Files:** none new — verification task.

- [ ] **Step 1: Run every backend test**

Run: `SECRET_KEY=test-secret .venv/bin/python -m pytest backend/tests -v`
Expected: all green.

- [ ] **Step 2: Manual smoke test against the running Docker stack**

```bash
docker compose up -d --build
curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<value of SEED_ADMIN_PASSWORD in your .env>"}'
```
Expected: 200 with tokens. Then:
```bash
curl -s http://localhost:8000/api/sources
```
Expected: `403` (no `Authorization` header) — confirms the middleware is really active end-to-end, not just in tests.

- [ ] **Step 3: Commit (only if Steps 1–2 required a fix)**

No commit needed if nothing changed — this task is verification-only, per `.claude/rules/14-coding-behavior.md` point 4.

---

### Task 14: FE `lib/api.ts` — `authFetch()` with auto-refresh

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: `authFetch(path: string, init?: RequestInit) => Promise<Response>` — consumed by Tasks 19–20 and by `AuthContext` (Task 15).

- [ ] **Step 1: Write the implementation**

```typescript
// frontend/src/lib/api.ts
export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return null;

  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return null;

  const data = await res.json();
  localStorage.setItem("access_token", data.access_token);
  return data.access_token as string;
}

// Wrapper cho mọi API call cần auth — tự gắn Bearer token, tự refresh 1 lần nếu
// access token hết hạn (401), tự điều hướng về /login nếu refresh cũng thất bại.
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem("access_token");
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      response = await fetch(`${API_BASE}${path}`, { ...init, headers });
    } else {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
  }

  return response;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run type-check`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: authFetch() helper — auto-attach Bearer token + single refresh retry on 401"
```

---

### Task 15: FE `lib/AuthContext.tsx` — `AuthProvider` + `useAuth`

**Files:**
- Create: `frontend/src/lib/AuthContext.tsx`

**Interfaces:**
- Consumes: `API_BASE` (`frontend/src/lib/api.ts`, existing).
- Produces: `AuthProvider` (wraps the app), `useAuth() -> { user, loading, login, logout }` — consumed by Task 16 (`ProtectedRoute`, `PermissionGuard`), Task 17 (`Login` page), Task 18 (`main.tsx`), Task 19 (`MainLayout`).

- [ ] **Step 1: Write the implementation**

```typescript
// frontend/src/lib/AuthContext.tsx
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

export type CurrentUser = {
  user_id: string;
  username: string;
  roles: string[];
  permissions: string[];
};

type AuthContextValue = {
  user: CurrentUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchMe(accessToken: string): Promise<CurrentUser> {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error("unauthorized");
  return res.json();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    fetchMe(token)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: "Đăng nhập thất bại" }));
      throw new Error(body.detail ?? "Đăng nhập thất bại");
    }
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    setUser(data.user);
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth() phải được gọi bên trong AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run type-check`
Expected: no errors (this file isn't wired into the app yet, so no runtime check possible until Task 18).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/AuthContext.tsx
git commit -m "feat: AuthContext — login/logout/me, token persisted in localStorage"
```

---

### Task 16: FE `ProtectedRoute` + `PermissionGuard`

**Files:**
- Create: `frontend/src/components/common/ProtectedRoute.tsx`
- Create: `frontend/src/components/common/PermissionGuard.tsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 15).
- Produces: `<ProtectedRoute />` (consumed by Task 18's `App.tsx`), `<PermissionGuard permission="...">` (available for future use — not wired to any button in Phase 1 since Phase 1 doesn't gate individual buttons, only whole routes/endpoints).

- [ ] **Step 1: Write `ProtectedRoute`**

```typescript
// frontend/src/components/common/ProtectedRoute.tsx
import { Spin } from "antd";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";

export default function ProtectedRoute() {
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

  return <Outlet />;
}
```

- [ ] **Step 2: Write `PermissionGuard`**

```typescript
// frontend/src/components/common/PermissionGuard.tsx
import { ReactNode } from "react";
import { useAuth } from "@/lib/AuthContext";

type Props = {
  permission: string;
  children: ReactNode;
};

export default function PermissionGuard({ permission, children }: Props) {
  const { user } = useAuth();
  if (!user?.permissions.includes(permission)) return null;
  return <>{children}</>;
}
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npm run type-check`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/common/ProtectedRoute.tsx frontend/src/components/common/PermissionGuard.tsx
git commit -m "feat: ProtectedRoute + PermissionGuard components"
```

---

### Task 17: FE `Login` page

**Files:**
- Create: `frontend/src/pages/Login/index.tsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 15).
- Produces: default-exported `LoginPage` component — consumed by Task 18's `App.tsx`.

- [ ] **Step 1: Write the page**

```typescript
// frontend/src/pages/Login/index.tsx
import { useState } from "react";
import { Button, Card, Form, Input, Typography, message } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import Logo from "@/components/common/Logo";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  async function onFinish(values: { username: string; password: string }) {
    setSubmitting(true);
    try {
      await login(values.username, values.password);
      navigate("/", { replace: true });
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Đăng nhập thất bại");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#F5F7FA",
      }}
    >
      <Card style={{ width: 380 }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
          <Logo />
        </div>
        <Typography.Title level={4} style={{ textAlign: "center", marginBottom: 24 }}>
          Đăng nhập
        </Typography.Title>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="Tên đăng nhập" rules={[{ required: true, message: "Nhập tên đăng nhập" }]}>
            <Input prefix={<UserOutlined />} autoFocus />
          </Form.Item>
          <Form.Item name="password" label="Mật khẩu" rules={[{ required: true, message: "Nhập mật khẩu" }]}>
            <Input.Password prefix={<LockOutlined />} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={submitting}>
              Đăng nhập
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run type-check`
Expected: no errors. (`Logo` component's prop signature — check `frontend/src/components/common/Logo.tsx` accepts being called with no props; if it requires `collapsed: boolean`, pass `collapsed={false}` instead.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Login/index.tsx
git commit -m "feat: /login page"
```

---

### Task 18: Wire `AuthProvider` + `/login` route + `ProtectedRoute` into the app

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `AuthProvider` (Task 15), `LoginPage` (Task 17), `ProtectedRoute` (Task 16).

- [ ] **Step 1: Wrap `App` in `AuthProvider`**

```typescript
// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider, App as AntdApp } from "antd";
import viVN from "antd/locale/vi_VN";
import dayjs from "dayjs";
import "dayjs/locale/vi";
import App from "./App";
import { theme } from "./theme";
import { AuthProvider } from "@/lib/AuthContext";
import "./index.css";

dayjs.locale("vi");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ConfigProvider theme={theme} locale={viVN}>
        <AntdApp>
          <AuthProvider>
            <App />
          </AuthProvider>
        </AntdApp>
      </ConfigProvider>
    </BrowserRouter>
  </React.StrictMode>
);
```

- [ ] **Step 2: Add `/login` route + wrap the existing `MainLayout` route in `ProtectedRoute`**

```typescript
// frontend/src/App.tsx — add these two imports
import LoginPage from "@/pages/Login";
import ProtectedRoute from "@/components/common/ProtectedRoute";
```

Change the top-level `<Routes>` from:
```typescript
    <Routes>
      <Route element={<MainLayout />}>
```
to:
```typescript
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<MainLayout />}>
```
and close the extra `<Route>` at the end (before `</Routes>`):
```typescript
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
      </Route>
    </Routes>
```

- [ ] **Step 3: Type-check + manual browser check**

Run: `cd frontend && npm run type-check`
Expected: no errors.

Run: `cd frontend && npm run dev`, open `http://localhost:5173` in a browser.
Expected: redirected to `/login` (no token yet). Log in with `admin` / the `SEED_ADMIN_PASSWORD` value → redirected to `/` and the Dashboard renders.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/main.tsx frontend/src/App.tsx
git commit -m "feat: wire AuthProvider + /login route + ProtectedRoute into the app"
```

---

### Task 19: `MainLayout` — show real logged-in user + logout

**Files:**
- Modify: `frontend/src/layouts/MainLayout.tsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 15).

- [ ] **Step 1: Replace the hardcoded user block**

Add the import:
```typescript
import { useAuth } from "@/lib/AuthContext";
import { useNavigate } from "react-router-dom"; // already imported — reuse existing import
import { LogoutOutlined } from "@ant-design/icons"; // add to the existing icon import block
```

Inside `MainLayout()`, add:
```typescript
  const { user, logout } = useAuth();
```

Replace:
```typescript
            <Space style={{ cursor: "default" }}>
              <Avatar style={{ background: "#00859A" }} size={32} icon={<UserOutlined />} />
              {!collapsed && (
                <Typography.Text strong style={{ color: "#0A1D55" }}>
                  Nguyễn Văn A
                </Typography.Text>
              )}
            </Space>
```
with:
```typescript
            <Space style={{ cursor: "default" }}>
              <Avatar style={{ background: "#00859A" }} size={32} icon={<UserOutlined />} />
              {!collapsed && (
                <Typography.Text strong style={{ color: "#0A1D55" }}>
                  {user?.username}
                </Typography.Text>
              )}
            </Space>
            <Button
              type="text"
              icon={<LogoutOutlined style={{ fontSize: 16 }} />}
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              {!collapsed && "Đăng xuất"}
            </Button>
```

- [ ] **Step 2: Type-check + manual browser check**

Run: `cd frontend && npm run type-check`
Expected: no errors.

Run: `cd frontend && npm run dev`, log in, confirm the header shows `admin` and clicking "Đăng xuất" redirects to `/login` and blocks access to `/` again.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/layouts/MainLayout.tsx
git commit -m "feat: MainLayout header shows real logged-in user + logout button"
```

---

### Task 20: Update `Sources`/`Reports` pages to use `authFetch`

**Files:**
- Modify: `frontend/src/pages/Sources/index.tsx`
- Modify: `frontend/src/pages/Reports/index.tsx`
- Modify: `frontend/src/pages/Reports/ReportCreate.tsx`

**Interfaces:**
- Consumes: `authFetch` (Task 14).

- [ ] **Step 1: `Sources/index.tsx`**

Replace:
```typescript
import { API_BASE } from "@/lib/api";
```
with:
```typescript
import { authFetch } from "@/lib/api";
```
Replace:
```typescript
    fetch(`${API_BASE}/api/sources`)
```
with:
```typescript
    authFetch("/api/sources")
```

- [ ] **Step 2: `Reports/index.tsx` and `Reports/ReportCreate.tsx`**

Run: `grep -n "API_BASE\|fetch(" frontend/src/pages/Reports/index.tsx frontend/src/pages/Reports/ReportCreate.tsx`

For every occurrence of `fetch(\`${API_BASE}...\`, ...)`, apply the same transform: import `authFetch` instead of (or alongside) `API_BASE`, and change the call to `authFetch("/api/reports/...", { ...same second argument... })` — keeping the exact same path suffix and the same `method`/`headers`/`body` options already present, just dropping the `${API_BASE}` template prefix since `authFetch` prepends it internally.

- [ ] **Step 3: Type-check**

Run: `cd frontend && npm run type-check`
Expected: no errors.

- [ ] **Step 4: Manual browser check**

Run: `cd frontend && npm run dev`, log in as `admin`, visit `/sources` — list loads. Visit `/reports/create`, pick a source + date range, submit — job created successfully (proves the `Authorization` header reaches the backend and `report.create` permission passes for `admin`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Sources/index.tsx frontend/src/pages/Reports/index.tsx frontend/src/pages/Reports/ReportCreate.tsx
git commit -m "feat: Sources/Reports pages use authFetch so requests carry the JWT"
```

---

## Self-Review Notes

- **Spec coverage:** all "Thêm"/"Sửa" bullets from roadmap Phase 1 are covered — 5 tables (Task 2–3), RBAC matrix seed (Task 4), JWT 60min/7day (Task 6), `require_permission` on `/api/sources` + `/api/reports/*` (Task 11–12), `/login` page (Task 17), rate limiting + lockout (Task 9). `PermissionGuard` exists (Task 16) but per the confirmed scope decision is not wired to any button yet, since Phase 1 doesn't add new gated UI actions beyond whole-page auth.
- **Deferred (explicitly out of scope, confirmed with user):** `/api/users`, `/api/roles` CRUD, wiring `/system/users` and `/system/roles` mock pages to real data, `audit_logs`/`system_settings` (Phase 9).
- **Type consistency:** `require_permission(resource, action)` used identically in Tasks 8, 11, 12. `UserResponse`/`TokenResponse` shape used identically in Task 7 (schema), Task 9 (router), Task 15 (FE `CurrentUser` type) — `{user_id, username, roles[], permissions[]}` matches rule 05's `GET /api/auth/me` contract exactly.
