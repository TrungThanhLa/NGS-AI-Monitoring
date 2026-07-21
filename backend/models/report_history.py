import uuid

from sqlalchemy import Column, ForeignKey, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class ReportHistory(Base):
    __tablename__ = "report_history"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.job_id"))  # [SẼ XÓA ở Task 14]
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"))
    format = Column(String(20), server_default="docx")
    file_path = Column(Text, nullable=False)
    status = Column(String(20), server_default="completed")
    error_log = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
