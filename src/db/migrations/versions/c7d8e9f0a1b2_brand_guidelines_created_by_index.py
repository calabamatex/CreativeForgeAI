"""index brand_guidelines.created_by for tenant scoping

Tenant scoping (object-level authorization) filters every non-admin brand
read by ``created_by`` — both the list endpoint's WHERE clause and the
per-object ownership checks. ``campaigns.created_by`` was already indexed in
the baseline schema; this brings ``brand_guidelines`` in line.

Revision ID: c7d8e9f0a1b2
Revises: da96efc5089e
Create Date: 2026-06-12 19:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "da96efc5089e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_index(
        "ix_brand_guidelines_created_by",
        "brand_guidelines",
        ["created_by"],
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index("ix_brand_guidelines_created_by", table_name="brand_guidelines")
