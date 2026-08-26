"""Auth use cases (dev plan: services layer)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import EmailAlreadyRegistered
from app.common.security import hash_password


def register_user(
    session: Session, email: str, password: str, display_name: str
) -> User:
    """Create a new user account with a hashed password.

    Emails are normalized to lowercase so Pat@Example.com and
    pat@example.com are the same account. Caller commits.
    """
    normalized_email = email.strip().lower()

    existing = session.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if existing is not None:
        raise EmailAlreadyRegistered(f"{normalized_email} is already registered.")

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    session.add(user)
    session.flush()
    return user
