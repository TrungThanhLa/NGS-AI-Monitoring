from sqlalchemy import Column, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class CampaignArticle(Base):
    __tablename__ = "campaign_articles"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), primary_key=True)
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.article_id"), primary_key=True)
    matched_keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.keyword_id"))
    matched_at = Column(TIMESTAMP, server_default=func.now())
