"""
SOP Forge — User & Department ODM models (Pydantic/MongoDB).
"""

import enum
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class UserRole(str, enum.Enum):
    """User roles matching the PRD target user types."""
    EMPLOYEE = "employee"
    MANAGER = "manager"
    EXECUTIVE = "executive"
    ADMIN = "admin"

class Department(BaseModel):
    """Organizational department."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str | None = None
    head_user_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class User(BaseModel):
    """System user — employee, manager, executive, or admin."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    employee_id: str
    name: str
    email: str
    hashed_password: str
    role: UserRole = UserRole.EMPLOYEE
    department_id: str | None = None
    manager_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
