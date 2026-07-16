"""fix: MANAGER thiếu permission case.close so với RBAC matrix rule 15 (case.close = Y
cho cả ADMIN và MANAGER) — migration 0011 seed thiếu sót permission này cho MANAGER.
Không sửa lại 0011 vì đã apply lên DB dev chung — chỉ bù đúng 1 dòng còn thiếu.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-16
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Namespace + công thức UUID5 giống hệt 0011 — để trỏ đúng vào row role/permission đã tồn tại
_NAMESPACE = uuid.UUID("6fbb1d60-7b1a-4e9a-9c1a-000000000000")

_MANAGER_ROLE_ID = str(uuid.uuid5(_NAMESPACE, "role:MANAGER"))
_CASE_CLOSE_PERMISSION_ID = str(uuid.uuid5(_NAMESPACE, "permission:case.close"))


def upgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "VALUES (:role_id, :permission_id) ON CONFLICT DO NOTHING"
        ),
        {"role_id": _MANAGER_ROLE_ID, "permission_id": _CASE_CLOSE_PERMISSION_ID},
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE role_id = :role_id AND permission_id = :permission_id"
        ),
        {"role_id": _MANAGER_ROLE_ID, "permission_id": _CASE_CLOSE_PERMISSION_ID},
    )
