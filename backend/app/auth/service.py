"""Auth use cases (dev plan: services layer)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import EmailAlreadyRegistered, InvalidCredentials
from app.common.security import hash_password, verify_password

# Verified against when the email is unknown, so "no such user" takes as
# long as "wrong password" and attackers can't probe which emails exist.
_DUMMY_HASH = hash_password("timing-equalizer")


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


def authenticate_user(session: Session, email: str, password: str) -> User:
    """Return the user for valid credentials.

    Deliberately raises the SAME error for unknown email, wrong
    password, and deactivated account — the response must not reveal
    which part failed.
    """
    normalized_email = email.strip().lower()
    user = session.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )

    if user is None:
        verify_password(password, _DUMMY_HASH)  # burn the same time anyway
        raise InvalidCredentials("Incorrect email or password.")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentials("Incorrect email or password.")

    if not user.is_active:
        raise InvalidCredentials("Incorrect email or password.")

    return user
