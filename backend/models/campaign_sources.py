from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class CampaignSource(Base):
    __tablename__ = "campaign_sources"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.source_id"), primary_key=True)
