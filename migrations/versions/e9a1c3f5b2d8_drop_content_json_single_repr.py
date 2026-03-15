"""drop content_json — single TipTap JSON representation in content column

Revision ID: e9a1c3f5b2d8
Revises: d7f3a2e1b8c5
Create Date: 2026-03-14 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9a1c3f5b2d8"
down_revision: str | None = "d7f3a2e1b8c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("documents", "content_json")
    op.execute("UPDATE documents SET content = ''")


def downgrade() -> None:
    op.add_column("documents", sa.Column("content_json", sa.Text(), nullable=True))
