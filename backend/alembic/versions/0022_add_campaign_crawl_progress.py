"""thêm bảng campaign_crawl_progress — theo dõi tiến độ crawl từng Source của Campaign
ONE_SHOT (Discover xong bao nhiêu URL, đã fetch/tái sử dụng xong bao nhiêu) để FE hiển
thị progress UI trực quan thay vì chỉ thấy status=ACTIVE chung chung

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campaign_crawl_progress",
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.campaign_id"), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.source_id"), primary_key=True),
        sa.Column("total_urls", sa.Integer),
        sa.Column("done_urls", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("updated_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("campaign_crawl_progress")
