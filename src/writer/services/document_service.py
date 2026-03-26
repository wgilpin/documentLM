"""Document CRUD service — pure async functions, no business logic in endpoints."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.logging import get_logger
from writer.models.db import Document
from writer.models.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentSummary,
    DocumentUpdate,
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



