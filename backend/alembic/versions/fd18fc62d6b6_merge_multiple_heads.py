"""merge multiple heads

Revision ID: fd18fc62d6b6
Revises: 005, b34f83e39541
Create Date: 2026-06-01 00:37:04.308356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd18fc62d6b6'
down_revision: Union[str, None] = ('005', 'b34f83e39541')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
