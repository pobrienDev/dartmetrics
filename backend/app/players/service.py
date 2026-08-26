"""Player use cases.

Ownership rule (dev plan authorization matrix): only the linked user
may edit a player. Guests have no owner and are not editable in the
MVP. One own-profile per account (Phase 0 spec 10.2).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.common.errors import Forbidden, PlayerNotFound, PlayerProfileExists
from app.players.models import Player
from app.players.schemas import PlayerUpdateRequest


def create_player(
    session: Session,
    user: User,
    display_name: str,
    nickname: str | None,
    is_guest: bool,
) -> Player:
    if is_guest:
        player = Player(user_id=None, display_name=display_name, nickname=nickname)
    else:
        existing = session.scalar(select(Player).where(Player.user_id == user.id))
        if existing is not None:
            raise PlayerProfileExists(
                "This account already has a player profile."
            )
        player = Player(user_id=user.id, display_name=display_name, nickname=nickname)

    session.add(player)
    session.flush()
    return player


def list_players(
    session: Session, query: str | None, limit: int
) -> list[Player]:
    """Active players, optionally filtered by name, for opponent pickers."""
    stmt = select(Player).where(Player.is_active.is_(True))
    if query:
        stmt = stmt.where(Player.display_name.ilike(f"%{query}%"))
    return list(session.scalars(stmt.order_by(Player.display_name).limit(limit)))


def get_player(session: Session, player_id: uuid.UUID) -> Player:
    player = session.get(Player, player_id)
    if player is None:
        raise PlayerNotFound(f"Player {player_id} does not exist.")
    return player


def update_player(
    session: Session, user: User, player_id: uuid.UUID, changes: PlayerUpdateRequest
) -> Player:
    player = get_player(session, player_id)

    if player.user_id != user.id:
        raise Forbidden("You can only edit your own player profile.")

    # Only fields the client actually sent; None-able nickname stays
    # settable to None explicitly.
    updates = changes.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(player, field, value)

    session.flush()
    return player
