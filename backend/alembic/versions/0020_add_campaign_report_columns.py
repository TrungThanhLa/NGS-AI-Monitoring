"""thêm campaign_id/format/status/error_log vào report_history — chuẩn bị cho luồng
báo cáo theo Campaign (Phase 7), CHƯA đụng bảng jobs/report_history.job_id (giữ additive,
để luồng Job cũ vẫn chạy được cho tới khi cutover ở migration 0021)

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "report_history",
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.campaign_id"), nullable=True),
    )
    op.add_column("report_history", sa.Column("format", sa.String(20), server_default="docx", nullable=False))
    # status mặc định 'completed' — an toàn cho các dòng report_history cũ do luồng Job
    # (report_job.py) ghi trực tiếp sau khi file đã sinh xong, không qua polling
    op.add_column("report_history", sa.Column("status", sa.String(20), server_default="completed", nullable=False))
    op.add_column("report_history", sa.Column("error_log", sa.Text))


def downgrade():
    op.drop_column("report_history", "error_log")
    op.drop_column("report_history", "status")
    op.drop_column("report_history", "format")
    op.drop_column("report_history", "campaign_id")
