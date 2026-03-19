"""add chat_sessions table and session_id to chat_messages

Revision ID: a4b5c6d7e8f9
Revises: f1a2b3c4d5e6
Create Date: 2026-03-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4b5c6d7e8f9"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create session_status enum type (EXCEPTION block handles re-runs / partial failures)
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE sessionstatus AS ENUM ('active', 'archived');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # 2. Create chat_sessions table
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("active", "archived", name="sessionstatus", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_chat_sessions_user_document",
        "chat_sessions",
        ["user_id", "document_id"],
    )

    # 3. Backfill: create one session per (user_id, document_id) pair in chat_messages
    op.execute(
        """
        INSERT INTO chat_sessions (id, user_id, document_id, status, created_at)
        SELECT
            gen_random_uuid(),
            user_id,
            document_id,
            'active',
            MIN(created_at)
        FROM chat_messages
        GROUP BY user_id, document_id
        """
    )

    # 4. Add session_id column (nullable initially for backfill)
    op.add_column(
        "chat_messages",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 5. Backfill session_id on existing chat_messages
    op.execute(
        """
        UPDATE chat_messages cm
        SET session_id = cs.id
        FROM chat_sessions cs
        WHERE cs.user_id = cm.user_id
          AND cs.document_id = cm.document_id
        """
    )

    # 6. Set session_id NOT NULL
    op.alter_column("chat_messages", "session_id", nullable=False)

    # 7. Add FK constraint
    op.create_foreign_key(
        "fk_chat_messages_session_id",
        "chat_messages",
        "chat_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 8. Add index on (session_id, created_at)
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )

    # 9. Add partial unique index on chat_sessions for single-active invariant
    op.execute(
        """
        CREATE UNIQUE INDEX ix_chat_sessions_one_active
        ON chat_sessions (user_id, document_id)
        WHERE status = 'active'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chat_sessions_one_active")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_constraint("fk_chat_messages_session_id", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "session_id")
    op.drop_index("ix_chat_sessions_user_document", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    sa.Enum(name="sessionstatus").drop(op.get_bind(), checkfirst=True)
