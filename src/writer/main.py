"""FastAPI application entry point."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.config import settings
from writer.core.database import _get_engine, _get_session_factory, get_db
from writer.core.logging import configure_logging
from writer.core.templates import templates
from writer.models.db import Document
from writer.services import document_service, settings_service
from writer.services.document_service import DocumentNotFoundError

# Fixed UUID for the dev seed document — stable across restarts
_SEED_DOC_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_SEED_TITLE = "Dev Sandbox"
_SEED_CONTENT = """\
# Dev Sandbox

This document is **reset on every server start** so you always have a clean slate
for testing the editor, suggestions, undo/redo, and chat features.

## Section One

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Pellentesque habitant
morbi tristique senectus et netus et malesuada fames ac turpis egestas.

- Item one — try editing this
- Item two — select text and right-click to leave a comment
- Item three — use the chat panel to ask the AI to rewrite a section

## Section Two

Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia
curae; Donec velit neque, *auctor* sit amet aliquam vel, ullamcorper sit amet ligula.

> A blockquote for variety.  Use Ctrl+Z / Ctrl+Y to test undo and redo.

## Section Three

Some `inline code` and a short numbered list:

1. First step
2. Second step
3. Third step

**Bold text** and _italic text_ and some plain prose to round things out.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    import logging
    import os

    log = logging.getLogger("writer.startup")
    if settings.gemini_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key
        log.info("GEMINI_API_KEY loaded (%d chars)", len(settings.gemini_api_key))
    else:
        log.warning("GEMINI_API_KEY is not set — chat agent will fail")

    if settings.dev_seed_doc:
        async with _get_session_factory()() as db, db.begin():
            result = await db.execute(select(Document).where(Document.id == _SEED_DOC_ID))
            existing = result.scalar_one_or_none()
            if existing:
                await db.delete(existing)
            db.add(Document(id=_SEED_DOC_ID, title=_SEED_TITLE, content=_SEED_CONTENT))
        port = os.environ.get("WRITER_PORT", "8000")
        log.info("Dev seed doc reset → http://localhost:%s/documents/%s", port, _SEED_DOC_ID)

    yield
    await _get_engine().dispose()


app = FastAPI(title="AI Document Workbench", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


DbDep = Annotated[AsyncSession, Depends(get_db)]

# Import and register routers
from writer.api import chat as chat_router  # noqa: E402
from writer.api import documents as doc_router  # noqa: E402
from writer.api import settings as settings_router  # noqa: E402
from writer.api import sources as src_router  # noqa: E402
from writer.api import suggestions as sug_router  # noqa: E402

app.include_router(doc_router.router, prefix="/api/documents", tags=["documents"])
app.include_router(src_router.router, prefix="/api/documents", tags=["sources"])
app.include_router(sug_router.router, tags=["suggestions"])
app.include_router(chat_router.router, tags=["chat"])
app.include_router(settings_router.router)


# UI routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: DbDep) -> HTMLResponse:
    documents = await document_service.list_documents(db)
    return templates.TemplateResponse("index.html", {"request": request, "documents": documents})


@app.get("/documents/new", response_class=HTMLResponse)
async def new_document(request: Request, db: DbDep) -> HTMLResponse:
    user_settings = await settings_service.get_settings(db)
    return templates.TemplateResponse(
        "document.html",
        {
            "request": request,
            "doc": None,
            "undo_buffer_size": settings.undo_buffer_size,
            "user_settings": user_settings,
        },
    )


@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, db: DbDep, doc_id: uuid.UUID) -> HTMLResponse:
    try:
        doc = await document_service.get_document(db, doc_id)
    except DocumentNotFoundError:
        return templates.TemplateResponse(
            "index.html", {"request": request, "documents": [], "error": "Document not found"}
        )
    user_settings = await settings_service.get_settings(db)
    return templates.TemplateResponse(
        "document.html",
        {
            "request": request,
            "doc": doc,
            "undo_buffer_size": settings.undo_buffer_size,
            "user_settings": user_settings,
        },
    )
