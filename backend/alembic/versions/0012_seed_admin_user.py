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
