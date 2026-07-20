"""thêm bảng campaigns/keywords/campaign_keywords/campaign_sources cho Phase 2
Campaign & Master Data + cột sources.source_group

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("source_group", sa.String(255)))

    op.create_table(
        "keywords",
        sa.Column("keyword_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("keyword", sa.String(500), nullable=False),
        sa.Column("topic_group", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )

    op.create_table(
        "campaigns",
        sa.Column("campaign_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("objective", sa.Text),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(50), server_default="DRAFT"),
        sa.Column("mode", sa.String(20), server_default="CONTINUOUS"),
        sa.Column("start_date", sa.TIMESTAMP, nullable=False),
        sa.Column("end_date", sa.TIMESTAMP),
        sa.Column("alert_threshold", sa.Integer, server_default="100"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP),
        sa.Column("deleted_at", sa.TIMESTAMP),
    )

    op.create_table(
        "campaign_keywords",
        sa.Column(
            "campaign_id", UUID(as_uuid=True),
            sa.ForeignKey("campaigns.campaign_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column(
            "keyword_id", UUID(as_uuid=True),
            sa.ForeignKey("keywords.keyword_id", ondelete="RESTRICT"), primary_key=True,
        ),
    )

    op.create_table(
        "campaign_sources",
        sa.Column(
            "campaign_id", UUID(as_uuid=True),
            sa.ForeignKey("campaigns.campaign_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column(
            "source_id", UUID(as_uuid=True),
            sa.ForeignKey("sources.source_id", ondelete="RESTRICT"), primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("campaign_sources")
    op.drop_table("campaign_keywords")
    op.drop_table("campaigns")
    op.drop_table("keywords")
    op.drop_column("sources", "source_group")
