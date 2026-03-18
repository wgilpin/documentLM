"""add file_path to sources

Revision ID: f1a2b3c4d5e6
Revises: e9a1c3f5b2d8
Create Date: 2026-03-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "17ae9dac3e73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("file_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "file_path")
