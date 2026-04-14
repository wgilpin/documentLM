"""Bounded generation API endpoint."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.core.templates import templates as _shared_templates
from writer.models.db import Document
from writer.models.schemas import (
    BoundedGenerateRequest,
    BoundedGenerationResponse,
    UserResponse,
)
from writer.services import agent_service, snippet_service
from writer.services.snippet_service import SnippetNotFoundError

router = APIRouter()
logger = get_logger(__name__)

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


@router.post("/documents/{doc_id}/bounded-generate", response_model=None)
async def bounded_generate(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    body: BoundedGenerateRequest,
) -> HTMLResponse | BoundedGenerationResponse:
    logger.info(
        "bounded_generate: doc=%s user=%s snippets=%d intent=%r",
        doc_id,
        current_user.id,
        len(body.snippet_ids),
        body.intent[:80],
    )

    # Fetch document content
    doc_result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Fetch snippets with source titles
    snippet_pairs: list[tuple[str, str]] = []
    for snippet_id in body.snippet_ids:
        try:
            snippet = await snippet_service.get_snippet_with_source_title(
                db, snippet_id, current_user.id
            )
            source_title = snippet.source_title or "Unknown Source"
            snippet_pairs.append((snippet.text, source_title))
        except SnippetNotFoundError:
            logger.warning("bounded_generate: snippet %s not found, skipping", snippet_id)

    # Invoke bounded drafter
    try:
        suggested_text = await agent_service.invoke_bounded_drafter(
            snippets=snippet_pairs,
            intent=body.intent,
            cursor_context=body.cursor_context,
            document_content=doc.content or "",
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.error("bounded_generate: agent error: %s", exc)
        raise HTTPException(status_code=502, detail="Generation failed") from exc

    response = BoundedGenerationResponse(suggested_text=suggested_text)

    if request.headers.get("HX-Request"):
        html = _shared_templates.get_template("partials/bounded_suggestion.html").render(
            {"suggested_text": suggested_text, "request": request}
        )
        return HTMLResponse(html)
    return response
