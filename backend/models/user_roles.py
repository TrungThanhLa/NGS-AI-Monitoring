from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), primary_key=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True)
