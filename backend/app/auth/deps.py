"""Authentication dependencies.

get_current_user is the guard for protected routes: declare it as a
dependency and the endpoint only runs for a valid, active, logged-in
user — otherwise the request stops with a 401 envelope before the
endpoint body executes.
"""

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import NotAuthenticated
from app.common.security import decode_access_token
from app.db import get_db

# auto_error=False so a missing header raises OUR envelope, not
# FastAPI's default; the scheme still registers in the OpenAPI docs so
# the Swagger UI shows an Authorize button.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise NotAuthenticated("Missing bearer token.")

    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        # Covers expired, tampered, malformed — no detail leaks out.
        raise NotAuthenticated("Invalid or expired token.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("Invalid or expired token.")

    return user
