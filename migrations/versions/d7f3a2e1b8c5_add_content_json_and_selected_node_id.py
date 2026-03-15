"""add content_json to documents and selected_node_id to comments

Revision ID: d7f3a2e1b8c5
Revises: c4e8f2a1b9d7
Create Date: 2026-03-14 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7f3a2e1b8c5"
down_revision: str | None = "c4e8f2a1b9d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_json", sa.Text(), nullable=True))
    op.add_column("comments", sa.Column("selected_node_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "content_json")
    op.drop_column("comments", "selected_node_id")
