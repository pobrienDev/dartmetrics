"""Statistics HTTP routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.statistics import service
from app.statistics.schemas import PlayerStatsResponse

router = APIRouter(prefix="/api/v1/players", tags=["statistics"])


@router.get("/{player_id}/stats", response_model=PlayerStatsResponse)
def get_player_stats(
    player_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerStatsResponse:
    """Career statistics derived from raw throw data."""
    return service.player_stats(db, player_id)
