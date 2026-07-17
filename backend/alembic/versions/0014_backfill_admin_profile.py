"""backfill full_name/email cho user 'admin' đã seed ở migration 0012 (lúc đó chỉ set
username/password_hash) — cần có dữ liệu hiển thị cho màn hình Thông tin cá nhân
(GET /api/auth/me).

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users SET full_name = 'System Administrator', email = 'admin@ngs.gov.vn' "
            "WHERE username = 'admin' AND full_name IS NULL"
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users SET full_name = NULL, email = NULL "
            "WHERE username = 'admin' AND full_name = 'System Administrator'"
        )
    )
