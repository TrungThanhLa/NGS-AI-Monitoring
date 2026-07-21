"""thêm cột review status (business review workflow) cho articles — tách biệt
hoàn toàn với cột status kỹ thuật hiện có (pending_analysis|analyzed|error),
theo BR-CONTENT-02, cho Phase 4 (Content Repository & Review Workflow)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("articles", sa.Column("review_status", sa.String(50), server_default="NEW", nullable=False))
    op.add_column(
        "articles",
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="RESTRICT")),
    )
    op.add_column("articles", sa.Column("reviewed_at", sa.TIMESTAMP))
    op.add_column("articles", sa.Column("reviewer_note", sa.Text))
    # Cột dự phòng cho DELETE endpoint ở phase sau (BR-CONTENT-04) — Phase 4 KHÔNG có
    # nơi nào ghi giá trị vào cột này, luôn NULL cho tới khi có endpoint xóa thật.
    op.add_column("articles", sa.Column("deleted_at", sa.TIMESTAMP))


def downgrade():
    op.drop_column("articles", "deleted_at")
    op.drop_column("articles", "reviewer_note")
    op.drop_column("articles", "reviewed_at")
    op.drop_column("articles", "reviewed_by")
    op.drop_column("articles", "review_status")
