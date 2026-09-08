"""add bot players: players.bot_difficulty

Revision ID: 3c9d2b7e5a10
Revises: 1f4e6601cae7
Create Date: 2026-09-08 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c9d2b7e5a10'
down_revision: Union[str, Sequence[str], None] = '1f4e6601cae7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('players', sa.Column('bot_difficulty', sa.String(length=10), nullable=True))
    op.create_check_constraint(
        op.f('ck_players_bot_difficulty_valid'),
        'players',
        "bot_difficulty IS NULL OR bot_difficulty IN ('noob', 'easy', 'medium', 'hard', 'pro')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ck_players_bot_difficulty_valid'), 'players', type_='check')
    op.drop_column('players', 'bot_difficulty')
