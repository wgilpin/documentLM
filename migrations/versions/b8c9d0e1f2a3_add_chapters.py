"""add chapters and chapter_snippets tables

Revision ID: b8c9d0e1f2a3
Revises: 7275283b6b35
Create Date: 2026-04-14 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "7275283b6b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- DDL: create chapters table ---
    op.create_table(
        "chapters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default="Untitled Chapter"),
        sa.Column("brief", sa.Text(), nullable=True),
        sa.Column("brief_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "position", name="uq_chapters_document_position"),
    )
    op.create_index("chapters_document_position_idx", "chapters", ["document_id", "position"])
    op.create_index("chapters_document_user_idx", "chapters", ["document_id", "user_id"])

    # --- DDL: create chapter_snippets junction table ---
    op.create_table(
        "chapter_snippets",
        sa.Column("chapter_id", sa.UUID(), nullable=False),
        sa.Column("snippet_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snippet_id"], ["snippets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chapter_id", "snippet_id"),
    )
    op.create_index("chapter_snippets_snippet_idx", "chapter_snippets", ["snippet_id"])

    # --- DML: migrate existing documents to single-chapter ---
    conn = op.get_bind()

    # For each existing document, create one chapter
    docs = conn.execute(
        sa.text("SELECT id, user_id, title, content FROM documents")
    ).fetchall()
    for doc in docs:
        chapter_id = conn.execute(
            sa.text(
                "INSERT INTO chapters (id, document_id, user_id, title, content, position) "
                "VALUES (gen_random_uuid(), :doc_id, :user_id, :title, :content, 0) "
                "RETURNING id"
            ),
            {"doc_id": doc.id, "user_id": doc.user_id, "title": doc.title, "content": doc.content},
        ).scalar()

        # Link existing snippets to the new chapter
        conn.execute(
            sa.text(
                "INSERT INTO chapter_snippets (chapter_id, snippet_id) "
                "SELECT :chapter_id, id FROM snippets WHERE document_id = :doc_id"
            ),
            {"chapter_id": chapter_id, "doc_id": doc.id},
        )


def downgrade() -> None:
    op.drop_index("chapter_snippets_snippet_idx", table_name="chapter_snippets")
    op.drop_table("chapter_snippets")
    op.drop_index("chapters_document_user_idx", table_name="chapters")
    op.drop_index("chapters_document_position_idx", table_name="chapters")
    op.drop_table("chapters")
