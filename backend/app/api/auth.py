"""
SOP Forge — Auth API router.
Login, token refresh, and user profile endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    create_access_token,
    get_current_user,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserProfile

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a user and return a JWT access token."""
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(
        user_id=str(user.id),
        role=user.role.value,
        employee_id=user.employee_id,
    )

    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        role=user.role.value,
        employee_id=user.employee_id,
        name=user.name,
    )


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    dept_name = None
    if current_user.department:
        dept_name = current_user.department.name

    return UserProfile(
        id=current_user.id,
        employee_id=current_user.employee_id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        department_name=dept_name,
        is_active=current_user.is_active,
    )
