"""merge multiple heads

Revision ID: b34f83e39541
Revises: 004, 4907f41541f5
Create Date: 2026-05-31 23:48:11.648590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b34f83e39541'
down_revision: Union[str, None] = ('004', '4907f41541f5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
