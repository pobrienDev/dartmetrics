"""Match persistence models (Phase 0 spec, sections 9-12, 17).

A Match is the contest between exactly two players; a Leg is one race
from 501 to 0 inside it; LegPlayerState tracks each player's remaining
score; a Turn is one visit of up to three darts; a DartThrow is the
most granular scoring event. Database constraints enforce the spec's
invariants where practical so bad states cannot be persisted even by
buggy code.

One invariant — "only one winning dart per leg" — spans two tables and
cannot be a simple constraint; the turn service is responsible for it.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
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
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="leg", order_by="Turn.turn_number"
    )

    def __repr__(self) -> str:
        return f"<Leg {self.leg_number} of match {self.match_id} {self.status}>"


class LegPlayerState(Base):
    """Per-player live state within a leg (spec section 10.5).

    remaining_score can never persist as negative or exactly 1 — the
    two states double-out rules make impossible after a completed turn.
    """

    __tablename__ = "leg_player_states"
    __table_args__ = (
        UniqueConstraint("leg_id", "player_id", name="uq_leg_player_states_leg_player"),
        CheckConstraint(
            "remaining_score >= 0 AND remaining_score != 1",
            name="remaining_score_legal",
        ),
        CheckConstraint("darts_thrown >= 0", name="darts_thrown_non_negative"),
        CheckConstraint("turns_taken >= 0", name="turns_taken_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    leg_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("legs.id"), nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id"), nullable=False
    )
    remaining_score: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=501
    )
    darts_thrown: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turns_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<LegPlayerState player={self.player_id} remaining={self.remaining_score}>"


class Turn(Base):
    """One visit by one player (spec section 10.6).

    The check constraints encode the turn-level rules table (spec
    section 15): a bust turn changes nothing and scores 0; a normal or
    checkout turn scores exactly start minus end; a checkout ends at 0.
    """

    __tablename__ = "turns"
    __table_args__ = (
        UniqueConstraint("leg_id", "turn_number", name="uq_turns_leg_turn_number"),
        CheckConstraint("turn_number > 0", name="turn_number_positive"),
        CheckConstraint(
            "points_scored >= 0 AND points_scored <= 180", name="points_in_range"
        ),
        CheckConstraint("NOT (is_bust AND is_checkout)", name="bust_xor_checkout"),
        CheckConstraint(
            "(is_bust AND turn_end_score = turn_start_score AND points_scored = 0)"
            " OR (NOT is_bust AND points_scored = turn_start_score - turn_end_score)",
            name="bust_preserves_score",
        ),
        CheckConstraint(
            "NOT is_checkout OR turn_end_score = 0", name="checkout_ends_at_zero"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    leg_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("legs.id"), nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("players.id"), nullable=False
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    turn_start_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    turn_end_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    points_scored: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_bust: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_checkout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    leg: Mapped[Leg] = relationship(back_populates="turns")
    dart_throws: Mapped[list["DartThrow"]] = relationship(
        back_populates="turn", order_by="DartThrow.dart_number"
    )

    def __repr__(self) -> str:
        return (
            f"<Turn {self.turn_number} player={self.player_id} "
            f"{self.turn_start_score}->{self.turn_end_score}>"
        )


class DartThrow(Base):
    """One physical dart (spec section 10.7) — the most granular event.

    segment is stored as text per the spec: '1'-'20', '25' for the
    bull, or 'MISS'. multiplier is 0 miss, 1 single, 2 double, 3
    triple; the inner bull is segment '25' with multiplier 2.
    """

    __tablename__ = "dart_throws"
    __table_args__ = (
        UniqueConstraint("turn_id", "dart_number", name="uq_dart_throws_turn_dart"),
        CheckConstraint("dart_number BETWEEN 1 AND 3", name="dart_number_1_to_3"),
        CheckConstraint("multiplier BETWEEN 0 AND 3", name="multiplier_0_to_3"),
        CheckConstraint("score >= 0 AND score <= 60", name="score_in_range"),
        CheckConstraint("NOT is_winning_dart OR is_double", name="winning_dart_is_double"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    turn_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("turns.id"), nullable=False
    )
    dart_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    segment: Mapped[str] = mapped_column(String(4), nullable=False)
    multiplier: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_double: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_checkout_attempt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_winning_dart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    turn: Mapped[Turn] = relationship(back_populates="dart_throws")

    def __repr__(self) -> str:
        return f"<DartThrow {self.dart_number}: {self.segment} x{self.multiplier} = {self.score}>"
