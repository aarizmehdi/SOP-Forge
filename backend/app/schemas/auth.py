"""
SOP Forge — Auth schemas.
Pydantic models for authentication endpoints.
"""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Login credentials."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=4)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    employee_id: str
    name: str


class UserProfile(BaseModel):
    """Current user profile."""
    id: UUID
    employee_id: str
    name: str
    email: str
    role: UserRole
    department_name: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}
