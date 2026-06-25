"""initial schema — sources, jobs, articles, article_analysis, report_history

Revision ID: 0001
Revises:
Create Date: 2026-06-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.create_table(
        "sources",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False, unique=True),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("sitemap_url", sa.Text),
        sa.Column("listing_url", sa.Text),
        sa.Column("parsing_rules", postgresql.JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )

    op.create_table(
        "jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("date_from", sa.Date, nullable=False),
        sa.Column("date_to", sa.Date, nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("output_docx", sa.Text),
        sa.Column("output_json", sa.Text),
        sa.Column("error_log", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.TIMESTAMP),
    )

    op.create_table(
        "articles",
        sa.Column("article_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.source_id")),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.Text),
        sa.Column("content_raw", sa.Text),
        sa.Column("author", sa.Text),
        sa.Column("published_at", sa.TIMESTAMP),
        sa.Column("crawled_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("status", sa.String(50), server_default="pending_analysis"),
    )

    op.create_table(
        "article_analysis",
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("articles.article_id")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")),
        sa.Column("topics", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.Text), server_default="{}"),
        sa.Column("sentiment", sa.String(20)),
        sa.Column("emotion", sa.String(20)),
        sa.Column("confidence", sa.Float),
        sa.Column("needs_review", sa.Boolean, server_default=sa.text("false")),
        sa.Column("summary", sa.Text),
        sa.Column("prompt_version", sa.Integer, nullable=False),
        sa.Column("analyzed_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )

    op.create_table(
        "report_history",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("report_history")
    op.drop_table("article_analysis")
    op.drop_table("articles")
    op.drop_table("jobs")
    op.drop_table("sources")
