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


def _update_node_range(
    content_json: str,
    from_node_id: str,
    to_node_id: str | None,
    new_text: str,
) -> str:
    """Replace all top-level doc nodes from from_node_id to to_node_id (inclusive)
    with the blocks parsed from new_text markdown.

    When to_node_id is None or equal to from_node_id, only the single node is replaced.
    Raises ValueError if either node ID is not found at the top level.
    """
    import json

    from writer.services.tiptap import markdown_to_tiptap

    doc = json.loads(content_json)
    new_doc = json.loads(markdown_to_tiptap(new_text))
    new_nodes: list[dict] = new_doc.get("content") or [  # type: ignore[type-arg]
        {"type": "paragraph", "content": []}
    ]

    effective_to = to_node_id if to_node_id else from_node_id
    children: list[dict] = doc.get("content", [])  # type: ignore[type-arg]

    result: list[dict] = []  # type: ignore[type-arg]
    state = "before"  # before | in_range | after
    found_start = False
    found_end = False

    for child in children:
        child_id = child.get("attrs", {}).get("id")
        if state == "before":
            if child_id == from_node_id:
                found_start = True
                result.extend(new_nodes)
                if effective_to == from_node_id:
                    found_end = True
                    state = "after"
                else:
                    state = "in_range"
                # skip from_node itself
            else:
                result.append(child)
        elif state == "in_range":
            if child_id == effective_to:
                found_end = True
                state = "after"
                # skip to_node (already replaced by new_nodes above)
            # else: skip intermediate nodes
        else:
            result.append(child)

    if not found_start or not found_end:
        raise ValueError(
            f"Range nodes {from_node_id!r}..{effective_to!r} not found in document"
        )
    doc["content"] = result
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
            doc.content = _update_node_range(
                doc.content,
                comment.selected_node_id,
                comment.to_node_id,
                suggestion.suggested_text,
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


def is_selection_valid(content: str, start: int, end: int, selected_text: str) -> bool:
    """Return True when [start, end) is in-bounds and content[start:end] == selected_text."""
    if start >= end:
        return False
    if end > len(content):
        return False
    return content[start:end] == selected_text


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
