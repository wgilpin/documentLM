"""Suggestions / margin comments API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.core.templates import templates as _shared_templates
from writer.models.db import Comment, Suggestion
from writer.models.enums import CommentStatus, SuggestionStatus
from writer.models.schemas import (
    CommentCreate,
    CommentResponse,
    SuggestionResponse,
    UserResponse,
)
from writer.services import agent_service, document_service, source_service
from writer.services.document_service import DocumentNotFoundError

router = APIRouter()
logger = get_logger(__name__)

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


def get_templates() -> Jinja2Templates:
    return _shared_templates


@router.post("/api/documents/{doc_id}/comments", response_model=None)
async def submit_comment(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    selection_start: Annotated[int, Form()],
    selection_end: Annotated[int, Form()],
    selected_text: Annotated[str, Form()],
    body: Annotated[str, Form()],
) -> HTMLResponse | SuggestionResponse:
    # Validate document exists and belongs to current user
    try:
        doc = await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    # Persist comment
    comment_data = CommentCreate(
        document_id=doc_id,
        selection_start=selection_start,
        selection_end=selection_end,
        selected_text=selected_text,
        body=body,
    )
    comment_orm = Comment(
        document_id=comment_data.document_id,
        selection_start=comment_data.selection_start,
        selection_end=comment_data.selection_end,
        selected_text=comment_data.selected_text,
        body=comment_data.body,
    )
    db.add(comment_orm)
    await db.flush()
    await db.refresh(comment_orm)
    comment = CommentResponse.model_validate(comment_orm)

    # Fetch sources for context
    sources = await source_service.list_sources(db, doc_id, current_user.id)

    # Invoke Drafter agent
    try:
        suggested_text = await agent_service.invoke_drafter(
            comment, doc, sources, current_user.id, db
        )
    except Exception as exc:
        logger.exception("Agent invocation error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI agent error: {exc}") from exc

    # Persist suggestion — doc.content is never modified
    suggestion_orm = Suggestion(
        comment_id=comment.id,
        original_text=selected_text,
        suggested_text=suggested_text,
    )
    db.add(suggestion_orm)
    await db.flush()
    await db.refresh(suggestion_orm)
    await db.commit()

    suggestion = SuggestionResponse.model_validate(suggestion_orm)

    if request.headers.get("HX-Request"):
        tmpl = get_templates()
        html = tmpl.get_template("partials/suggestion.html").render(
            {"s": suggestion, "request": request}
        )
        return HTMLResponse(html)
    return suggestion


@router.get("/api/documents/{doc_id}/suggestions", response_model=None)
async def list_suggestions(
    request: Request, db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID
) -> HTMLResponse | list[SuggestionResponse]:
    result = await db.execute(
        select(Suggestion)
        .join(Comment, Suggestion.comment_id == Comment.id)
        .where(Comment.document_id == doc_id)
        .where(Suggestion.status == SuggestionStatus.pending)
        .order_by(Suggestion.created_at)
    )
    suggestions = [SuggestionResponse.model_validate(s) for s in result.scalars().all()]

    if request.headers.get("HX-Request"):
        tmpl = get_templates()
        html = "".join(
            tmpl.get_template("partials/suggestion.html").render({"s": s, "request": request})
            for s in suggestions
        )
        return HTMLResponse(html)
    return suggestions  # type: ignore[return-value]


@router.post("/api/suggestions/{suggestion_id}/accept", response_model=None)
async def accept(
    request: Request, db: DbDep, suggestion_id: uuid.UUID
) -> JSONResponse | SuggestionResponse:
    result = await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    comment_result = await db.execute(select(Comment).where(Comment.id == suggestion.comment_id))
    comment = comment_result.scalar_one_or_none()

    suggestion.status = SuggestionStatus.accepted
    if comment is not None:
        comment.status = CommentStatus.resolved
    await db.flush()
    await db.commit()

    logger.info("Accepted suggestion id=%s", suggestion_id)

    if request.headers.get("HX-Request"):
        return JSONResponse({"status": "accepted"})
    return SuggestionResponse.model_validate(suggestion)


@router.post("/api/suggestions/{suggestion_id}/reject", response_model=None)
async def reject(
    request: Request, db: DbDep, suggestion_id: uuid.UUID
) -> JSONResponse | SuggestionResponse:
    result = await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    comment_result = await db.execute(select(Comment).where(Comment.id == suggestion.comment_id))
    comment = comment_result.scalar_one_or_none()

    suggestion.status = SuggestionStatus.rejected
    if comment is not None:
        comment.status = CommentStatus.resolved
    await db.flush()
    await db.commit()

    logger.info("Rejected suggestion id=%s", suggestion_id)

    if request.headers.get("HX-Request"):
        return JSONResponse({"status": "rejected"})
    return SuggestionResponse.model_validate(suggestion)
