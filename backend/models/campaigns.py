import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    campaign_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    objective = Column(Text)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    status = Column(String(50), server_default="DRAFT")
    mode = Column(String(20), server_default="CONTINUOUS")
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP)
    alert_threshold = Column(Integer, server_default="100")
    is_active = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP)
    deleted_at = Column(TIMESTAMP)
