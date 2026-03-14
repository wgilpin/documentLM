"""add overview to documents

Revision ID: c4e8f2a1b9d7
Revises: a3f2b1c4d5e6
Create Date: 2026-03-14 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8f2a1b9d7"
down_revision: str | None = "a3f2b1c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("overview", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "overview")
