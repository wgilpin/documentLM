"""add chat_messages table

Revision ID: a3f2b1c4d5e6
Revises: 1165a94143d4
Create Date: 2026-03-13 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f2b1c4d5e6"
down_revision: Union[str, Sequence[str], None] = "1165a94143d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", name="chatrole"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_chat_messages_document_id_created_at",
        "chat_messages",
        ["document_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chat_messages_document_id_created_at", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.execute("DROP TYPE IF EXISTS chatrole")
