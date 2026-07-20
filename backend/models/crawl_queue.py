import uuid

from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class CrawlQueue(Base):
    __tablename__ = "crawl_queue"
    __table_args__ = (UniqueConstraint("source_id", "url_hash", name="crawl_queue_source_id_url_hash_key"),)

    queue_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"))
    url = Column(Text, nullable=False)
    url_hash = Column(String(64), nullable=False)
    status = Column(String(20), server_default="pending")
    retry_count = Column(Integer, server_default="0")
    discovered_at = Column(TIMESTAMP, server_default=func.now())
    fetched_at = Column(TIMESTAMP)
