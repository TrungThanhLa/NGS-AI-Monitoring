"""thêm sources.discover_backfilled_from — "mốc nước cao nhất" Discover đã chắc chắn
quét xong cho từng Nguồn, phục vụ cơ chế backfill theo hợp (union) khoảng ngày các
Campaign CONTINUOUS đang ACTIVE (thay cửa sổ trượt 30 ngày cố định cũ)

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("discover_backfilled_from", sa.TIMESTAMP))


def downgrade():
    op.drop_column("sources", "discover_backfilled_from")
