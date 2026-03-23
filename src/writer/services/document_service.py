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


async def create_document(
    db: AsyncSession, data: DocumentCreate, user_id: uuid.UUID
) -> DocumentResponse:
    logger.info("Creating document title=%r user=%s", data.title, user_id)
    doc = Document(user_id=user_id, title=data.title, content=data.content, overview=data.overview)
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    logger.info("Created document id=%s", doc.id)
    return DocumentResponse.model_validate(doc)


async def get_document(db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID) -> DocumentResponse:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundError(doc_id)
    return DocumentResponse.model_validate(doc)


async def list_documents(db: AsyncSession, user_id: uuid.UUID) -> list[DocumentSummary]:
    result = await db.execute(
        select(Document).where(Document.user_id == user_id).order_by(Document.updated_at.desc())
    )
    docs = result.scalars().all()
    return [DocumentSummary.model_validate(d) for d in docs]


async def update_document(
    db: AsyncSession, doc_id: uuid.UUID, data: DocumentUpdate, user_id: uuid.UUID
) -> DocumentResponse:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    )
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


async def delete_document(db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundError(doc_id)
    await db.delete(doc)
    await db.flush()
    logger.info("Deleted document id=%s", doc_id)


async def toggle_privacy(
    db: AsyncSession, doc_id: uuid.UUID, user_id: uuid.UUID, is_private: bool
) -> DocumentResponse:
    """Set the Private flag on a document and update ChromaDB metadata."""
    from writer.services import vector_store

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise DocumentNotFoundError(doc_id)
    doc.is_private = is_private
    await db.flush()
    await db.refresh(doc)
    logger.info("toggle_privacy doc=%s is_private=%s", doc_id, is_private)
    try:
        import asyncio

        await asyncio.to_thread(vector_store.update_privacy, user_id, doc_id, is_private)
    except Exception as exc:
        logger.error("toggle_privacy: ChromaDB update failed for doc=%s: %s", doc_id, exc)
    return DocumentResponse.model_validate(doc)


import re
def find_fuzzy_block(text_content: str, old_text: str, new_text: str, start_hint: int) -> tuple[int, int]:
    words_old = re.findall(r'\w+', old_text)
    words_new = re.findall(r'\w+', new_text)
    
    num_start = min(4, len(words_old))
    num_end = min(4, len(words_new))
    if num_start == 0 or num_end == 0: return -1, -1
        
    start_str = r'[\W_]*'.join(re.escape(w) for w in words_old[:num_start])
    end_str = r'[\W_]*'.join(re.escape(w) for w in words_new[-num_end:])
    
    # Catch initial 2 tildes, trailing punctuation, then standard core words
    start_pattern = r'(?:\\?~){2}[\W_]*?' + start_str
    
    window_start = max(0, start_hint - 100)
    window_end = min(len(text_content), start_hint + len(old_text) + len(new_text) + 200)
    window = text_content[window_start:window_end]
    
    start_match = re.search(start_pattern, window)
    if not start_match:
        start_match = re.search(start_str, window)
        if not start_match: return -1, -1
        
    start_idx = window_start + start_match.start()
    
    # End core words, trailing punctuation, then closing formatting markers
    end_pattern = end_str + r'[\W_]*?(?:\\?[*_]){3}'
    
    end_window = text_content[start_idx:window_end]
    end_match = re.search(end_pattern, end_window)
    if not end_match:
        end_match = re.search(end_str, end_window)
        if not end_match: return -1, -1
        
    end_idx = start_idx + end_match.end()
    return start_idx, end_idx


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

    content = doc.content or ""
    
    start_idx, end_idx = find_fuzzy_block(content, suggestion.original_text, suggestion.suggested_text, comment.selection_start)
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        doc.content = (
            content[:start_idx]
            + suggestion.suggested_text
            + content[end_idx:]
        )
    else:
        # Fallback if block couldn't be extracted
        if is_selection_valid(content, comment.selection_start, comment.selection_end, comment.selected_text):
            doc.content = (
                content[: comment.selection_start]
                + suggestion.suggested_text
                + content[comment.selection_end :]
            )
        else:
            suggestion.status = SuggestionStatus.stale
            await db.flush()
            raise ValueError(f"Selection is stale — document overrides failed. Fuzzy match bounds not found.")
            
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


async def reject_suggestion(db: AsyncSession, suggestion_id: uuid.UUID) -> tuple[SuggestionResponse, Document]:
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

    suggestion.status = SuggestionStatus.rejected
    comment.status = CommentStatus.resolved

    content = doc.content or ""
    
    start_idx, end_idx = find_fuzzy_block(content, suggestion.original_text, suggestion.suggested_text, comment.selection_start)

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        doc.content = (
            content[:start_idx]
            + suggestion.original_text
            + content[end_idx:]
        )
    else:
        if is_selection_valid(content, comment.selection_start, comment.selection_end, comment.selected_text):
            doc.content = (
                content[: comment.selection_start]
                + suggestion.original_text
                + content[comment.selection_end :]
            )
        else:
            suggestion.status = SuggestionStatus.stale
            await db.flush()
            raise ValueError("Selection is stale — fuzzy block bounds not found and selection is compromised.")

    await db.flush()
    await db.refresh(suggestion)
    logger.info("Rejected suggestion id=%s", suggestion_id)
    return SuggestionResponse.model_validate(suggestion), doc

