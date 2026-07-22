import uuid

from sqlalchemy import Column, Float, ForeignKey, String, TIMESTAMP, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


VALID_REVIEW_STATUSES = {"NEW", "REVIEWED", "NEED_VERIFY", "VERIFIED", "NOT_RELEVANT", "CASE_CREATED"}


class Article(Base):
    __tablename__ = "articles"
    # UNIQUE(source_id, url_hash) toàn bảng (migration 0021) — thay thế hoàn toàn
    # UNIQUE(job_id, url_hash) [migration 0009] sau khi jobs bị xóa (Phase 7). Dedup
    # toàn cục theo Source, đúng nghĩa duy nhất còn lại của hệ thống (Phase 3 continuous
    # crawl đã dùng cơ chế này, giờ áp dụng cho MỌI dòng, không chỉ dòng job_id IS NULL).
    __table_args__ = (UniqueConstraint("source_id", "url_hash", name="articles_source_id_url_hash_key"),)

    article_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
