"""Semantic search API — dual-group search with chapter scoping."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.templates import templates as _shared_templates
from writer.models.schemas import SearchV2Response, UserResponse
from writer.services import chapter_service, search_service
from writer.services.filter_scope import FilterScopeParseError, parse_filter_scope

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


@router.get("/documents/{doc_id}/search", response_model=None)
async def search_corpus(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    q: Annotated[str, Query()] = "",
    scope: Annotated[str, Query()] = "all",
    top_k: Annotated[int, Query(ge=1, le=20)] = 10,
) -> HTMLResponse | SearchV2Response:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    try:
        parsed_scope = parse_filter_scope(scope)
    except FilterScopeParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await search_service.search_document_dual(
        query=q.strip(),
        user_id=current_user.id,
        doc_id=doc_id,
        session=db,
        scope=parsed_scope,
        top_k=top_k,
    )

    if request.headers.get("HX-Request"):
        chapters = await chapter_service.list_chapters(db, doc_id)
        html = _shared_templates.get_template("partials/search_results.html").render(
            {
                "search": result,
                "doc_id": doc_id,
                "request": request,
                "chapters": chapters,
            }
        )
        return HTMLResponse(html)
    return result
