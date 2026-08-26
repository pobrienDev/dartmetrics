"""Auth HTTP routes (dev plan: routes layer — HTTP concerns only)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.schemas import RegisterRequest, UserResponse
from app.db import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    """Create a new user account."""
    user = service.register_user(
        db, email=body.email, password=body.password, display_name=body.display_name
    )
    db.commit()
    return user
