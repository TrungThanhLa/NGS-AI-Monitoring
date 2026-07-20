from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class CampaignArticleKeyword(Base):
    __tablename__ = "campaign_article_keywords"
    __table_args__ = (
        ForeignKeyConstraint(
            ["campaign_id", "article_id"],
            ["campaign_articles.campaign_id", "campaign_articles.article_id"],
            name="campaign_article_keywords_campaign_article_fkey",
        ),
    )

    campaign_id = Column(UUID(as_uuid=True), primary_key=True)
    article_id = Column(UUID(as_uuid=True), primary_key=True)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.keyword_id"), primary_key=True)
