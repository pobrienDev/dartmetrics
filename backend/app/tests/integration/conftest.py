"""Fixtures for integration tests against real PostgreSQL.

Each test runs inside a transaction on a dedicated connection that is
rolled back afterwards, so tests never pollute the development
database and can run in any order.

Requires the Docker PostgreSQL container ('docker compose up -d') and
an applied migration ('alembic upgrade head'). If the database is not
reachable, integration tests are skipped rather than failed.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import User
from app.matches.models import Leg, LegPlayerState, LegStatus, Match, MatchStatus
from app.players.models import Player

REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set; copy .env.example to .env")
    engine = create_engine(url)
    try:
        with engine.connect():
            pass
    except Exception:
        pytest.skip("PostgreSQL is not reachable; run 'docker compose up -d'")
    return engine


@pytest.fixture
def db_session(engine):
    """A session inside an outer transaction that is always rolled back."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


class MatchSetup:
    """Bundle of freshly created rows for one in-progress 501 match."""

    def __init__(self, session: Session, best_of_legs: int = 1):
        self.user = User(
            email="test@dartmetrics.local", password_hash="x", display_name="Tester"
        )
        self.player1 = Player(display_name="Player One")
        self.player2 = Player(display_name="Player Two")
        session.add_all([self.user, self.player1, self.player2])
        session.flush()

        self.match = Match(
            created_by_user_id=self.user.id,
            player1_id=self.player1.id,
            player2_id=self.player2.id,
            best_of_legs=best_of_legs,
            status=MatchStatus.IN_PROGRESS,
        )
        session.add(self.match)
        session.flush()

        self.leg = Leg(
            match_id=self.match.id,
            leg_number=1,
            starting_player_id=self.player1.id,
            status=LegStatus.IN_PROGRESS,
        )
        session.add(self.leg)
        session.flush()

        self.state1 = LegPlayerState(leg_id=self.leg.id, player_id=self.player1.id)
        self.state2 = LegPlayerState(leg_id=self.leg.id, player_id=self.player2.id)
        session.add_all([self.state1, self.state2])
        session.flush()


@pytest.fixture
def match_setup(db_session):
    return MatchSetup(db_session)
