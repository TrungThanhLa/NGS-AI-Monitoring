import uuid

from sqlalchemy import Column, Float, ForeignKey, String, TIMESTAMP, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


VALID_REVIEW_STATUSES = {"NEW", "REVIEWED", "NEED_VERIFY", "VERIFIED", "NOT_RELEVANT", "CASE_CREATED"}


class Article(Base):
    __tablename__ = "articles"
    # Composite UNIQUE (job_id, url_hash) — không phải unique đơn trên url_hash: mỗi
    # job crawl/phân tích độc lập, cùng 1 URL có thể xuất hiện ở nhiều job khác nhau,
    # nhưng vẫn chống trùng NGAY Ở TẦNG DB nếu cùng 1 job vô tình insert trùng URL
    # (lưới an toàn dự phòng, bổ sung cho check seen_urls ở report_job.py).
    __table_args__ = (UniqueConstraint("job_id", "url_hash", name="articles_job_id_url_hash_key"),)

    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id"))
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)
    title = Column(Text)
    content_raw = Column(Text)
    author = Column(Text)
    published_at = Column(TIMESTAMP)
    crawled_at = Column(TIMESTAMP, server_default=func.now())
    status = Column(String(50), server_default="pending_analysis")
    crawl_duration_seconds = Column(Float)

    # Trạng thái đánh giá NGHIỆP VỤ (BR-CONTENT-02) — tách biệt hoàn toàn khỏi `status`
    # kỹ thuật ở trên. Chỉ ANALYST/MANAGER được sửa (BR-CONTENT-03, enforce qua
    # permission content.review, không cần check role riêng trong code).
    review_status = Column(String(50), server_default="NEW", nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"))
    reviewed_at = Column(TIMESTAMP)
    reviewer_note = Column(Text)
    # Cột dự phòng cho DELETE endpoint ở phase sau (BR-CONTENT-04) — hiện tại luôn NULL,
    # chưa có endpoint nào ghi giá trị.
    deleted_at = Column(TIMESTAMP)
