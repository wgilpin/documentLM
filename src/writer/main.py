"""FastAPI application entry point."""

import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from writer.core.auth import get_current_user
from writer.core.config import settings
from writer.core.database import _get_engine, get_db
from writer.core.logging import configure_logging
from writer.core.templates import templates
from writer.models.schemas import UserResponse
from writer.services import document_service, settings_service
from writer.services.document_service import DocumentNotFoundError


async def _seed_document(email: str, log: logging.Logger) -> None:
    from sqlalchemy import select

    from writer.core.database import _get_session_factory
    from writer.models.db import User
    from writer.models.schemas import DocumentCreate

    async with _get_session_factory()() as db:
        result = await db.execute(select(User).where(User.email == email.strip().lower()))
        user = result.scalar_one_or_none()
        if user is None:
            log.warning("--seed-doc: no user found with email=%r — skipping", email)
            return
        await document_service.create_document(
            db,
            DocumentCreate(
                title="Welcome to AI Document Workbench",
                content="<p>This is your seed document. Start writing!</p>",
                overview="Dev seed document",
            ),
            user.id,
        )
        await db.commit()
        log.info("--seed-doc: created seed document for user=%r", email)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    import os

    log = logging.getLogger("writer.startup")
    if settings.gemini_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key
        log.info("GEMINI_API_KEY loaded (%d chars)", len(settings.gemini_api_key))
    else:
        log.warning("GEMINI_API_KEY is not set — chat agent will fail")

    if not settings.secret_key:
        log.warning("SECRET_KEY is not set — using insecure dev key, do not use in production")

    if settings.dev_seed_doc_email:
        await _seed_document(settings.dev_seed_doc_email, log)

    yield
    await _get_engine().dispose()


app = FastAPI(title="AI Document Workbench", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key or "dev-insecure-key-change-in-production",
    max_age=86400,  # 24 hours
    https_only=False,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]

# Import and register routers
from writer.api import auth as auth_router  # noqa: E402
from writer.api import chat as chat_router  # noqa: E402
from writer.api import documents as doc_router  # noqa: E402
from writer.api import settings as settings_router  # noqa: E402
from writer.api import sources as src_router  # noqa: E402
from writer.api import suggestions as sug_router  # noqa: E402

app.include_router(auth_router.router)
app.include_router(doc_router.router, prefix="/api/documents", tags=["documents"])
app.include_router(src_router.router, prefix="/api/documents", tags=["sources"])
app.include_router(sug_router.router, tags=["suggestions"])
app.include_router(chat_router.router, tags=["chat"])
app.include_router(settings_router.router)


# UI routes — all protected by get_current_user
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: DbDep, current_user: CurrentUser) -> HTMLResponse:
    documents = await document_service.list_documents(db, current_user.id)
    return templates.TemplateResponse("index.html", {"request": request, "documents": documents})


@app.get("/documents/new", response_class=HTMLResponse)
async def new_document(request: Request, db: DbDep, current_user: CurrentUser) -> HTMLResponse:
    user_settings = await settings_service.get_settings(db, current_user.id)
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
async def view_document(
    request: Request, db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID
) -> HTMLResponse:
    try:
        doc = await document_service.get_document(db, doc_id, current_user.id)
    except DocumentNotFoundError:
        return templates.TemplateResponse(
            "index.html", {"request": request, "documents": [], "error": "Document not found"}
        )
    user_settings = await settings_service.get_settings(db, current_user.id)
    return templates.TemplateResponse(
        "document.html",
        {
            "request": request,
            "doc": doc,
            "undo_buffer_size": settings.undo_buffer_size,
            "user_settings": user_settings,
        },
    )
