"""Chat API endpoints — GET and POST /api/documents/{doc_id}/chat."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.models.enums import ChatRole
from writer.models.schemas import ChatMessageCreate, ChatMessageResponse
from writer.services import chat_service, document_service
from writer.services.document_service import DocumentNotFoundError

router = APIRouter()
logger = get_logger(__name__)

DbDep = Annotated[AsyncSession, Depends(get_db)]

_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory="src/writer/templates")
    return _templates


@router.get("/api/documents/{doc_id}/chat", response_model=None)
async def get_chat_history(
    request: Request,
    db: DbDep,
    doc_id: uuid.UUID,
) -> HTMLResponse | list[ChatMessageResponse]:
    try:
        await document_service.get_document(db, doc_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    messages = await chat_service.list_chat_messages(db, doc_id)

    if request.headers.get("HX-Request"):
        tmpl = get_templates()
        html = "".join(
            tmpl.get_template("partials/chat_message.html").render({"msg": m, "request": request})
            for m in messages
        )
        return HTMLResponse(html)
    return messages  # type: ignore[return-value]


@router.post("/api/documents/{doc_id}/chat", response_model=None)
async def post_chat_message(
    request: Request,
    db: DbDep,
    doc_id: uuid.UUID,
    content: Annotated[str, Form()],
) -> HTMLResponse | list[ChatMessageResponse]:
    try:
        await document_service.get_document(db, doc_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    # Validate via schema
    ChatMessageCreate(content=content)

    # Persist user message
    user_msg = await chat_service.create_chat_message(db, doc_id, content, ChatRole.user)

    # Load full history (includes the just-persisted user message)
    history = await chat_service.list_chat_messages(db, doc_id)

    # Invoke agent and persist assistant reply
    try:
        assistant_msg = await chat_service.process_chat(db, doc_id, history)
    except Exception as exc:
        logger.exception("ChatAgent error for doc=%s: %s", doc_id, exc)
        raise HTTPException(status_code=502, detail=f"AI agent error: {exc}") from exc

    await db.commit()

    if request.headers.get("HX-Request"):
        tmpl = get_templates()
        html = "".join(
            tmpl.get_template("partials/chat_message.html").render({"msg": m, "request": request})
            for m in (user_msg, assistant_msg)
        )
        return HTMLResponse(html)
    return [user_msg, assistant_msg]  # type: ignore[return-value]
