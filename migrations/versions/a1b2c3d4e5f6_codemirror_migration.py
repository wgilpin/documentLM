"""codemirror_migration: convert content to markdown, drop node-id columns

Revision ID: a1b2c3d4e5f6
Revises: 351313c224f9
Create Date: 2026-03-15 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "351313c224f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tiptap_to_markdown(content: str) -> str:
    """Inline copy of tiptap_to_markdown so the migration is self-contained."""
    import json

    def _render(node: dict) -> str:  # type: ignore[type-arg]
        t = node.get("type", "")
        ch = node.get("content", [])
        if t == "doc":
            return "\n\n".join(_render(c) for c in ch)
        if t == "heading":
            level = int(node.get("attrs", {}).get("level", 1))
            return "#" * level + " " + "".join(_render(c) for c in ch)
        if t == "paragraph":
            return "".join(_render(c) for c in ch)
        if t == "text":
            text = str(node.get("text", ""))
            _MARK_WRAP = {"bold": ("**", "**"), "italic": ("_", "_"), "code": ("`", "`")}
            for mark in node.get("marks", []):
                o, c = _MARK_WRAP.get(mark["type"], ("", ""))
                text = f"{o}{text}{c}"
            return text
        if t == "hardBreak":
            return "\n"
        if t == "bulletList":
            return "\n".join("- " + _render_list_item(item) for item in ch)
        if t == "orderedList":
            return "\n".join(f"{i + 1}. " + _render_list_item(ch[i]) for i in range(len(ch)))
        if t == "listItem":
            return _render_list_item(node)
        if t == "blockquote":
            inner = "\n\n".join(_render(c) for c in ch)
            return "\n".join("> " + line for line in inner.splitlines())
        if t == "codeBlock":
            lang = node.get("attrs", {}).get("language", "") or ""
            code = "".join(_render(c) for c in ch)
            return f"```{lang}\n{code}\n```"
        return "".join(_render(c) for c in ch)

    def _render_list_item(node: dict) -> str:  # type: ignore[type-arg]
        return "".join(_render(c) for c in node.get("content", []))

    if not content:
        return ""
    try:
        return _render(json.loads(content))
    except (json.JSONDecodeError, KeyError):
        return content


def upgrade() -> None:
    """Convert documents.content from TipTap JSON to plain markdown;
    drop node-id columns from comments."""
    bind = op.get_bind()

    # Convert each document's content in Python
    rows = bind.execute(sa.text("SELECT id, content FROM documents")).fetchall()
    for row in rows:
        doc_id, content = row
        if content:
            markdown = _tiptap_to_markdown(content)
            bind.execute(
                sa.text("UPDATE documents SET content = :md WHERE id = :id"),
                {"md": markdown, "id": doc_id},
            )

    op.drop_column("comments", "selected_node_id")
    op.drop_column("comments", "to_node_id")


def downgrade() -> None:
    """Re-add node-id columns (content round-trip is lossy — JSON is not restored)."""
    op.add_column("comments", sa.Column("to_node_id", sa.Text(), nullable=True))
    op.add_column("comments", sa.Column("selected_node_id", sa.Text(), nullable=True))
