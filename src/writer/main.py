"""FastAPI application entry point."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.config import settings
from writer.core.templates import templates
from writer.core.database import _get_engine, get_db
from writer.core.logging import configure_logging
from writer.services import document_service
from writer.services.document_service import DocumentNotFoundError


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
    yield
    await _get_engine().dispose()


app = FastAPI(title="AI Document Workbench", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


DbDep = Annotated[AsyncSession, Depends(get_db)]

# Import and register routers
from writer.api import chat as chat_router  # noqa: E402
from writer.api import documents as doc_router  # noqa: E402
from writer.api import sources as src_router  # noqa: E402
from writer.api import suggestions as sug_router  # noqa: E402

app.include_router(doc_router.router, prefix="/api/documents", tags=["documents"])
app.include_router(src_router.router, prefix="/api/documents", tags=["sources"])
app.include_router(sug_router.router, tags=["suggestions"])
app.include_router(chat_router.router, tags=["chat"])


# UI routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: DbDep) -> HTMLResponse:
    documents = await document_service.list_documents(db)
    return templates.TemplateResponse("index.html", {"request": request, "documents": documents})


@app.get("/documents/new", response_class=HTMLResponse)
async def new_document(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("document.html", {"request": request, "doc": None})


@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, db: DbDep, doc_id: uuid.UUID) -> HTMLResponse:
    try:
        doc = await document_service.get_document(db, doc_id)
    except DocumentNotFoundError:
        return templates.TemplateResponse(
            "index.html", {"request": request, "documents": [], "error": "Document not found"}
        )
    return templates.TemplateResponse("document.html", {"request": request, "doc": doc})
