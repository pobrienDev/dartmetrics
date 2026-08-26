"""Auth HTTP routes (dev plan: routes layer — HTTP concerns only)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.common.security import create_access_token
from app.db import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# The plan's catalog puts /me at /api/v1/me, not under /auth
me_router = APIRouter(prefix="/api/v1", tags=["auth"])


@me_router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """The authenticated user's own account."""
    return current_user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    """Create a new user account."""
    user = service.register_user(
        db, email=body.email, password=body.password, display_name=body.display_name
    )
    db.commit()
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange valid credentials for a bearer access token."""
    user = service.authenticate_user(db, email=body.email, password=body.password)
    return TokenResponse(access_token=create_access_token(user.id))
