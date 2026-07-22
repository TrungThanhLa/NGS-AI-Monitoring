"""xóa hẳn bảng jobs + mọi dữ liệu liên quan (hard-delete, đã xác nhận với user —
dữ liệu test, chấp nhận mất, không backup) — thay thế hoàn toàn bằng campaigns
(mode=ONE_SHOT/CONTINUOUS). Đổi report_history.campaign_id thành NOT NULL, đổi dedup
articles từ UNIQUE(job_id, url_hash) sang UNIQUE(source_id, url_hash) toàn bảng (Phase 7)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

# Ngưỡng an toàn — nếu số dòng jobs vượt quá, migration DỪNG LẠI thay vì xóa mù quáng.
# Nâng từ 5 lên 50 (2026-07-22) sau khi xác nhận với người phụ trách dự án: 36 dòng jobs
# hiện có đều là dữ liệu test/dev (status='completed', tạo trong ~32 giờ ngày 2026-07-15/16,
# khớp với sự cố rò rỉ dữ liệu test đã biết trước đó của dự án) — chấp nhận xóa.
_MAX_SAFE_JOBS_ROW_COUNT = 50


def upgrade():
    conn = op.get_bind()
    jobs_count = conn.execute(sa.text("SELECT COUNT(*) FROM jobs")).scalar()
    if jobs_count > _MAX_SAFE_JOBS_ROW_COUNT:
        raise RuntimeError(
            f"Migration 0021 dừng lại: bảng jobs có {jobs_count} dòng, vượt ngưỡng an toàn "
            f"{_MAX_SAFE_JOBS_ROW_COUNT}. Đây có thể là dữ liệu thật, không phải dữ liệu test. "
            "Xác nhận lại với người vận hành / backup thủ công trước khi chạy lại migration này."
        )

    # Xóa theo đúng thứ tự phụ thuộc FK: article_analysis -> articles -> report_history -> jobs
    op.execute("DELETE FROM article_analysis WHERE job_id IS NOT NULL")
    op.execute("DELETE FROM articles WHERE job_id IS NOT NULL")
    op.execute("DELETE FROM report_history WHERE job_id IS NOT NULL")

    op.drop_column("report_history", "job_id")
    op.alter_column("report_history", "campaign_id", nullable=False)

    op.drop_column("article_analysis", "job_id")

    # Dedup articles: đổi từ UNIQUE(job_id, url_hash) [migration 0009] sang
    # UNIQUE(source_id, url_hash) toàn bảng — partial index (source_id, url_hash)
    # WHERE job_id IS NULL [migration 0018] giờ dư thừa vì job_id sắp bị xóa hẳn.
    op.drop_constraint("articles_job_id_url_hash_key", "articles", type_="unique")
    op.drop_index("articles_source_id_url_hash_continuous_key", table_name="articles")
    op.drop_column("articles", "job_id")
    op.create_unique_constraint("articles_source_id_url_hash_key", "articles", ["source_id", "url_hash"])

    op.drop_table("jobs")


def downgrade():
    # Downgrade khôi phục CẤU TRÚC bảng jobs (rỗng) + cột job_id — KHÔNG khôi phục được
    # dữ liệu đã hard-delete ở upgrade() (đã chấp nhận đánh đổi này khi quyết định
    # hard-delete thay vì backup, xem design doc mục "Data Model"). Downgrade chỉ để đảm
    # bảo round-trip schema sạch cho môi trường CHƯA từng chạy upgrade() với dữ liệu thật.
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_ids", sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column("date_from", sa.Date, nullable=False),
        sa.Column("date_to", sa.Date, nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("output_docx", sa.Text),
        sa.Column("output_json", sa.Text),
        sa.Column("error_log", sa.Text),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("created_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("completed_at", sa.TIMESTAMP),
    )

    op.drop_constraint("articles_source_id_url_hash_key", "articles", type_="unique")
    op.add_column("articles", sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")))
    op.create_unique_constraint("articles_job_id_url_hash_key", "articles", ["job_id", "url_hash"])
    op.create_index(
        "articles_source_id_url_hash_continuous_key", "articles", ["source_id", "url_hash"],
        unique=True, postgresql_where=sa.text("job_id IS NULL"),
    )

    op.add_column("article_analysis", sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")))

    op.alter_column("report_history", "campaign_id", nullable=True)
    op.add_column("report_history", sa.Column("job_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.job_id")))
