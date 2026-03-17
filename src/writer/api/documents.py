"""Document CRUD API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.models.schemas import (
    DocumentCreate,
    DocumentPrivacyUpdate,
    DocumentResponse,
    DocumentSummary,
    DocumentUpdate,
    UserResponse,
)
from writer.services import document_service
from writer.services.document_service import DocumentNotFoundError

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


@router.get("/", response_model=list[DocumentSummary])
async def list_documents(db: DbDep, current_user: CurrentUser) -> list[DocumentSummary]:
    return await document_service.list_documents(db, current_user.id)


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document_endpoint(
    db: DbDep, current_user: CurrentUser, data: DocumentCreate
) -> DocumentResponse:
    return await document_service.create_document(db, data, current_user.id)


@router.post("/form", status_code=status.HTTP_303_SEE_OTHER)
async def create_document_form(
    db: DbDep,
    current_user: CurrentUser,
    title: Annotated[str, Form()],
    overview: Annotated[str, Form()] = "",
) -> RedirectResponse:
    doc = await document_service.create_document(
        db, DocumentCreate(title=title, overview=overview or None), current_user.id
    )
    await db.commit()
    return RedirectResponse(url=f"/documents/{doc.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID) -> DocumentResponse:
    try:
        return await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID, data: DocumentUpdate
) -> DocumentResponse:
    try:
        result = await document_service.update_document(db, doc_id, data, current_user.id)
        await db.commit()
        return result
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID) -> None:
    try:
        await document_service.delete_document(db, doc_id, current_user.id)
        await db.commit()
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.patch("/{doc_id}/privacy", response_model=DocumentResponse)
async def toggle_privacy(
    db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID, data: DocumentPrivacyUpdate
) -> DocumentResponse:
    try:
        result = await document_service.toggle_privacy(db, doc_id, current_user.id, data.is_private)
        await db.commit()
        return result
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
