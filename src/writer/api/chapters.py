"""Chapter CRUD API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.templates import templates as _tpl
from writer.models.schemas import (
    ChapterBriefVisibilityUpdate,
    ChapterCreate,
    ChapterPositionUpdate,
    ChapterResponse,
    ChapterUpdate,
    UserResponse,
)
from writer.services import chapter_service
from writer.services.chapter_service import ChapterNotFoundError

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


@router.post(
    "/{doc_id}/chapters",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    data: ChapterCreate,
) -> HTMLResponse | ChapterResponse:
    chapter = await chapter_service.create_chapter(db, doc_id, current_user.id, data)
    await db.commit()

    if request.headers.get("HX-Request"):
        chapters = await chapter_service.list_chapters(db, doc_id)
        html = _tpl.get_template("partials/chapter_card.html").render(
            {"chapter": chapter, "doc_id": doc_id, "request": request}
        )
        toc_html = _tpl.get_template("partials/toc.html").render(
            {"chapters": chapters, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(
            html + toc_html,
            status_code=status.HTTP_201_CREATED,
        )
    return chapter


@router.get("/{doc_id}/chapters", response_model=None)
async def list_chapters(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
) -> HTMLResponse | list[ChapterResponse]:
    chapters = await chapter_service.list_chapters(db, doc_id)

    if request.headers.get("HX-Request"):
        html = ""
        for ch in chapters:
            html += _tpl.get_template("partials/chapter_card.html").render(
                {"chapter": ch, "doc_id": doc_id, "request": request}
            )
        toc_html = _tpl.get_template("partials/toc.html").render(
            {"chapters": chapters, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html + toc_html)
    return chapters  # type: ignore[return-value]


@router.get("/{doc_id}/chapters/{chapter_id}", response_model=None)
async def get_chapter(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> HTMLResponse | ChapterResponse:
    try:
        chapter = await chapter_service.get_chapter(db, chapter_id)
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc

    if request.headers.get("HX-Request"):
        html = _tpl.get_template("partials/chapter_editor.html").render(
            {"chapter": chapter, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html)
    return chapter


@router.put("/{doc_id}/chapters/{chapter_id}", response_model=None)
async def update_chapter(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID,
    data: ChapterUpdate,
) -> HTMLResponse | ChapterResponse:
    try:
        chapter = await chapter_service.update_chapter(db, chapter_id, data)
        await db.commit()
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc

    if request.headers.get("HX-Request"):
        html = _tpl.get_template("partials/chapter_card.html").render(
            {"chapter": chapter, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html)
    return chapter


@router.delete("/{doc_id}/chapters/{chapter_id}", response_model=None)
async def delete_chapter(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID,
) -> HTMLResponse | None:
    try:
        await chapter_service.delete_chapter(db, chapter_id)
        await db.commit()
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc

    if request.headers.get("HX-Request"):
        chapters = await chapter_service.list_chapters(db, doc_id)
        html = ""
        for ch in chapters:
            html += _tpl.get_template("partials/chapter_card.html").render(
                {"chapter": ch, "doc_id": doc_id, "request": request}
            )
        toc_html = _tpl.get_template("partials/toc.html").render(
            {"chapters": chapters, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html + toc_html)
    return None


@router.patch("/{doc_id}/chapters/{chapter_id}/position", response_model=None)
async def reorder_chapter(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID,
    data: ChapterPositionUpdate,
) -> HTMLResponse | list[ChapterResponse]:
    try:
        chapters = await chapter_service.reorder_chapter(db, chapter_id, data.position)
        await db.commit()
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc

    if request.headers.get("HX-Request"):
        html = ""
        for ch in chapters:
            html += _tpl.get_template("partials/chapter_card.html").render(
                {"chapter": ch, "doc_id": doc_id, "request": request}
            )
        toc_html = _tpl.get_template("partials/toc.html").render(
            {"chapters": chapters, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html + toc_html)
    return chapters  # type: ignore[return-value]


@router.patch(
    "/{doc_id}/chapters/{chapter_id}/brief-visibility",
    response_model=None,
)
async def toggle_brief_visibility(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID,
    data: ChapterBriefVisibilityUpdate,
) -> HTMLResponse | ChapterResponse:
    try:
        chapter = await chapter_service.toggle_brief_visibility(
            db, chapter_id, brief_visible=data.brief_visible
        )
        await db.commit()
    except ChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chapter not found") from exc

    if request.headers.get("HX-Request"):
        html = _tpl.get_template("partials/chapter_card.html").render(
            {"chapter": chapter, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html)
    return chapter


# ── Snippet-Chapter Association Endpoints (US3) ─────────────────────────


@router.post(
    "/{doc_id}/chapters/{chapter_id}/snippets/{snippet_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
async def assign_snippet_to_chapter(
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID,
    snippet_id: uuid.UUID,
) -> None:
    from writer.services import snippet_service

    await snippet_service.assign_snippet_to_chapter(db, chapter_id, snippet_id)
    await db.commit()


@router.delete(
    "/{doc_id}/chapters/{chapter_id}/snippets/{snippet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def unassign_snippet_from_chapter(
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    chapter_id: uuid.UUID,
    snippet_id: uuid.UUID,
) -> None:
    from writer.services import snippet_service

    await snippet_service.unassign_snippet_from_chapter(db, chapter_id, snippet_id)
    await db.commit()
