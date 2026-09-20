"""Player model (Phase 0 spec, sections 9-10.2).

A Player is a darts competitor. user_id is nullable so a registered
user can record matches against guests who have no account.

Bots are guests too (no user) with bot_difficulty set; the bot engine
(app/scoring/bot.py) throws for them. One shared bot exists per
difficulty, so bot statistics and head-to-head records accumulate
like any other player's.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Defined with the bot engine so the scoring package stays framework-free;
# re-exported here because the Player model and its callers use it.
from app.scoring.bot import BotDifficulty


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint(
            "bot_difficulty IS NULL OR bot_difficulty IN "
            "('noob', 'easy', 'medium', 'hard', 'pro')",
            name="bot_difficulty_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Set only for computer opponents; stored as the enum's value.
    bot_difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def is_bot(self) -> bool:
        return self.bot_difficulty is not None

    def __repr__(self) -> str:
        return f"<Player {self.display_name}>"
