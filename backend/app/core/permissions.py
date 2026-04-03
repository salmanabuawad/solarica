"""
Role-based access control helpers for FastAPI routes.
"""
from fastapi import Depends, HTTPException, status
from app.core.security import get_current_user


def require_roles(*allowed_roles: str):
    """
    Factory that returns a FastAPI dependency checking user role.
    Usage: Depends(require_roles("admin", "manager"))
    """
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        role = current_user.get("role", "")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not allowed. Required: {list(allowed_roles)}",
            )
        return current_user
    return _check


def any_authenticated():
    """Dependency that just requires any valid JWT."""
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        return current_user
    return _check
