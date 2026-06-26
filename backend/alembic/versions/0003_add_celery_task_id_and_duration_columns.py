"""thêm celery_task_id (jobs) và duration columns (articles, article_analysis)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("celery_task_id", sa.String(255)))
    op.add_column("articles", sa.Column("crawl_duration_seconds", sa.Float))
    op.add_column("article_analysis", sa.Column("analysis_duration_seconds", sa.Float))


def downgrade():
    op.drop_column("article_analysis", "analysis_duration_seconds")
    op.drop_column("articles", "crawl_duration_seconds")
    op.drop_column("jobs", "celery_task_id")
