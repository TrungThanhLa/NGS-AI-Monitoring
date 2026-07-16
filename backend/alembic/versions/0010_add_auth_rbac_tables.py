"""thêm bảng users/roles/permissions/user_roles/role_permissions cho Phase 1 Auth & RBAC

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("full_name", sa.String(255)),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("status", sa.String(30), server_default="ACTIVE"),
        sa.Column("failed_login_count", sa.Integer, server_default="0"),
        sa.Column("locked_until", sa.TIMESTAMP),
        sa.Column("last_login_at", sa.TIMESTAMP),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP),
        sa.Column("deleted_at", sa.TIMESTAMP),
    )

    op.create_table(
        "roles",
        sa.Column("role_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_system", sa.Boolean, server_default="true"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )

    op.create_table(
        "permissions",
        sa.Column(
            "permission_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column(
            "permission_id",
            UUID(as_uuid=True),
            sa.ForeignKey("permissions.permission_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )


def downgrade():
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
