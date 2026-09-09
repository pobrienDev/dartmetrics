"""Match HTTP routes — all require authentication."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.matches import service
from app.matches.models import MatchStatus
from app.matches.schemas import (
    BotVisitResponse,
    DartResponse,
    MatchCreateRequest,
    MatchListResponse,
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
    """Create a match (501 or Cricket) against an opponent and start leg 1."""
    match = service.create_match(
        db,
        user=current_user,
        opponent_player_id=body.opponent_player_id,
        best_of_legs=body.best_of_legs,
        starting_player_id=body.starting_player_id,
        game_type=body.game_type,
    )
    state = service.build_match_state(db, match)
    db.commit()
    return state


@router.get("", response_model=MatchListResponse)
def list_matches(
    match_status: MatchStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchListResponse:
    """Your matches (created or playing in), newest first.

    Filter with ?status=in_progress to find matches to resume.
    """
    items, total = service.list_matches(
        db, user=current_user, status=match_status, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{match_id}", response_model=MatchStateResponse)
def get_match(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchStateResponse:
    """Current authoritative state of a match (creator or participants only)."""
    match = service.get_match_for_user(db, current_user, match_id)
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


@router.post(
    "/{match_id}/bot-visit",
    response_model=BotVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_bot_visit(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BotVisitResponse:
    """Have the bot whose turn it is throw its visit.

    409 NOT_BOT_TURN when the active player is a human.
    """
    turn, match, darts = service.record_bot_visit(
        db, user=current_user, match_id=match_id
    )
    state = service.build_match_state(db, match)
    db.commit()
    return {
        "turn": turn,
        "state": state,
        "darts": [DartResponse.from_dart_input(dart) for dart in darts],
    }


@router.get("/{match_id}/summary")
def get_match_summary(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-player performance summary for one match (live or final);
    creator or participants only."""
    from app.statistics.schemas import MatchSummaryResponse
    from app.statistics.service import match_summary

    service.get_match_for_user(db, current_user, match_id)
    return MatchSummaryResponse(**match_summary(db, match_id))


@router.post("/{match_id}/abandon", response_model=MatchStateResponse)
def abandon_match(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchStateResponse:
    """Cancel an in-progress match without recording a winner."""
    match = service.abandon_match(db, user=current_user, match_id=match_id)
    state = service.build_match_state(db, match)
    db.commit()
    return state


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
