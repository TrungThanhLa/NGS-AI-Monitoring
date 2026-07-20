from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class CampaignKeyword(Base):
    __tablename__ = "campaign_keywords"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.keyword_id"), primary_key=True)
