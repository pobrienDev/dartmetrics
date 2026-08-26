"""Match request/response contracts.

MatchStateResponse is THE authoritative scoreboard shape (dev plan
11.1): every endpoint that changes match state returns it, so the
frontend always re-renders from server truth instead of computing
scores locally.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.matches.models import GameType, LegStatus, MatchStatus
from app.scoring.domain import DartInput, Multiplier


class MatchCreateRequest(BaseModel):
    opponent_player_id: uuid.UUID
    best_of_legs: int = Field(ge=1, le=21)
    game_type: GameType = GameType.X01
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
    remaining_score: int | None  # x01 only; None otherwise
    marks: dict[int, int] | None = None  # cricket only: target -> 0..3
    is_active_turn: bool


class LegStateResponse(BaseModel):
    id: uuid.UUID
    leg_number: int
    status: LegStatus
    starting_player_id: uuid.UUID
    winner_player_id: uuid.UUID | None


class MatchStateResponse(BaseModel):
    id: uuid.UUID
    game_type: GameType
    status: MatchStatus
    best_of_legs: int
    legs_required_to_win: int
    winner_player_id: uuid.UUID | None
    players: list[PlayerStateResponse]
    current_leg: LegStateResponse | None


class MatchPlayerSummary(BaseModel):
    player_id: uuid.UUID
    display_name: str
    legs_won: int


class MatchSummary(BaseModel):
    id: uuid.UUID
    status: MatchStatus
    best_of_legs: int
    winner_player_id: uuid.UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    players: list[MatchPlayerSummary]


class MatchListResponse(BaseModel):
    items: list[MatchSummary]
    total: int
    limit: int
    offset: int


class DartRequest(BaseModel):
    """One dart as JSON, e.g. {"segment": 20, "multiplier": "triple"}
    or {"multiplier": "miss"}. Board legality is checked here, so an
    impossible dart (triple 25, double 21) is a 422 validation error."""

    segment: int | None = None
    multiplier: Literal["miss", "single", "double", "triple"]

    @model_validator(mode="after")
    def must_be_a_real_dart(self) -> "DartRequest":
        self.to_dart_input()  # raises ValueError -> 422 with the message
        return self

    def to_dart_input(self) -> DartInput:
        return DartInput(
            segment=self.segment, multiplier=Multiplier[self.multiplier.upper()]
        )


class VisitRequest(BaseModel):
    player_id: uuid.UUID
    darts: list[DartRequest] = Field(min_length=1, max_length=3)


class TurnSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    player_id: uuid.UUID
    turn_number: int
    turn_start_score: int
    turn_end_score: int
    points_scored: int
    is_bust: bool
    is_checkout: bool


class VisitResponse(BaseModel):
    turn: TurnSummary
    state: MatchStateResponse
