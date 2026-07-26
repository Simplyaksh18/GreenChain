"""merge multiple heads

Revision ID: 515776545c95
Revises: 007, 0216d02ec9fb
Create Date: 2026-06-01 13:05:23.008103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '515776545c95'
down_revision: Union[str, None] = ('007', '0216d02ec9fb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
