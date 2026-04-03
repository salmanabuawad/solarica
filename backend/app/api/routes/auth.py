from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.core.permissions import require_roles
from app.repositories import user_repo, audit_repo
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead

router = APIRouter()


def _user_to_read(user) -> UserRead:
    return UserRead(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = user_repo.authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    effective_role = payload.role if payload.role else user.role
    token = create_access_token({
        "sub": user.username,
        "id": str(user.id),
        "role": effective_role,
        "display_name": user.display_name,
    })
    audit_repo.log_action(db, actor_username=user.username, actor_role=effective_role,
                          action="login", entity_type="user", entity_id=user.id)
    db.commit()
    return TokenResponse(
        access_token=token,
        user=UserRead(id=str(user.id), username=user.username,
                      display_name=user.display_name, role=effective_role),
    )


@router.post("/register", response_model=UserRead)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin")),
):
    if user_repo.get_by_username(db, payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"Username '{payload.username}' already exists")
    user = user_repo.create_user(
        db,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        role=payload.role,
    )
    audit_repo.log_action(db, actor_username=current_user["username"], actor_role=current_user["role"],
                          action="register_user", entity_type="user", entity_id=user.id,
                          detail=f"Created user: {user.username} role={user.role}")
    db.commit()
    return _user_to_read(user)


@router.get("/me", response_model=UserRead)
def me(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    username = current_user.get("username") or current_user.get("sub")
    user = user_repo.get_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_read(user)


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin")),
):
    return [_user_to_read(u) for u in user_repo.list_users(db)]
