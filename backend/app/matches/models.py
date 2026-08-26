"""Match and Leg models (Phase 0 spec, sections 9-10.4, 12, 17).

A Match is the contest between exactly two players; a Leg is one race
from 501 to 0 inside it. Database constraints enforce the spec's
invariants where practical so bad states cannot be persisted even by
buggy code.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MatchStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LegStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("player1_id != player2_id", name="players_distinct"),
        CheckConstraint(
            "best_of_legs > 0 AND best_of_legs % 2 = 1", name="best_of_legs_odd"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    player1_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id"), nullable=False
    )
    player2_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id"), nullable=False
    )
    best_of_legs: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, native_enum=False, length=20),
        nullable=False,
        default=MatchStatus.SCHEDULED,
    )
    winner_player_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("players.id"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    legs: Mapped[list["Leg"]] = relationship(
        back_populates="match", order_by="Leg.leg_number"
    )

    @property
    def legs_required_to_win(self) -> int:
        return self.best_of_legs // 2 + 1

    def __repr__(self) -> str:
        return f"<Match {self.id} best-of-{self.best_of_legs} {self.status}>"


class Leg(Base):
    __tablename__ = "legs"
    __table_args__ = (
        UniqueConstraint("match_id", "leg_number", name="uq_legs_match_leg_number"),
        CheckConstraint("leg_number > 0", name="leg_number_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("matches.id"), nullable=False
    )
    leg_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    starting_player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id"), nullable=False
    )
    winner_player_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("players.id"), nullable=True
    )
    status: Mapped[LegStatus] = mapped_column(
        Enum(LegStatus, native_enum=False, length=20),
        nullable=False,
        default=LegStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    match: Mapped[Match] = relationship(back_populates="legs")

    def __repr__(self) -> str:
        return f"<Leg {self.leg_number} of match {self.match_id} {self.status}>"
