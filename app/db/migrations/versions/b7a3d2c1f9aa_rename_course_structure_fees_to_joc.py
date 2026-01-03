"""rename course_structure_fees to joc_structure_fees

Revision ID: b7a3d2c1f9aa
Revises: c2f1b4a9d1c
Create Date: 2026-01-03 04:40:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7a3d2c1f9aa"
down_revision: Union[str, Sequence[str], None] = "c2f1b4a9d1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("course_structure_fees", "joc_structure_fees")

    op.execute(
        "ALTER INDEX IF EXISTS ix_course_structure_fees_candidate_id RENAME TO ix_joc_structure_fees_candidate_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS ix_joc_structure_fees_candidate_id RENAME TO ix_course_structure_fees_candidate_id"
    )

    op.rename_table("joc_structure_fees", "course_structure_fees")
