import uuid

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func

from backend.db import Base


class ArticleAnalysis(Base):
    __tablename__ = "article_analysis"

    analysis_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.article_id"))
    topics = Column(ARRAY(Text), nullable=False)
    keywords = Column(ARRAY(Text), server_default="{}")
    sentiment = Column(String(20))
    emotion = Column(String(20))
    confidence = Column(Float)
    needs_review = Column(Boolean, server_default="false")
    summary = Column(Text)
    # Version của prompt (backend/ai/prompts/vN.py) đã sinh ra bản phân tích này —
    # cần để không lẫn kết quả giữa các lần tinh chỉnh prompt ở Slice 3+.
    prompt_version = Column(Integer, nullable=False)
    # Tên model AI đã dùng (VD "qwen3:8b") — cần để không lẫn dữ liệu khi sau này đổi
    # model trên server GPU (xem CLAUDE.md, Slice 3).
    ai_model = Column(String(255), nullable=False)
    analyzed_at = Column(TIMESTAMP, server_default=func.now())
    analysis_duration_seconds = Column(Float)
