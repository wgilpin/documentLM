"""Source ingestion API endpoints."""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.database import get_db
from writer.core.templates import templates as _shared_templates
from writer.models.enums import SourceType
from writer.models.schemas import SourceCreate, SourceResponse
from writer.services import source_service
from writer.services.source_service import PdfParseError, SourceNotFoundError

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]


def get_templates() -> Jinja2Templates:
    return _shared_templates


@router.get("/{doc_id}/sources", response_model=None)
async def list_sources(
    request: Request, db: DbDep, doc_id: uuid.UUID
) -> HTMLResponse | list[SourceResponse]:
    sources = await source_service.list_sources(db, doc_id)
    if request.headers.get("HX-Request"):
        if not sources:
            return HTMLResponse('<li class="source-empty-state">No sources added yet.</li>')
        tmpl = get_templates()
        html = "".join(
            tmpl.get_template("partials/sources.html").render(
                {"source": s, "doc_id": doc_id, "request": request}
            )
            for s in sources
        )
        return HTMLResponse(html)
    return sources  # type: ignore[return-value]


@router.post("/{doc_id}/sources", response_model=None)
async def add_source(
    request: Request,
    db: DbDep,
    background_tasks: BackgroundTasks,
    doc_id: uuid.UUID,
    source_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    content: Annotated[str, Form()] = "",
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> HTMLResponse | SourceResponse:
    from writer.services.indexer import run_indexing

    stype = SourceType(source_type)

    if stype == SourceType.pdf and file is not None:
        file_bytes = await file.read()
        try:
            source = await source_service.add_source_pdf(db, doc_id, title, file_bytes)
        except PdfParseError as exc:
            if request.headers.get("HX-Request"):
                error_html = '<div class="source-error">Invalid PDF file.</div>'
                return HTMLResponse(
                    error_html,
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    headers={"HX-Retarget": "#source-error-pdf", "HX-Reswap": "innerHTML"},
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not parse PDF.",
            ) from exc
    else:
        data = SourceCreate(
            document_id=doc_id,
            source_type=stype,
            title=title,
            content=content,
            url=url or None,
        )
        source = await source_service.add_source(db, data)

    await db.commit()
    background_tasks.add_task(run_indexing, source_id=source.id, db=db)

    if request.headers.get("HX-Request"):
        tmpl = get_templates()
        html = tmpl.get_template("partials/sources.html").render(
            {"source": source, "doc_id": doc_id, "request": request}
        )
        return HTMLResponse(html)
    return source


@router.get("/{doc_id}/sources/{source_id}/view", response_model=None)
async def view_source(
    request: Request, db: DbDep, doc_id: uuid.UUID, source_id: uuid.UUID
) -> HTMLResponse:
    try:
        source = await source_service.get_source(db, source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc
    if source.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Source not found")
    tmpl = get_templates()
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            tmpl.get_template("partials/source_note_modal.html").render(
                {"source": source, "request": request}
            )
        )
    return HTMLResponse(
        tmpl.get_template("source_view.html").render({"source": source, "request": request})
    )


@router.delete("/{doc_id}/sources/{source_id}", response_model=None)
async def delete_source(
    request: Request, db: DbDep, doc_id: uuid.UUID, source_id: uuid.UUID
) -> HTMLResponse | None:
    try:
        await source_service.delete_source(db, source_id)
        await db.commit()
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc

    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return None
