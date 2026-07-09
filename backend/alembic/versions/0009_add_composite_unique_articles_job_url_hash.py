"""composite UNIQUE (job_id, url_hash) trên articles — mỗi job crawl/phân tích độc
lập, vẫn chống trùng URL trong phạm vi 1 job ở tầng DB (không chỉ dựa vào code)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("articles_url_hash_key", "articles", type_="unique")
    op.create_unique_constraint("articles_job_id_url_hash_key", "articles", ["job_id", "url_hash"])
    op.create_index("ix_articles_url_hash", "articles", ["url_hash"])


def downgrade():
    # Dedupe TRƯỚC khi tạo lại UNIQUE đơn trên url_hash — nếu không, lệnh
    # create_unique_constraint bên dưới sẽ crash vì lúc này DB đã có nhiều dòng
    # cùng url_hash khác job_id (đúng hành vi mong muốn sau khi upgrade chạy 1 thời
    # gian). Giữ lại đúng 1 dòng mới nhất cho mỗi url_hash (ưu tiên crawled_at lớn
    # nhất, dùng article_id làm tie-breaker khi trùng crawled_at), xoá các dòng còn
    # lại — downgrade là thao tác hiếm khi cần, chấp nhận mất dữ liệu các bản trùng
    # cũ hơn.
    # COALESCE về '-infinity' vì crawled_at nullable ở tầng schema — so sánh row
    # (a.crawled_at, ...) < (b.crawled_at, ...) trực tiếp sẽ trả NULL (falsy) nếu
    # 1 trong 2 bên NULL, khiến cả 2 dòng trùng đều "sống sót" và câu lệnh
    # create_unique_constraint bên dưới crash vì duplicate key.
    op.execute(
        """
        DELETE FROM articles a
        USING articles b
        WHERE a.url_hash = b.url_hash
          AND (COALESCE(a.crawled_at, '-infinity'::timestamp), a.article_id)
            < (COALESCE(b.crawled_at, '-infinity'::timestamp), b.article_id)
        """
    )
    op.drop_index("ix_articles_url_hash", "articles")
    op.drop_constraint("articles_job_id_url_hash_key", "articles", type_="unique")
    op.create_unique_constraint("articles_url_hash_key", "articles", ["url_hash"])
