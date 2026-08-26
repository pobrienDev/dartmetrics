"""Statistics response contracts.

Percentages and averages are None (JSON null) when the underlying
sample is empty — the spec is explicit that N/A must never be shown
as 0% (Appendix C).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class HeadToHeadSide(BaseModel):
    player_id: uuid.UUID
    display_name: str
    matches_won: int
    legs_won: int


class HeadToHeadResponse(BaseModel):
    player: HeadToHeadSide
    opponent: HeadToHeadSide
    matches_played: int
    last_played_at: datetime | None = None


class PlayerStatsResponse(BaseModel):
    player_id: uuid.UUID
    display_name: str

    matches_played: int
    matches_won: int
    win_percentage: float | None

    legs_played: int
    legs_won: int
    leg_win_percentage: float | None
    best_leg_darts: int | None

    total_darts: int
    three_dart_average: float | None
    first_nine_average: float | None

    highest_visit: int | None
    count_100_plus: int
    count_140_plus: int
    count_180: int

    checkout_attempts: int
    checkout_successes: int
    checkout_percentage: float | None
