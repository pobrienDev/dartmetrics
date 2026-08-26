"""Auth request/response contracts (dev plan: schemas layer).

Pydantic models define what crosses the HTTP boundary — deliberately
separate from the SQLAlchemy models so the API contract and the
database schema can evolve independently. UserResponse contains no
password field of any kind, so a hash can never leak by accident.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class UserResponse(BaseModel):
    # from_attributes lets FastAPI build this straight from the ORM User
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    is_active: bool
    created_at: datetime
