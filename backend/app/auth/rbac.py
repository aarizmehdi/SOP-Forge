"""
SOP Forge — Role-Based Access Control (RBAC) module.
Provides FastAPI dependencies for role-gated endpoint access.
Role hierarchy: admin > executive > manager > employee
"""

from functools import wraps

from fastapi import Depends, HTTPException, status

from app.auth.jwt import get_current_user
from app.models.user import User, UserRole

# Role hierarchy — higher index = higher authority
ROLE_HIERARCHY = {
    UserRole.EMPLOYEE: 0,
    UserRole.MANAGER: 1,
    UserRole.EXECUTIVE: 2,
    UserRole.ADMIN: 3,
}


def has_minimum_role(user_role: UserRole, required_role: UserRole) -> bool:
    """Check if a user's role meets or exceeds the required role level."""
    return ROLE_HIERARCHY.get(user_role, -1) >= ROLE_HIERARCHY.get(required_role, 999)


def require_role(minimum_role: UserRole):
    """
    FastAPI dependency factory that enforces minimum role access.
    
    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint():
            ...
    
    Or as a parameter dependency:
        async def endpoint(user: User = Depends(require_role(UserRole.MANAGER))):
            ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_minimum_role(current_user.role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {minimum_role.value} or higher.",
            )
        return current_user

    return role_checker


# ── Convenience Dependencies ──
require_employee = require_role(UserRole.EMPLOYEE)
require_manager = require_role(UserRole.MANAGER)
require_executive = require_role(UserRole.EXECUTIVE)
require_admin = require_role(UserRole.ADMIN)
