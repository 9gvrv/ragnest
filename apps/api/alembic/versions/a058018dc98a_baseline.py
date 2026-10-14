"""baseline

Revision ID: a058018dc98a
Revises: 736e318369b1
Create Date: 2026-10-14 15:45:02.915893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a058018dc98a'
down_revision: Union[str, Sequence[str], None] = '736e318369b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
