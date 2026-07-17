"""thêm cột phone + avatar_path (nullable, không bắt buộc) cho users

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("phone", sa.String(20)))
    op.add_column("users", sa.Column("avatar_path", sa.Text))


def downgrade():
    op.drop_column("users", "avatar_path")
    op.drop_column("users", "phone")
