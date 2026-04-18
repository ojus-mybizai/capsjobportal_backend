"""add created_at indexes for list filtering

Revision ID: d5e1c8f4a2b9
Revises: b7a3d2c1f9aa
Create Date: 2026-04-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d5e1c8f4a2b9"
down_revision: Union[str, Sequence[str], None] = "b7a3d2c1f9aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = [
    ("ix_companies_created_at", "companies"),
    ("ix_jobs_created_at", "jobs"),
    ("ix_candidates_created_at", "candidates"),
    ("ix_interviews_created_at", "interviews"),
]


def upgrade() -> None:
    """Upgrade schema."""
    for index_name, table_name in INDEXES:
        op.create_index(index_name, table_name, ["created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    for index_name, table_name in INDEXES:
        op.drop_index(index_name, table_name=table_name)
