"""thêm sources.crawl_started_at — cờ đánh dấu crawl_task đang chạy thật cho Nguồn này
(ghi lúc bắt đầu, xóa về NULL lúc kết thúc dù thành công/lỗi), phục vụ cột "Trạng thái"
(Đang quét/Đã quét) trên UI Tiến độ crawl — thay vì hỏi Celery inspect().active() mỗi
lần gọi API (chậm, tốn RPC nếu poll dày)

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("crawl_started_at", sa.TIMESTAMP))


def downgrade():
    op.drop_column("sources", "crawl_started_at")
