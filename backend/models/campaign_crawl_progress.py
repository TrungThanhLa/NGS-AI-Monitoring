from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class CampaignCrawlProgress(Base):
    __tablename__ = "campaign_crawl_progress"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), primary_key=True)
    total_urls = Column(Integer)
    done_urls = Column(Integer, server_default="0")
    status = Column(String(20), server_default="pending")
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
