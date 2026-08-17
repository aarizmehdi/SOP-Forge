"""
SOP Forge — User & Department ORM models.
Defines organizational hierarchy: users, roles, and departments.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    """User roles matching the PRD target user types."""
    EMPLOYEE = "employee"
    MANAGER = "manager"
    EXECUTIVE = "executive"
    ADMIN = "admin"


class Department(Base):
    """Organizational department."""
    __tablename__ = "departments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    head_user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", use_alter=True),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    head = relationship("User", foreign_keys=[head_user_id], post_update=True)
    members = relationship(
        "User",
        back_populates="department",
        foreign_keys="User.department_id",
    )

    def __repr__(self) -> str:
        return f"<Department {self.name}>"


class User(Base):
    """System user — employee, manager, executive, or admin."""
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    department_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id"),
        nullable=True,
    )
    manager_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    department = relationship("Department", back_populates="members", foreign_keys=[department_id])
    manager = relationship("User", remote_side="User.id", foreign_keys=[manager_id])

    def __repr__(self) -> str:
        return f"<User {self.employee_id} ({self.role.value})>"
