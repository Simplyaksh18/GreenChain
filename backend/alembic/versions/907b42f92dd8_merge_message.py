"""merge message

Revision ID: 907b42f92dd8
Revises: 008_custodial_model, 515776545c95
Create Date: 2026-06-03 13:36:02.117654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '907b42f92dd8'
down_revision: Union[str, None] = ('008_custodial_model', '515776545c95')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
