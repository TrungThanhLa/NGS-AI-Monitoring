"""thêm bảng audit_logs — bất biến, không soft-delete (BR-SYS-01 ngoại lệ)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_logs",
        sa.Column("audit_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("old_value", JSONB),
        sa.Column("new_value", JSONB),
        sa.Column("ip_address", sa.String(100)),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("audit_logs")
