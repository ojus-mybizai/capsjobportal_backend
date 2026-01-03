"""add candidate created_by

Revision ID: c2f1b4a9d1c
Revises: 98621c511ead
Create Date: 2026-01-03 03:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.base


# revision identifiers, used by Alembic.
revision: str = "c2f1b4a9d1c"
down_revision: Union[str, Sequence[str], None] = "98621c511ead"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "candidates",
        sa.Column("created_by", app.models.base.GUID(), nullable=True),
    )
    op.create_foreign_key(
        "candidates_created_by_fkey",
        "candidates",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_index("ix_candidates_created_by", "candidates", ["created_by"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_candidates_created_by", table_name="candidates")
    op.drop_constraint("candidates_created_by_fkey", "candidates", type_="foreignkey")
    op.drop_column("candidates", "created_by")
