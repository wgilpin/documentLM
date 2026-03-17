"""add_multi_user_support

Revision ID: 17ae9dac3e73
Revises: 6b34d1e33800
Create Date: 2026-03-17 19:19:36.090016

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "17ae9dac3e73"
down_revision: Union[str, Sequence[str], None] = "6b34d1e33800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — clean-slate multi-user migration."""
    # Step 1: Clean slate — delete all existing data before adding NOT NULL columns
    op.execute("DELETE FROM chat_messages")
    op.execute("DELETE FROM suggestions")
    op.execute("DELETE FROM comments")
    op.execute("DELETE FROM sources")
    op.execute("DELETE FROM documents")
    op.execute("DELETE FROM user_settings")

    # Step 2: Create new tables (IF NOT EXISTS — tables may already exist from a partial run)
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID NOT NULL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS invite_codes (
            id UUID NOT NULL PRIMARY KEY,
            code VARCHAR(32) NOT NULL UNIQUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            used_at TIMESTAMP WITH TIME ZONE,
            used_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    # Step 3: Add user_id + is_private to documents (safe — table is empty)
    op.add_column(
        "documents",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "fk_documents_user_id",
        "documents",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Step 4: Add user_id to sources (safe — table is empty)
    op.add_column(
        "sources",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_sources_user_id",
        "sources",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Step 5: Add user_id to chat_messages (safe — table is empty)
    op.add_column(
        "chat_messages",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_chat_messages_user_id",
        "chat_messages",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Step 6: Recreate user_settings with user_id UUID PK (replacing integer id)
    op.drop_table("user_settings")
    op.create_table(
        "user_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("ai_instructions", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_settings")
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("ai_instructions", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_constraint("fk_chat_messages_user_id", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "user_id")
    op.drop_constraint("fk_sources_user_id", "sources", type_="foreignkey")
    op.drop_column("sources", "user_id")
    op.drop_constraint("fk_documents_user_id", "documents", type_="foreignkey")
    op.drop_column("documents", "is_private")
    op.drop_column("documents", "user_id")
    op.drop_table("invite_codes")
    op.drop_table("users")
