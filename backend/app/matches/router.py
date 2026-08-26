"""Match HTTP routes — all require authentication."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.matches import service
from app.matches.schemas import MatchCreateRequest, MatchStateResponse

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


@router.post("", response_model=MatchStateResponse, status_code=status.HTTP_201_CREATED)
def create_match(
    body: MatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchStateResponse:
    """Create a 501 match against an opponent and start leg 1."""
    match = service.create_match(
        db,
        user=current_user,
        opponent_player_id=body.opponent_player_id,
        best_of_legs=body.best_of_legs,
        starting_player_id=body.starting_player_id,
    )
    state = service.build_match_state(db, match)
    db.commit()
    return state


@router.get("/{match_id}", response_model=MatchStateResponse)
def get_match(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchStateResponse:
    """Current authoritative state of a match."""
    match = service.get_match(db, match_id)
    return service.build_match_state(db, match)
