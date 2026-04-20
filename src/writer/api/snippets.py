"""Snippet CRUD API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.templates import templates as _shared_templates
from writer.models.schemas import (
    ChapterAssociationUpdate,
    SnippetCreate,
    SnippetResponse,
    SnippetUpdate,
    UserResponse,
)
from writer.services import chapter_service, snippet_service
from writer.services.filter_scope import FilterScopeParseError, parse_filter_scope
from writer.services.snippet_service import (
    ChapterDocumentMismatchError,
    DocumentNotFoundError,
    SnippetNotFoundError,
)

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


async def _build_chapter_title_map(db: AsyncSession, doc_id: uuid.UUID) -> dict[uuid.UUID, str]:
    chapters = await chapter_service.list_chapters(db, doc_id)
    return {c.id: c.title for c in chapters}


@router.post(
    "/documents/{doc_id}/snippets", response_model=None, status_code=status.HTTP_201_CREATED
)
async def create_snippet(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    data: SnippetCreate,
    background_tasks: BackgroundTasks,
) -> HTMLResponse | SnippetResponse:
    try:
        snippet = await snippet_service.create_snippet(
            db, doc_id, current_user.id, data, background_tasks=background_tasks
        )
        await db.commit()
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except ChapterDocumentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if request.headers.get("HX-Request"):
        title_map = await _build_chapter_title_map(db, doc_id)
        html = _shared_templates.get_template("partials/snippet_card.html").render(
            {
                "snippet": snippet,
                "doc_id": doc_id,
                "request": request,
                "chapter_id_to_title": title_map,
            }
        )
        return HTMLResponse(html, status_code=status.HTTP_201_CREATED)
    return snippet


@router.get("/documents/{doc_id}/snippets", response_model=None)
async def list_snippets(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    scope: str = "all",
    chapter_id: uuid.UUID | None = None,
) -> HTMLResponse | list[SnippetResponse]:
    # Backward-compat: legacy `chapter_id` query param maps to scope=chapter:<uuid>
    if chapter_id is not None and scope == "all":
        scope = f"chapter:{chapter_id}"

    try:
        parsed_scope = parse_filter_scope(scope)
    except FilterScopeParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    snippets = await snippet_service.list_snippets_by_scope(
        db, doc_id, current_user.id, parsed_scope
    )

    if request.headers.get("HX-Request"):
        title_map = await _build_chapter_title_map(db, doc_id)
        active_chapter_id: uuid.UUID | None = None
        if scope.startswith("chapter:"):
            try:
                active_chapter_id = uuid.UUID(scope[len("chapter:") :])
            except ValueError:
                active_chapter_id = None
        html = _shared_templates.get_template("partials/snippet_bank.html").render(
            {
                "snippets": snippets,
                "doc_id": doc_id,
                "request": request,
                "chapter_id_to_title": title_map,
                "chapters": await chapter_service.list_chapters(db, doc_id),
                "active_scope": scope,
                "active_chapter_id": active_chapter_id,
            }
        )
        return HTMLResponse(html)
    return snippets


@router.put("/documents/{doc_id}/snippets/{snippet_id}/chapters", response_model=None)
async def update_snippet_chapters(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    snippet_id: uuid.UUID,
    data: ChapterAssociationUpdate,
) -> HTMLResponse | SnippetResponse:
    try:
        snippet = await snippet_service.get_snippet_with_source_title(
            db, snippet_id, current_user.id
        )
    except SnippetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Snippet not found") from exc
    if snippet.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Snippet not found")

    try:
        await snippet_service.replace_snippet_chapter_associations(
            db,
            snippet_id,
            data.chapter_ids,
            document_id=doc_id,
            user_id=current_user.id,
        )
        await db.commit()
    except ChapterDocumentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    refreshed = await snippet_service.get_snippet_with_source_title(db, snippet_id, current_user.id)
    if request.headers.get("HX-Request"):
        title_map = await _build_chapter_title_map(db, doc_id)
        html = _shared_templates.get_template("partials/snippet_card.html").render(
            {
                "snippet": refreshed,
                "doc_id": doc_id,
                "request": request,
                "chapter_id_to_title": title_map,
            }
        )
        return HTMLResponse(html)
    return refreshed


@router.get("/documents/{doc_id}/snippets/{snippet_id}/chapters/edit", response_model=None)
async def edit_snippet_chapters_form(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    snippet_id: uuid.UUID,
) -> HTMLResponse:
    try:
        snippet = await snippet_service.get_snippet_with_source_title(
            db, snippet_id, current_user.id
        )
    except SnippetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Snippet not found") from exc
    if snippet.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Snippet not found")

    chapters = await chapter_service.list_chapters(db, doc_id)
    selected = set(snippet.chapter_ids)
    form_id = f"snippet-chapters-form-{snippet_id}"
    options_html = "".join(
        f'<label class="chapter-picker-option">'
        f'<input type="checkbox" name="chapter_ids" value="{c.id}"'
        f"{' checked' if c.id in selected else ''}>"
        f"<span>{c.title}</span></label>"
        for c in chapters
    )
    form_html = (
        f'<form id="{form_id}" class="chapter-picker-list-form" '
        f'hx-put="/api/documents/{doc_id}/snippets/{snippet_id}/chapters" '
        f'hx-ext="json-enc" '
        f'hx-trigger="change from:input" '
        f'hx-vals="js:{{chapter_ids: Array.from(document.querySelectorAll('
        f"'#{form_id} input[name=chapter_ids]:checked')).map(e=>e.value)}}\" "
        f'hx-target="#snippet-{snippet_id}" hx-swap="outerHTML">'
        f'<div class="chapter-picker-list">{options_html}</div>'
        f"</form>"
    )
    return HTMLResponse(form_html)


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
        title_map = await _build_chapter_title_map(db, doc_id)
        html = _shared_templates.get_template("partials/snippet_card.html").render(
            {
                "snippet": snippet,
                "doc_id": doc_id,
                "request": request,
                "chapter_id_to_title": title_map,
            }
        )
        return HTMLResponse(html)
    return snippet
