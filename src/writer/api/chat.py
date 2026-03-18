"""Chat API endpoints — GET and POST /api/documents/{doc_id}/chat."""

import html as html_lib
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.core.templates import templates as _shared_templates
from writer.models.enums import ChatRole, SourceType
from writer.models.schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    SourceCreate,
    SourceResponse,
    UserResponse,
)
from writer.services import agent_service, chat_service, document_service, source_service
from writer.services.content_fetcher import fetch_url_content
from writer.services.document_service import DocumentNotFoundError
from writer.services.indexer import run_indexing

router = APIRouter()
logger = get_logger(__name__)

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


def get_templates() -> Jinja2Templates:
    return _shared_templates


def _sse(html: str) -> str:
    """Format HTML as an SSE data event, collapsing internal newlines."""
    return "data: " + html.replace("\n", " ").replace("\r", "") + "\n\n"


def _status_html(message: str) -> str:
    return f'<div class="chat-status-msg">{message}</div>'


@router.get("/api/documents/{doc_id}/chat", response_model=None)
async def get_chat_history(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
) -> HTMLResponse | list[ChatMessageResponse]:
    try:
        doc = await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    messages = await chat_service.list_chat_messages(db, doc_id, current_user.id)

    # First-open: no messages yet and document has an overview.
    if not messages and doc.overview and request.headers.get("HX-Request"):
        wrapper = (
            f'<div id="chat-stream-wrapper"'
            f' hx-ext="sse"'
            f' sse-connect="/api/documents/{doc_id}/chat/stream"'
            f' sse-swap="message">'
            f'<div class="chat-status-msg">Starting up\u2026</div>'
            f"</div>"
        )
        return HTMLResponse(wrapper)

    if request.headers.get("HX-Request"):
        tmpl = get_templates()
        html = "".join(
            tmpl.get_template("partials/chat_message.html").render({"msg": m, "request": request})
            for m in messages
        )
        return HTMLResponse(html)
    return messages  # type: ignore[return-value]


def _action_buttons_html(doc_id: uuid.UUID) -> str:
    return (
        f'<div id="chat-action-buttons" class="chat-action-buttons">'
        f'<button class="btn btn-secondary btn-sm"'
        f' hx-post="/api/documents/{doc_id}/chat/find-sources"'
        f' hx-swap="none"'
        f' hx-disabled-elt="this"'
        f' hx-on::before-request="this.classList.add(\'btn--loading\')"'
        f' hx-on::after-request="this.classList.remove(\'btn--loading\')">'
        f'Find relevant sources</button>'
        f'<button class="btn btn-secondary btn-sm"'
        f' hx-post="/api/documents/{doc_id}/chat/suggest-outline"'
        f' hx-target="#chat-history"'
        f' hx-swap="beforeend"'
        f' hx-disabled-elt="this"'
        f' hx-on::before-request="this.classList.add(\'btn--loading\')"'
        f' hx-on::after-request="this.classList.remove(\'btn--loading\')">Suggest Outline</button>'
        f'</div>'
    )


