import uuid

from sqlalchemy import Column, Date, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func

from backend.db import Base


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    status = Column(String(50), server_default="pending")
    output_docx = Column(Text)
    output_json = Column(Text)
    error_log = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    completed_at = Column(TIMESTAMP)
