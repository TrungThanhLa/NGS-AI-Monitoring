"""thêm bảng source_groups — danh mục Nhóm nguồn chuẩn hóa (BR-SRC-01: mỗi Nguồn thuộc
đúng 1 Nhóm nguồn, VD Chính phủ/Bộ ngành/Báo chí), thay cho việc gõ tay tự do vào cột
sources.source_group hiện có (cột này giữ nguyên VARCHAR, chỉ validate giá trị khớp tên
1 Nhóm nguồn active — không đổi thành FK để tránh ảnh hưởng rộng tới các nơi đang đọc
sources.source_group dạng chuỗi)

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-24
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

_SEED_GROUPS = ["Chính phủ", "Bộ ngành", "Báo chí"]


def upgrade():
    op.create_table(
        "source_groups",
        sa.Column("group_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
    )

    table = sa.table("source_groups", sa.column("group_id", UUID), sa.column("name", sa.String))
    op.bulk_insert(table, [{"group_id": uuid.uuid4(), "name": name} for name in _SEED_GROUPS])


def downgrade():
    op.drop_table("source_groups")
