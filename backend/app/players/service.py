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
from app.players.models import BotDifficulty, Player
from app.players.schemas import PlayerUpdateRequest


def create_player(
    session: Session,
    user: User,
    display_name: str,
    nickname: str | None,
    is_guest: bool,
) -> Player:
    if is_guest:
        # A guest is scored by, listed to, and readable by its creator only.
        player = Player(
            user_id=None,
            created_by_user_id=user.id,
            display_name=display_name,
            nickname=nickname,
        )
    else:
        existing = session.scalar(select(Player).where(Player.user_id == user.id))
        if existing is not None:
            raise PlayerProfileExists(
                "This account already has a player profile."
            )
        player = Player(
            user_id=user.id,
            created_by_user_id=user.id,
            display_name=display_name,
            nickname=nickname,
        )

    session.add(player)
    session.flush()
    return player


BOT_DISPLAY_NAMES: dict[BotDifficulty, str] = {
    BotDifficulty.NOOB: "Noob Bot",
    BotDifficulty.EASY: "Easy Bot",
    BotDifficulty.MEDIUM: "Medium Bot",
    BotDifficulty.HARD: "Hard Bot",
    BotDifficulty.PRO: "Pro Bot",
}


def list_bots(session: Session) -> list[Player]:
    """The five shared bot opponents, easiest first. The rows are created
    by the migration that added the one-bot-per-difficulty index, so
    this is a plain read (GET must not write)."""
    by_difficulty = {
        p.bot_difficulty: p
        for p in session.scalars(select(Player).where(Player.bot_difficulty.is_not(None)))
    }
    return [by_difficulty[d.value] for d in BotDifficulty if d.value in by_difficulty]


def list_players(
    session: Session, user: User, query: str | None, limit: int
) -> list[Player]:
    """The caller's own active guests, optionally filtered by name, for
    the opponent picker. Other accounts' guests are theirs to see, and
    registered profiles cannot be chosen as opponents (see
    matches.service.create_match). Bots are listed by list_bots."""
    stmt = select(Player).where(
        Player.is_active.is_(True),
        Player.bot_difficulty.is_(None),
        Player.user_id.is_(None),
        Player.created_by_user_id == user.id,
    )
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
