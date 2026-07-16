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
