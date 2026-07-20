from sqlalchemy import Column, ForeignKey, String, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    setting_key = Column(String(255), primary_key=True)
    setting_value = Column(Text)
    data_type = Column(String(50))
    description = Column(Text)
    updated_at = Column(TIMESTAMP)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"))
