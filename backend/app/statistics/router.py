"""Statistics HTTP routes."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.statistics import service
from app.statistics.schemas import HeadToHeadResponse, PlayerStatsResponse

router = APIRouter(prefix="/api/v1/players", tags=["statistics"])


@router.get("/{player_id}/stats", response_model=PlayerStatsResponse)
def get_player_stats(
    player_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerStatsResponse:
    """Career statistics derived from raw throw data."""
    return service.player_stats(db, player_id)


@router.get("/{player_id}/head-to-head/{opponent_id}", response_model=HeadToHeadResponse)
def get_head_to_head(
    player_id: uuid.UUID,
    opponent_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HeadToHeadResponse:
    """Completed-match record between two players."""
    return service.head_to_head(db, player_id, opponent_id)
