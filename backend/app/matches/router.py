"""Match HTTP routes — all require authentication."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.matches import service
from app.matches.schemas import (
    MatchCreateRequest,
    MatchStateResponse,
    VisitRequest,
    VisitResponse,
)

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


@router.post("/{match_id}/visits", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
def record_visit(
    match_id: uuid.UUID,
    body: VisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VisitResponse:
    """Record one visit (1-3 darts) for a player in the active leg."""
    turn, match = service.record_match_visit(
        db,
        user=current_user,
        match_id=match_id,
        player_id=body.player_id,
        darts=[dart.to_dart_input() for dart in body.darts],
    )
    state = service.build_match_state(db, match)
    db.commit()
    return {"turn": turn, "state": state}


@router.delete("/{match_id}/visits/latest", response_model=MatchStateResponse)
def undo_latest_visit(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchStateResponse:
    """Undo the most recent visit in the active leg."""
    match = service.undo_latest_visit(db, user=current_user, match_id=match_id)
    state = service.build_match_state(db, match)
    db.commit()
    return state
