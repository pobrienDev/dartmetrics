"""Player request/response contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlayerCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    nickname: str | None = Field(default=None, max_length=100)
    # True creates an unlinked guest opponent; False creates the
    # authenticated user's own (single) player profile.
    is_guest: bool = False


class PlayerUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    nickname: str | None = Field(default=None, max_length=100)

    @field_validator("display_name")
    @classmethod
    def display_name_is_not_null(cls, value: str | None) -> str | None:
        """Omit the field to keep the current name. An explicit null used
        to pass through to the NOT NULL column and surface as a
        misleading 409 CONFLICT; it is a validation error."""
        if value is None:
            raise ValueError("display_name cannot be null; omit it to keep the current name.")
        return value


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    display_name: str
    nickname: str | None
    is_active: bool
    # Set for computer opponents (noob, easy, medium, hard, pro).
    bot_difficulty: str | None = None
    created_at: datetime
