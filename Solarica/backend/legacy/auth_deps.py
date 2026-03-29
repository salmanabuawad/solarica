"""FastAPI auth dependencies: get_current_user and role guards."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth_utils import decode_token
from database import get_connection

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Decode the Bearer JWT and return a user dict with global_roles list.
    Raises 401 if the token is missing, invalid, or the user is inactive.
    """
    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.full_name, u.email, u.is_active, r.role_code
                FROM users u
                LEFT JOIN user_global_roles ugr ON ugr.user_id = u.id
                LEFT JOIN roles r ON r.id = ugr.role_id
                WHERE u.id = %s
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    first = rows[0]
    is_active = bool(first[3])
    if not is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    return {
        "id": first[0],
        "full_name": first[1],
        "email": first[2],
        "global_roles": [r[4] for r in rows if r[4]],
    }


class RequireGlobalRole:
    """
    Dependency factory that ensures the current user holds at least one of the
    specified global roles.  Usage::

        @router.post("/rules", dependencies=[Depends(RequireGlobalRole("manager"))])
        def create_rule(...): ...

        # Or capture the user object:
        @router.post("/rules")
        def create_rule(user=Depends(RequireGlobalRole("manager"))): ...
    """

    def __init__(self, *codes: str) -> None:
        self.codes = set(codes)

    def __call__(self, user: dict = Depends(get_current_user)) -> dict:
        if not self.codes.intersection(user["global_roles"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user
