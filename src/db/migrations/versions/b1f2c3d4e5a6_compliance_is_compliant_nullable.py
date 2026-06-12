"""make compliance_reports.is_compliant nullable

A NULL ``is_compliant`` represents a "not checked" report (e.g. a campaign
with no legal guidelines configured). This is distinct from ``False``
(checked and non-compliant) and ``True`` (checked and compliant) and prevents
the API from ever masking an unchecked campaign as compliant.

Revision ID: b1f2c3d4e5a6
Revises: 53a16420a6ea
Create Date: 2026-06-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1f2c3d4e5a6'
down_revision: Union[str, None] = '53a16420a6ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.alter_column(
        'compliance_reports',
        'is_compliant',
        existing_type=sa.Boolean(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Backfill any NULLs to False before reinstating the NOT NULL constraint
    # so the downgrade cannot fail on existing "not checked" rows.
    op.execute(
        "UPDATE compliance_reports SET is_compliant = false "
        "WHERE is_compliant IS NULL"
    )
    op.alter_column(
        'compliance_reports',
        'is_compliant',
        existing_type=sa.Boolean(),
        nullable=False,
    )
