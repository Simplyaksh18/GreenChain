"""merge multiple heads

Revision ID: 0216d02ec9fb
Revises: 006, fd18fc62d6b6
Create Date: 2026-06-01 01:35:57.405619

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0216d02ec9fb'
down_revision: Union[str, Sequence[str], None] = ('006', 'fd18fc62d6b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
