"""Document CRUD service — pure async functions, no business logic in endpoints."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Comment, Document, Suggestion
from writer.models.enums import CommentStatus, SuggestionStatus
from writer.models.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentSummary,
    DocumentUpdate,
    SuggestionResponse,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class DocumentNotFoundError(Exception):
    def __init__(self, doc_id: uuid.UUID) -> None:
        super().__init__(f"Document {doc_id} not found")
        self.doc_id = doc_id


class SuggestionNotFoundError(Exception):
    def __init__(self, suggestion_id: uuid.UUID) -> None:
        super().__init__(f"Suggestion {suggestion_id} not found")
        self.suggestion_id = suggestion_id


async def create_document(db: AsyncSession, data: DocumentCreate) -> DocumentResponse:
    logger.info("Creating document title=%r", data.title)
    doc = Document(title=data.title, content=data.content, overview=data.overview)
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    logger.info("Created document id=%s", doc.id)
    return DocumentResponse.model_validate(doc)


async def get_document(db: AsyncSession, doc_id: uuid.UUID) -> DocumentResponse:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundError(doc_id)
    return DocumentResponse.model_validate(doc)


async def list_documents(db: AsyncSession) -> list[DocumentSummary]:
    result = await db.execute(select(Document).order_by(Document.updated_at.desc()))
    docs = result.scalars().all()
    return [DocumentSummary.model_validate(d) for d in docs]


async def update_document(
    db: AsyncSession, doc_id: uuid.UUID, data: DocumentUpdate
) -> DocumentResponse:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundError(doc_id)
    if data.title is not None:
        doc.title = data.title
    if data.content is not None:
        doc.content = data.content
    await db.flush()
    await db.refresh(doc)
    logger.info("Updated document id=%s", doc_id)
    return DocumentResponse.model_validate(doc)


async def delete_document(db: AsyncSession, doc_id: uuid.UUID) -> None:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundError(doc_id)
    await db.delete(doc)
    await db.flush()
    logger.info("Deleted document id=%s", doc_id)


def _suggested_inline_nodes(suggested_text: str) -> list[dict]:  # type: ignore[type-arg]
    """Convert suggested markdown text to TipTap inline nodes.

    Uses the markdown parser to produce properly marked-up content (bold, italic,
    code) rather than a raw text node containing markdown syntax.
    Falls back to a plain text node if parsing produces nothing.
    """
    import json

    from writer.services.tiptap import markdown_to_tiptap

    try:
        doc = json.loads(markdown_to_tiptap(suggested_text))
        content_nodes = doc.get("content", [])
        if content_nodes:
            inline = content_nodes[0].get("content", [])
            if inline:
                return inline
    except Exception:
        pass
    return [{"type": "text", "text": suggested_text}]


def _update_node_text(content_json: str, node_id: str, new_text: str) -> str:
    """Recursively find a TipTap node by attrs.id and replace its inline content.

    The new_text is treated as markdown so that bold/italic/code marks are
    rendered correctly rather than displayed as raw syntax.
    Raises ValueError when the node is not found.
    """
    import json

    doc = json.loads(content_json)
    inline_nodes = _suggested_inline_nodes(new_text)

    def visit(node: dict) -> bool:  # type: ignore[type-arg]
        if node.get("attrs", {}).get("id") == node_id:
            node["content"] = inline_nodes
            return True
        return any(visit(child) for child in node.get("content", []))

    if not visit(doc):
        raise ValueError(f"Node {node_id!r} not found in document JSON")
    return json.dumps(doc)



async def accept_suggestion(db: AsyncSession, suggestion_id: uuid.UUID) -> DocumentResponse:
    result = await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise SuggestionNotFoundError(suggestion_id)

    comment_result = await db.execute(select(Comment).where(Comment.id == suggestion.comment_id))
    comment = comment_result.scalar_one_or_none()
    if comment is None:
        raise DocumentNotFoundError(suggestion.comment_id)

    doc_result = await db.execute(select(Document).where(Document.id == comment.document_id))
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundError(comment.document_id)

    # Node-ID path: fast and accurate, no text mismatch
    node_replaced = False
    if comment.selected_node_id and doc.content:
        try:
            doc.content = _update_node_text(
                doc.content, comment.selected_node_id, suggestion.suggested_text
            )
            node_replaced = True
        except ValueError:
            logger.warning(
                "accept_suggestion=%s: node %r not found — marking stale",
                suggestion_id,
                comment.selected_node_id,
            )
            suggestion.status = SuggestionStatus.stale
            await db.flush()
            raise ValueError(
                "Selection is stale — the target node was deleted"
            ) from None

    if not node_replaced:
        suggestion.status = SuggestionStatus.stale
        await db.flush()
        raise ValueError(
            "Selection is stale — document was edited after suggestion was created"
        )
    suggestion.status = SuggestionStatus.accepted
    comment.status = CommentStatus.resolved
    await db.flush()
    await db.refresh(doc)
    logger.info("Accepted suggestion id=%s for document id=%s", suggestion_id, doc.id)
    return DocumentResponse.model_validate(doc)


async def reject_suggestion(db: AsyncSession, suggestion_id: uuid.UUID) -> SuggestionResponse:
    result = await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise SuggestionNotFoundError(suggestion_id)

    comment_result = await db.execute(select(Comment).where(Comment.id == suggestion.comment_id))
    comment = comment_result.scalar_one_or_none()

    suggestion.status = SuggestionStatus.rejected
    if comment is not None:
        comment.status = CommentStatus.resolved
    await db.flush()
    await db.refresh(suggestion)
    logger.info("Rejected suggestion id=%s", suggestion_id)
    return SuggestionResponse.model_validate(suggestion)
