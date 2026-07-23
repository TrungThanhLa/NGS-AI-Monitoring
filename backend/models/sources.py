import uuid

from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from backend.db import Base


class Source(Base):
    __tablename__ = "sources"

    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=False, unique=True)
    group_name = Column(String(255), nullable=False)
    source_group = Column(String(255))
    sitemap_url = Column(String)
    listing_url = Column(String)
    parsing_rules = Column(JSONB, server_default="{}")
    is_active = Column(Boolean, server_default="true")
    crawl_frequency = Column(Integer, server_default="1800")
    last_crawled_at = Column(TIMESTAMP)
    status = Column(String(30), server_default="ACTIVE")
    consecutive_error_count = Column(Integer, server_default="0")
    created_at = Column(TIMESTAMP, server_default=func.now())
    # "Mốc nước cao nhất" Discover đã chắc chắn quét xong cho Nguồn này — dùng để quyết
    # định có cần "quét bù" (backfill) khi 1 Campaign CONTINUOUS mới cần dữ liệu xa hơn
    # mốc này hay không (xem continuous_crawl.py discover_source_urls). Không bao giờ
    # co lại/nới gần hơn hiện tại — chỉ tiến xa hơn về quá khứ.
    discover_backfilled_from = Column(TIMESTAMP)