async def _fetch_and_save_sources(
    candidates: list[dict[str, str]],
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[SourceResponse]:
    results = []
    for s in candidates:
        url = s.get("url")
        try:
            content = await fetch_url_content(url) if url else s.get("summary", "")
        except Exception as exc:
            logger.warning("fetch-sources: failed to fetch %s: %s", url, exc)
            continue
        source = await source_service.add_source(
            db,
            SourceCreate(
                document_id=doc_id,
                source_type=SourceType.url,
                title=s.get("title", "Source"),
                content=content,
                url=url,
            ),
            user_id,
        )
        results.append(source)
    return results


@router.get("/api/documents/{doc_id}/chat/stream")
async def stream_chat_init(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
) -> StreamingResponse:
    """SSE stream: saves the overview as the first user message and shows action buttons."""
    try:
        doc = await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    if not doc.overview:
        raise HTTPException(status_code=400, detail="Document has no overview")

    overview = doc.overview
    user_id = current_user.id
    tmpl = get_templates()

    def _messages_oob(msgs: list[ChatMessageResponse], extra_html: str = "") -> str:
        html = "".join(
            tmpl.get_template("partials/chat_message.html").render({"msg": m, "request": request})
            for m in msgs
        )
        return f'<div id="chat-history" hx-swap-oob="outerHTML">{html}{extra_html}</div>'

    async def generate() -> AsyncGenerator[str]:
        existing = await chat_service.list_chat_messages(db, doc_id, user_id)
        if existing:
            logger.info("Stream: already initialised for doc=%s — skipping", doc_id)
            yield _sse(_messages_oob(existing))
            return

        try:
            user_msg = await chat_service.create_chat_message(
                db, doc_id, user_id, overview, ChatRole.user
            )
            await db.commit()
            logger.info("Stream: initial message saved for doc=%s", doc_id)
            yield _sse(_messages_oob([user_msg], _action_buttons_html(doc_id)))
        except Exception as exc:
            logger.exception("Stream init failed for doc=%s: %s", doc_id, exc)
            yield _sse(
                '<div class="chat-status-msg chat-status-error">'
                "\u26a0 Initialization failed \u2014 please refresh to try again."
                "</div>"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/documents/{doc_id}/chat/find-sources", response_model=None)
async def find_sources_action(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
) -> HTMLResponse:
    """Find relevant sources for the document and add them to the source panel."""
    try:
        doc = await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    if not doc.overview:
        raise HTTPException(status_code=400, detail="Document has no overview")

    overview = doc.overview
    user_id = current_user.id
    target_sources = 5

    logger.info("find-sources: researching for doc=%s", doc_id)
    raw_sources = await agent_service.invoke_research_agent(overview, user_id, title=doc.title)
    saved_sources = await _fetch_and_save_sources(raw_sources, doc_id, user_id, db)

    if len(saved_sources) < target_sources:
        exclude = [s.url for s in saved_sources if s.url]
        needed = target_sources - len(saved_sources)
        extra_raw = await agent_service.invoke_research_agent(
            overview, user_id, title=doc.title, exclude_urls=exclude
        )
        extra = await _fetch_and_save_sources(extra_raw[:needed], doc_id, user_id, db)
        saved_sources.extend(extra)

    await db.commit()
    for source in saved_sources:
        await run_indexing(source_id=source.id, db=db, user_id=user_id)

    logger.info("find-sources: saved %d sources for doc=%s", len(saved_sources), doc_id)

    # OOB: refresh source list + remove action buttons
    source_oob = (
        f'<ul id="source-list"'
        f' hx-get="/api/documents/{doc_id}/sources"'
        f' hx-trigger="load"'
        f' hx-swap="innerHTML"'
        f' hx-swap-oob="true"></ul>'
    )
    buttons_oob = '<div id="chat-action-buttons" hx-swap-oob="outerHTML"></div>'
    return HTMLResponse(source_oob + buttons_oob)


@router.post("/api/documents/{doc_id}/chat/suggest-outline", response_model=None)
async def suggest_outline_action(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
) -> HTMLResponse:
    """Generate a document outline and add it as an assistant message in chat."""
    try:
        doc = await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    if not doc.overview:
        raise HTTPException(status_code=400, detail="Document has no overview")

    overview = doc.overview
    user_id = current_user.id

    logger.info("suggest-outline: planning for doc=%s", doc_id)
    sources = await source_service.list_sources(db, doc_id, user_id)
    plan_text = await agent_service.invoke_planner(overview, sources, doc_id, user_id)

    assistant_msg = await chat_service.create_chat_message(
        db, doc_id, user_id, plan_text, ChatRole.assistant
    )
    await db.commit()
    logger.info("suggest-outline: complete for doc=%s", doc_id)

    tmpl = get_templates()
    msg_html = tmpl.get_template("partials/chat_message.html").render(
        {"msg": assistant_msg, "request": request}
    )
    buttons_oob = '<div id="chat-action-buttons" hx-swap-oob="outerHTML"></div>'
    return HTMLResponse(msg_html + buttons_oob)


@router.post("/api/documents/{doc_id}/chat", response_model=None)
async def post_chat_message(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    content: Annotated[str, Form()],
) -> HTMLResponse | list[ChatMessageResponse]:
    import logging as _lg, sys as _sys
    _root = _lg.getLogger()
    # Write directly to stderr, bypassing all logging machinery
    _sys.stderr.write(f"[DIAG-DIRECT] root.handlers={_root.handlers} root.level={_root.level}\n")
    _sys.stderr.flush()
    # Force-add a handler and test
    _h = _lg.StreamHandler(_sys.stderr)
    _root.addHandler(_h)
    _root.warning("[DIAG-FORCED] root.warning with freshly added handler")
    _root.removeHandler(_h)
    logger.warning("[DIAG-CHAT-LOGGER] warning via chat logger")

    try:
        doc = await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    ChatMessageCreate(content=content)

    user_msg = await chat_service.create_chat_message(
        db, doc_id, current_user.id, content, ChatRole.user
    )

    history = await chat_service.list_chat_messages(db, doc_id, current_user.id)

    try:
        assistant_msg, new_doc_content, sources_added = await chat_service.process_chat(
            db, doc_id, current_user.id, history, doc.content or "", doc.is_private,
            title=doc.title, overview=doc.overview or "",
        )
    except Exception as exc:
        logger.exception("ChatAgent error for doc=%s: %s", doc_id, exc)
        raise HTTPException(status_code=502, detail=f"AI agent error: {exc}") from exc

    await db.commit()

    if request.headers.get("HX-Request"):
        tmpl = get_templates()
        messages_html = "".join(
            tmpl.get_template("partials/chat_message.html").render({"msg": m, "request": request})
            for m in (user_msg, assistant_msg)
        )
        oob = ""
        if sources_added:
            updated_sources = await source_service.list_sources(db, doc_id, current_user.id)
            if updated_sources:
                items_html = "".join(
                    tmpl.get_template("partials/sources.html").render(
                        {"source": s, "request": request}
                    )
                    for s in updated_sources
                )
            else:
                items_html = '<li class="source-empty-state">No sources added yet.</li>'
            oob += f'<ul id="source-list" hx-swap-oob="true">{items_html}</ul>'
        if new_doc_content is not None:
            escaped = html_lib.escape(new_doc_content)
            oob = (
                f'<textarea id="document-content" hx-swap-oob="outerHTML"'
                f' hx-put="/api/documents/{doc_id}"'
                f' hx-ext="json-enc"'
                f' hx-trigger="tiptap-changed delay:1s"'
                f' hx-vals=\'js:{{"content": document.getElementById("document-content").value,'
                f' "title": document.getElementById("doc-title").value}}\''
                f' hx-swap="none">{escaped}</textarea>'
            )
        return HTMLResponse(messages_html + oob)
    return [user_msg, assistant_msg]  # type: ignore[return-value]
