"""thêm bảng crawl_queue/system_settings/campaign_articles/campaign_article_keywords
+ cột lịch crawl trên sources + partial unique index articles cho Phase 3
Scheduler & Continuous Crawl

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("crawl_frequency", sa.Integer, server_default="1800"))
    op.add_column("sources", sa.Column("last_crawled_at", sa.TIMESTAMP))
    op.add_column("sources", sa.Column("status", sa.String(30), server_default="ACTIVE"))
    op.add_column("sources", sa.Column("consecutive_error_count", sa.Integer, server_default="0"))

    op.create_table(
        "crawl_queue",
        sa.Column("queue_id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.source_id", ondelete="RESTRICT")),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("discovered_at", sa.TIMESTAMP, server_default=sa.text("now()")),
        sa.Column("fetched_at", sa.TIMESTAMP),
        sa.UniqueConstraint("source_id", "url_hash", name="crawl_queue_source_id_url_hash_key"),
    )

    op.create_table(
        "system_settings",
        sa.Column("setting_key", sa.String(255), primary_key=True),
        sa.Column("setting_value", sa.Text),
        sa.Column("data_type", sa.String(50)),
        sa.Column("description", sa.Text),
        sa.Column("updated_at", sa.TIMESTAMP),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.user_id")),
    )
    op.execute(
        """
        INSERT INTO system_settings (setting_key, setting_value, data_type, description) VALUES
        ('SCHEDULER_ENABLED', 'false', 'BOOLEAN', 'Bật/tắt Celery Beat tự động crawl liên tục theo Campaign ACTIVE'),
        ('AI_AUTO_TRIGGER', 'false', 'BOOLEAN', 'Tự động chạy AI phân tích ngay sau khi crawl xong 1 bài')
        """
    )

    op.create_table(
        "campaign_articles",
        sa.Column(
            "campaign_id", UUID(as_uuid=True),
            sa.ForeignKey("campaigns.campaign_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column(
            "article_id", UUID(as_uuid=True),
            sa.ForeignKey("articles.article_id", ondelete="RESTRICT"), primary_key=True,
        ),
        sa.Column("matched_keyword_id", UUID(as_uuid=True), sa.ForeignKey("keywords.keyword_id")),
        sa.Column("matched_at", sa.TIMESTAMP, server_default=sa.text("now()")),
    )

    op.create_table(
        "campaign_article_keywords",
        sa.Column("campaign_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "keyword_id", UUID(as_uuid=True),
            sa.ForeignKey("keywords.keyword_id"), primary_key=True,
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id", "article_id"],
            ["campaign_articles.campaign_id", "campaign_articles.article_id"],
            name="campaign_article_keywords_campaign_article_fkey",
        ),
    )

    op.create_index(
        "articles_source_id_url_hash_continuous_key",
        "articles",
        ["source_id", "url_hash"],
        unique=True,
        postgresql_where=sa.text("job_id IS NULL"),
    )


def downgrade():
    op.drop_index("articles_source_id_url_hash_continuous_key", table_name="articles")
    op.drop_table("campaign_article_keywords")
    op.drop_table("campaign_articles")
    op.drop_table("system_settings")
    op.drop_table("crawl_queue")
    op.drop_column("sources", "consecutive_error_count")
    op.drop_column("sources", "status")
    op.drop_column("sources", "last_crawled_at")
    op.drop_column("sources", "crawl_frequency")
