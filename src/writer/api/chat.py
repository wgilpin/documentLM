"""Chat API endpoints — GET and POST /api/documents/{doc_id}/chat."""

import html as html_lib
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.core.templates import templates as _shared_templates
from writer.models.enums import ChatRole, SourceType
from writer.models.schemas import ChatMessageCreate, ChatMessageResponse, SourceCreate
from writer.services import chat_service, document_service
from writer.services.document_service import DocumentNotFoundError

router = APIRouter()
logger = get_logger(__name__)

DbDep = Annotated[AsyncSession, Depends(get_db)]


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
    doc_id: uuid.UUID,
) -> HTMLResponse | list[ChatMessageResponse]:
    try:
        doc = await document_service.get_document(db, doc_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    messages = await chat_service.list_chat_messages(db, doc_id)

    # First-open: no messages yet and document has an overview.
    # Return an SSE wrapper immediately — the /stream endpoint does the heavy work.
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


@router.get("/api/documents/{doc_id}/chat/stream")
async def stream_chat_init(
    request: Request,
    db: DbDep,
    doc_id: uuid.UUID,
) -> StreamingResponse:
    """SSE stream that runs research → fetch → plan and pushes stage updates."""
    try:
        doc = await document_service.get_document(db, doc_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    if not doc.overview:
        raise HTTPException(status_code=400, detail="Document has no overview")

    overview = doc.overview
    tmpl = get_templates()

    def _messages_oob(msgs: list[ChatMessageResponse]) -> str:
        """Render messages into an OOB swap that replaces #chat-history.

        Replacing #chat-history (which contains #chat-stream-wrapper) removes
        the sse-connect element from the DOM, stopping HTMX SSE from reconnecting.
        """
        html = "".join(
            tmpl.get_template("partials/chat_message.html").render({"msg": m, "request": request})
            for m in msgs
        )
        return f'<div id="chat-history" hx-swap-oob="outerHTML">{html}</div>'

    async def generate() -> AsyncGenerator[str]:
        from writer.services import agent_service, source_service
        from writer.services.indexer import run_indexing
        from writer.services.content_fetcher import fetch_url_content

        # Guard: if already initialised (e.g. SSE auto-reconnect after first run),
        # replace the SSE wrapper with existing messages and stop — no LLM calls.
        existing = await chat_service.list_chat_messages(db, doc_id)
        if existing:
            logger.info("Stream: already initialised for doc=%s — skipping", doc_id)
            yield _sse(_messages_oob(existing))
            return

        try:
            yield _sse(_status_html("Researching relevant sources\u2026"))
            logger.info("Stream: researching for doc=%s", doc_id)
            raw_sources = await agent_service.invoke_research_agent(overview)

            target_sources = 5

            async def _fetch_and_save(candidates: list[dict]) -> list:
                results = []
                for s in candidates:
                    url = s.get("url")
                    try:
                        content = await fetch_url_content(url) if url else s.get("summary", "")
                    except Exception as exc:
                        logger.warning("Stream: failed to fetch %s: %s", url, exc)
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
                    )
                    results.append(source)
                return results

            yield _sse(_status_html(f"Fetching content from {len(raw_sources)} source(s)\u2026"))
            logger.info("Stream: fetching %d sources for doc=%s", len(raw_sources), doc_id)
            saved_sources = await _fetch_and_save(raw_sources)

            if len(saved_sources) < target_sources:
                exclude = [s.url for s in saved_sources if s.url]
                needed = target_sources - len(saved_sources)
                logger.info(
                    "Stream: only %d sources saved, fetching %d more for doc=%s",
                    len(saved_sources),
                    needed,
                    doc_id,
                )
                yield _sse(_status_html(f"Finding {needed} more source(s)\u2026"))
                extra_raw = await agent_service.invoke_research_agent(
                    overview, exclude_urls=exclude
                )
                extra_sources = await _fetch_and_save(extra_raw[:needed])
                saved_sources.extend(extra_sources)

            await db.commit()
            for source in saved_sources:
                await run_indexing(source_id=source.id, db=db)

            yield _sse(_status_html("Generating your document plan\u2026"))
            logger.info("Stream: planning for doc=%s", doc_id)
            plan_text = await agent_service.invoke_planner(overview, saved_sources)

            user_msg = await chat_service.create_chat_message(db, doc_id, overview, ChatRole.user)
            assistant_msg = await chat_service.create_chat_message(
                db, doc_id, plan_text, ChatRole.assistant
            )
            await db.commit()
            logger.info("Stream: complete for doc=%s", doc_id)

            # OOB: replace #chat-history (removes sse-connect), refresh source list
            source_oob = (
                f'<ul id="source-list"'
                f' hx-get="/api/documents/{doc_id}/sources"'
                f' hx-trigger="load"'
                f' hx-swap="innerHTML"'
                f' hx-swap-oob="true"></ul>'
            )
            yield _sse(_messages_oob([user_msg, assistant_msg]) + source_oob)

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


@router.post("/api/documents/{doc_id}/chat", response_model=None)
async def post_chat_message(
    request: Request,
    db: DbDep,
    doc_id: uuid.UUID,
    content: Annotated[str, Form()],
) -> HTMLResponse | list[ChatMessageResponse]:
    try:
        doc = await document_service.get_document(db, doc_id)
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
        assistant_msg, new_doc_content = await chat_service.process_chat(
            db, doc_id, history, doc.content or ""
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
        # If the agent edited the document, push an OOB swap to update the textarea
        oob = ""
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
