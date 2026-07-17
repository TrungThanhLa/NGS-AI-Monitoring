import uuid

from sqlalchemy import Boolean, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from backend.db import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), unique=True)
    full_name = Column(String(255))
    password_hash = Column(Text, nullable=False)
    status = Column(String(30), server_default="ACTIVE")
    failed_login_count = Column(Integer, server_default="0")
    locked_until = Column(TIMESTAMP)
    last_login_at = Column(TIMESTAMP)
    is_active = Column(Boolean, server_default="true")
    phone = Column(String(20))
    avatar_path = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP)
    deleted_at = Column(TIMESTAMP)
