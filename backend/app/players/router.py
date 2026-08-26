"""Player HTTP routes — all require authentication."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.models import User
from app.db import get_db
from app.players import service
from app.players.schemas import (
    PlayerCreateRequest,
    PlayerResponse,
    PlayerUpdateRequest,
)

router = APIRouter(prefix="/api/v1/players", tags=["players"])


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
def create_player(
    body: PlayerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerResponse:
    """Create the authenticated user's player profile, or a guest opponent."""
    player = service.create_player(
        db,
        user=current_user,
        display_name=body.display_name,
        nickname=body.nickname,
        is_guest=body.is_guest,
    )
    db.commit()
    return player


@router.get("", response_model=list[PlayerResponse])
def list_players(
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlayerResponse]:
    """Active players for opponent selection, optionally filtered by name."""
    return service.list_players(db, query=q, limit=limit)


@router.get("/{player_id}", response_model=PlayerResponse)
def get_player(
    player_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerResponse:
    return service.get_player(db, player_id)


@router.patch("/{player_id}", response_model=PlayerResponse)
def update_player(
    player_id: uuid.UUID,
    body: PlayerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlayerResponse:
    """Edit your own player profile."""
    player = service.update_player(db, current_user, player_id, body)
    db.commit()
    return player
