"""
SOP Forge — Auth API router (MongoDB).
Login, token refresh, and user profile endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

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
async def login(credentials: LoginRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Authenticate a user and return a JWT access token."""
    user_dict = await db.users.find_one({"email": credentials.email})

    if user_dict is None or not verify_password(credentials.password, user_dict["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = User(**user_dict)

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
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get the current user's profile."""
    dept_name = None
    if current_user.department_id:
        dept = await db.departments.find_one({"id": current_user.department_id})
        if dept:
            dept_name = dept.get("name")

    return UserProfile(
        id=current_user.id,
        employee_id=current_user.employee_id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        department_name=dept_name,
        is_active=current_user.is_active,
    )
