"""xóa sạch dữ liệu crawl/campaign cũ trước khi triển khai lại cơ chế Discover CONTINUOUS
theo hợp (union) khoảng ngày Campaign — xác nhận với user 2026-07-23, GIỮ LẠI `sources`
(cấu hình nguồn thật, không phải dữ liệu test). Tránh phải xử lý tình huống "Nguồn đã có
Campaign ACTIVE từ trước lúc migration chạy" — mọi Nguồn bắt đầu sạch, không đồng loạt
backfill ngay lúc deploy (xem docs/superpowers/specs/2026-07-23-continuous-discover-per-
campaign-window-design.md mục Rollout).

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

# Ngưỡng an toàn — nếu bất kỳ bảng nào vượt quá, migration DỪNG LẠI thay vì xóa mù quáng
# (đúng pattern đã áp dụng ở migration 0021 khi xóa bảng jobs). Dữ liệu dev/test hiện tại
# nhỏ hơn nhiều so với ngưỡng này (xem log Step 1 lúc viết plan) — chỉ dùng làm lưới an
# toàn chống chạy nhầm vào DB không phải dev/test.
_MAX_SAFE_ROW_COUNT = 100_000


def upgrade():
    conn = op.get_bind()
    for table in ("articles", "campaigns", "crawl_queue"):
        count = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar()
        if count > _MAX_SAFE_ROW_COUNT:
            raise RuntimeError(
                f"Migration 0024 dừng lại: bảng {table} có {count} dòng, vượt ngưỡng an "
                f"toàn {_MAX_SAFE_ROW_COUNT}. Đây có thể là dữ liệu thật, không phải dữ liệu "
                "dev/test. Xác nhận lại với người vận hành / backup thủ công trước khi chạy lại."
            )

    # Xóa theo đúng thứ tự phụ thuộc FK — con trước cha
    op.execute("DELETE FROM campaign_article_keywords")
    op.execute("DELETE FROM campaign_articles")
    op.execute("DELETE FROM campaign_crawl_progress")
    op.execute("DELETE FROM campaign_keywords")
    op.execute("DELETE FROM campaign_sources")
    op.execute("DELETE FROM report_history")
    op.execute("DELETE FROM article_analysis")
    op.execute("DELETE FROM articles")
    op.execute("DELETE FROM crawl_queue")
    op.execute("DELETE FROM campaigns")
    op.execute("DELETE FROM keywords")
    # sources KHÔNG bị đụng tới — giữ nguyên cấu hình nguồn thật


def downgrade():
    # Không thể khôi phục dữ liệu đã xóa — downgrade chỉ ghi nhận, không làm gì.
    pass
