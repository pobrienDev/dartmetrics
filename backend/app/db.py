"""Database plumbing: declarative base, engine, and session dependency.

The naming convention gives every index/constraint a predictable name
(e.g. uq_users_email, fk_players_user_id_users). Without it, databases
invent their own names, which makes Alembic migrations unable to refer
to constraints reliably when altering or dropping them later.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache
def get_engine() -> Engine:
    """One engine (connection pool) per process, created on first use.

    pool_pre_ping checks a pooled connection is still alive before
    handing it out, so a database restart doesn't surface as a crash
    on the next request.
    """
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed.

    Endpoints/services decide when to commit; anything uncommitted
    when the request ends is rolled back by close().
    """
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
