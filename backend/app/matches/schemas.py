"""Match request/response contracts.

MatchStateResponse is THE authoritative scoreboard shape (dev plan
11.1): every endpoint that changes match state returns it, so the
frontend always re-renders from server truth instead of computing
scores locally.
"""

import uuid

from pydantic import BaseModel, Field, field_validator

from app.matches.models import LegStatus, MatchStatus


class MatchCreateRequest(BaseModel):
    opponent_player_id: uuid.UUID
    best_of_legs: int = Field(ge=1, le=21)
    # Defaults to the creator's player when omitted.
    starting_player_id: uuid.UUID | None = None

    @field_validator("best_of_legs")
    @classmethod
    def must_be_odd(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("best_of_legs must be odd (1, 3, 5, ...)")
        return value


class PlayerStateResponse(BaseModel):
    player_id: uuid.UUID
    display_name: str
    legs_won: int
    remaining_score: int | None  # None when no leg is active
    is_active_turn: bool


class LegStateResponse(BaseModel):
    id: uuid.UUID
    leg_number: int
    status: LegStatus
    starting_player_id: uuid.UUID
    winner_player_id: uuid.UUID | None


class MatchStateResponse(BaseModel):
    id: uuid.UUID
    status: MatchStatus
    best_of_legs: int
    legs_required_to_win: int
    winner_player_id: uuid.UUID | None
    players: list[PlayerStateResponse]
    current_leg: LegStateResponse | None
