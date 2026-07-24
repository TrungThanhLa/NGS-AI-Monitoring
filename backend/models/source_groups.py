import uuid

from sqlalchemy import Boolean, Column, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class SourceGroup(Base):
    __tablename__ = "source_groups"

    group_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, server_default="true")
    created_at = Column(TIMESTAMP, server_default=func.now())
