"""initial schema

Revision ID: 1165a94143d4
Revises: 
Create Date: 2026-03-13 14:36:39.777790

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql


# revision identifiers, used by Alembic.
revision: str = '1165a94143d4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "documents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.Enum("url", "pdf", "note", name="sourcetype"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selection_start", sa.Integer, nullable=False),
        sa.Column("selection_end", sa.Integer, nullable=False),
        sa.Column("selected_text", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.Enum("open", "resolved", name="commentstatus"), nullable=False,
                  server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )

    op.create_table(
        "suggestions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("comment_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_text", sa.Text, nullable=False),
        sa.Column("suggested_text", sa.Text, nullable=False),
        sa.Column("status",
                  sa.Enum("pending", "accepted", "rejected", "stale", name="suggestionstatus"),
                  nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("suggestions")
    op.drop_table("comments")
    op.drop_table("sources")
    op.drop_table("documents")
    op.execute("DROP TYPE IF EXISTS suggestionstatus")
    op.execute("DROP TYPE IF EXISTS commentstatus")
    op.execute("DROP TYPE IF EXISTS sourcetype")
