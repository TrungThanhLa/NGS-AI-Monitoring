"""thêm ai_model vào article_analysis — track model AI đã dùng, chuẩn bị đổi model khi chuyển server GPU

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("article_analysis", sa.Column("ai_model", sa.String(255)))
    # Backfill: mọi bản ghi trước migration này đều chạy bằng qwen3:8b (model duy nhất
    # từng dùng, xem Quick Reference CLAUDE.md) — không có model nào khác để suy luận.
    op.execute(sa.text("UPDATE article_analysis SET ai_model = 'qwen3:8b' WHERE ai_model IS NULL"))
    op.alter_column("article_analysis", "ai_model", nullable=False)


def downgrade():
    op.drop_column("article_analysis", "ai_model")
