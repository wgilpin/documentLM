"""Snippet CRUD API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.templates import templates as _shared_templates
from writer.models.schemas import SnippetCreate, SnippetResponse, SnippetUpdate, UserResponse
from writer.services import snippet_service
from writer.services.snippet_service import DocumentNotFoundError, SnippetNotFoundError

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


@router.post(
    "/documents/{doc_id}/snippets", response_model=None, status_code=status.HTTP_201_CREATED
)
async def create_snippet(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    data: SnippetCreate,
) -> HTMLResponse | SnippetResponse:
    try:
        snippet = await snippet_service.create_snippet(db, doc_id, current_user.id, data)
        await db.commit()
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    if request.headers.get("HX-Request"):
        html = _shared_templates.get_template("partials/snippet_card.html").render(
            {"snippet": snippet, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html, status_code=status.HTTP_201_CREATED)
    return snippet


@router.get("/documents/{doc_id}/snippets", response_model=None)
async def list_snippets(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID | None = None,
) -> HTMLResponse | list[SnippetResponse]:
    if chapter_id is not None:
        snippets = await snippet_service.list_snippets_by_chapter(db, chapter_id, current_user.id)
    else:
        snippets = await snippet_service.list_snippets(db, doc_id, current_user.id)

    if request.headers.get("HX-Request"):
        html = _shared_templates.get_template("partials/snippet_bank.html").render(
            {"snippets": snippets, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html)
    return snippets  # type: ignore[return-value]


@router.delete("/snippets/{snippet_id}", response_model=None)
async def delete_snippet(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    snippet_id: uuid.UUID,
) -> HTMLResponse | None:
    try:
        await snippet_service.delete_snippet(db, snippet_id, current_user.id)
        await db.commit()
    except SnippetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Snippet not found") from exc

    if request.headers.get("HX-Request"):
        return HTMLResponse("", headers={"HX-Trigger": "snippetDeleted"})
    return None


@router.patch("/snippets/{snippet_id}", response_model=None)
async def update_snippet(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    snippet_id: uuid.UUID,
    data: SnippetUpdate,
) -> HTMLResponse | SnippetResponse:
    try:
        snippet = await snippet_service.update_snippet(db, snippet_id, current_user.id, data)
        await db.commit()
    except SnippetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Snippet not found") from exc

    if request.headers.get("HX-Request"):
        doc_id = snippet.document_id
        html = _shared_templates.get_template("partials/snippet_card.html").render(
            {"snippet": snippet, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html)
    return snippet
