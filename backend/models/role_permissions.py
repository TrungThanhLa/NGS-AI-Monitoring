from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.db import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.role_id", ondelete="RESTRICT"), primary_key=True)
    permission_id = Column(
        UUID(as_uuid=True), ForeignKey("permissions.permission_id", ondelete="RESTRICT"), primary_key=True
    )
