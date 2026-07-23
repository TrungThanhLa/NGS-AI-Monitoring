"""thêm report_history.celery_task_id — cho phép Hủy report đang tạo (revoke Celery
task thật), giống cơ chế jobs.celery_task_id đã xóa cùng bảng jobs ở Phase 7

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("report_history", sa.Column("celery_task_id", sa.String(255)))


def downgrade():
    op.drop_column("report_history", "celery_task_id")
