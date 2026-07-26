"""merge multiple heads

Revision ID: 30cb15c1a5cb
Revises: 002, dc13f9085d58
Create Date: 2026-05-31 20:29:18.181200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30cb15c1a5cb'
down_revision: Union[str, None] = ('002', 'dc13f9085d58')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
