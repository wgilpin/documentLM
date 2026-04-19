"""Source ingestion API endpoints."""

import asyncio
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
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.auth import get_current_user
from writer.core.database import get_db
from writer.core.templates import templates as _shared_templates
from writer.models.enums import IndexingStatus, SourceType
from writer.models.schemas import (
    ChapterAssociationUpdate,
    SourceCreate,
    SourceResponse,
    UserResponse,
)
from writer.services import chapter_service, source_service
from writer.services.deep_research_service import ExtractedReference, parse_markdown_document
from writer.services.filter_scope import FilterScopeParseError, parse_filter_scope
from writer.services.source_service import (
    ChapterDocumentMismatchError,
    PdfParseError,
    SourceNotFoundError,
)

router = APIRouter()
# Separate router for /api/sources/{source_id}/... paths (not under /api/documents)
source_view_router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


def get_templates() -> Jinja2Templates:
    return _shared_templates


async def _build_chapter_title_map(db: AsyncSession, doc_id: uuid.UUID) -> dict[uuid.UUID, str]:
    chapters = await chapter_service.list_chapters(db, doc_id)
    return {c.id: c.title for c in chapters}


def _render_source_list(
    request: Request,
    sources: list[SourceResponse],
    doc_id: uuid.UUID,
    chapter_id_to_title: dict[uuid.UUID, str],
    *,
    scope_value: str,
) -> str:
    if not sources:
        return (
            f'<li class="source-empty-state">'
            f"No sources match the current filter ({scope_value}). "
            f'<a href="#" hx-get="/api/documents/{doc_id}/sources?scope=all" '
            f'hx-target="#source-list" hx-swap="innerHTML">Show all</a>.</li>'
        )
    tmpl = get_templates()
    return "".join(
        tmpl.get_template("partials/sources.html").render(
            {
                "source": s,
                "doc_id": doc_id,
                "request": request,
                "chapter_id_to_title": chapter_id_to_title,
            }
        )
        for s in sources
    )


@router.get("/{doc_id}/sources", response_model=None)
async def list_sources(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    scope: str = "all",
) -> HTMLResponse | list[SourceResponse]:
    try:
        parsed_scope = parse_filter_scope(scope)
    except FilterScopeParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sources = await source_service.list_sources_by_scope(db, doc_id, current_user.id, parsed_scope)
    if request.headers.get("HX-Request"):
        title_map = await _build_chapter_title_map(db, doc_id)
        return HTMLResponse(
            _render_source_list(request, sources, doc_id, title_map, scope_value=scope)
        )
    return sources


@router.post("/{doc_id}/sources", response_model=None)
async def add_source(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    doc_id: uuid.UUID,
    source_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    content: Annotated[str, Form()] = "",
    url: Annotated[str | None, Form()] = None,
    chapter_ids: Annotated[list[uuid.UUID] | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> HTMLResponse | SourceResponse:
    from writer.services.indexer import run_indexing

    chapter_ids = chapter_ids or []
    stype = SourceType(source_type)

    try:
        if stype == SourceType.pdf and file is not None:
            file_bytes = await file.read()
            try:
                source = await source_service.add_source_pdf(
                    db, doc_id, title, file_bytes, current_user.id, chapter_ids=chapter_ids
                )
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
                chapter_ids=chapter_ids,
            )
            source = await source_service.add_source(db, data, current_user.id)
    except ChapterDocumentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    await db.commit()
    if source.indexing_status != IndexingStatus.failed:
        background_tasks.add_task(run_indexing, source_id=source.id, db=db, user_id=current_user.id)

    if request.headers.get("HX-Request"):
        title_map = await _build_chapter_title_map(db, doc_id)
        tmpl = get_templates()
        html = tmpl.get_template("partials/sources.html").render(
            {
                "source": source,
                "doc_id": doc_id,
                "request": request,
                "chapter_id_to_title": title_map,
            }
        )
        return HTMLResponse(html)
    return source


@router.put("/{doc_id}/sources/{source_id}/chapters", response_model=None)
async def update_source_chapters(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    source_id: uuid.UUID,
    data: ChapterAssociationUpdate,
) -> HTMLResponse | SourceResponse:
    try:
        source = await source_service.get_source(db, source_id, current_user.id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc
    if source.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        await source_service.replace_source_chapter_associations(
            db,
            source_id,
            data.chapter_ids,
            document_id=doc_id,
            user_id=current_user.id,
        )
        await db.commit()
    except ChapterDocumentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    refreshed = await source_service.get_source(db, source_id, current_user.id)
    if request.headers.get("HX-Request"):
        title_map = await _build_chapter_title_map(db, doc_id)
        tmpl = get_templates()
        html = tmpl.get_template("partials/sources.html").render(
            {
                "source": refreshed,
                "doc_id": doc_id,
                "request": request,
                "chapter_id_to_title": title_map,
            }
        )
        return HTMLResponse(html)
    return refreshed


@router.get("/{doc_id}/sources/{source_id}/chapters/edit", response_model=None)
async def edit_source_chapters_form(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    doc_id: uuid.UUID,
    source_id: uuid.UUID,
) -> HTMLResponse:
    try:
        source = await source_service.get_source(db, source_id, current_user.id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc
    if source.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Source not found")

    chapters = await chapter_service.list_chapters(db, doc_id)
    form_id = f"source-chapters-form-{source_id}"
    picker_html = (
        get_templates()
        .get_template("partials/chapter_picker.html")
        .render(
            {
                "chapters": chapters,
                "selected_chapter_ids": list(source.chapter_ids),
                "form_id": form_id,
                "request": request,
            }
        )
    )
    # Wrap the picker in a form that PUTs the JSON array of selected UUIDs.
    form_html = (
        f'<form id="{form_id}" class="source-chapters-edit-form" '
        f'hx-put="/api/documents/{doc_id}/sources/{source_id}/chapters" '
        f'hx-ext="json-enc" '
        f'hx-vals="js:{{chapter_ids: Array.from(document.querySelectorAll('
        f"'#{form_id} input[name=chapter_ids]:checked')).map(e=>e.value)}}\" "
        f'hx-target="#source-{source_id}" hx-swap="outerHTML">'
        f"{picker_html}"
        f'<div class="chapter-picker-actions">'
        f'<button type="submit" class="btn btn-primary btn-sm">Apply</button>'
        f"</div></form>"
    )
    return HTMLResponse(form_html)


@router.get("/{doc_id}/sources/{source_id}/view", response_model=None)
async def view_source(
    request: Request, db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID, source_id: uuid.UUID
) -> HTMLResponse:
    try:
        source = await source_service.get_source(db, source_id, current_user.id)
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


@router.get("/{doc_id}/sources/{source_id}/pdf", response_model=None)
async def view_source_pdf(
    db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID, source_id: uuid.UUID
) -> FileResponse:
    try:
        source = await source_service.get_source(db, source_id, current_user.id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc
    if source.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.file_path:
        raise HTTPException(status_code=404, detail="PDF file not available")
    from pathlib import Path

    if not Path(source.file_path).exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(
        source.file_path, media_type="application/pdf", filename=f"{source.title}.pdf"
    )


class ImportDeepResearchResponse(BaseModel):
    created: list[SourceResponse]
    skipped_count: int


@router.post("/{doc_id}/sources/import-deep-research", response_model=None)
async def import_deep_research(
    request: Request,
    db: DbDep,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    doc_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
) -> HTMLResponse | ImportDeepResearchResponse:
    from writer.core.logging import get_logger
    from writer.services.indexer import run_indexing

    log = get_logger(__name__)
    log.info("import_deep_research: doc=%s user=%s file=%s", doc_id, current_user.id, file.filename)

    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        log.warning("import_deep_research: could not decode file as UTF-8")
        content = ""

    parsed = parse_markdown_document(content, file.filename or "research.md")

    if not parsed["body"] and not parsed["references"]:
        log.warning("import_deep_research: empty content for doc=%s", doc_id)
        error_html = (
            "<p>The file appears to be empty or unreadable. "
            "Please select a valid Markdown file.</p>"
        )
        return HTMLResponse(
            error_html,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            headers={"HX-Retarget": "#import-deep-research-error", "HX-Reswap": "innerHTML"},
        )

    created: list[SourceResponse] = []
    skipped_count = 0

    # Document body source
    note_data = SourceCreate(
        document_id=doc_id,
        source_type=SourceType.note,
        title=parsed["title"],
        content=parsed["body"],
        url=None,
    )
    note_source = await source_service.add_source(db, note_data, current_user.id)
    created.append(note_source)

    # Reference URL sources — fetch + clean all in parallel, then store
    from documentlm_core.services.content_cleaner import clean_content

    from writer.services.content_fetcher import fetch_url_content

    # De-duplicate references by URL
    seen_urls: set[str] = set()
    unique_refs: list[ExtractedReference] = []
    for ref in parsed["references"]:
        if ref["url"] not in seen_urls:
            seen_urls.add(ref["url"])
            unique_refs.append(ref)
        else:
            skipped_count += 1

    async def _fetch_and_clean(url: str) -> str | None:
        try:
            raw = await fetch_url_content(url)
            cleaned: str | None = await clean_content(raw)
            return cleaned
        except Exception:
            log.warning("import_deep_research: failed to fetch url=%s, skipping", url)
            return None

    fetched = await asyncio.gather(*[_fetch_and_clean(ref["url"]) for ref in unique_refs])

    for ref, fetched_content in zip(unique_refs, fetched, strict=True):
        if fetched_content is None:
            skipped_count += 1
            continue
        url_data = SourceCreate(
            document_id=doc_id,
            source_type=SourceType.url,
            title=ref["title"],
            content=fetched_content,
            url=ref["url"],
        )
        url_source = await source_service.add_source(db, url_data, current_user.id)
        # add_source returns existing source on duplicate — detect skip by checking created list
        if any(s.id == url_source.id for s in created):
            skipped_count += 1
        else:
            created.append(url_source)

    await db.commit()

    for src in created:
        if src.indexing_status != IndexingStatus.failed:
            background_tasks.add_task(
                run_indexing, source_id=src.id, db=db, user_id=current_user.id
            )

    log.info(
        "import_deep_research: created=%d skipped=%d doc=%s",
        len(created),
        skipped_count,
        doc_id,
    )

    if request.headers.get("HX-Request"):
        title_map = await _build_chapter_title_map(db, doc_id)
        tmpl = get_templates()
        html = "".join(
            tmpl.get_template("partials/sources.html").render(
                {
                    "source": s,
                    "doc_id": doc_id,
                    "request": request,
                    "chapter_id_to_title": title_map,
                }
            )
            for s in created
        )
        return HTMLResponse(html)

    return ImportDeepResearchResponse(created=created, skipped_count=skipped_count)


def _build_paragraphs_with_offsets(content: str) -> list[dict[str, object]]:
    """Split markdown content into paragraphs with character offsets for scroll anchors."""
    import markdown as md_lib

    paragraphs: list[dict[str, object]] = []
    offset = 0
    # Split on blank lines to get logical blocks
    blocks = content.split("\n\n")
    for block in blocks:
        block = block.strip()
        if block:
            rendered = md_lib.markdown(block, extensions=["extra"])
            paragraphs.append({"offset": offset, "html": rendered})
        offset += len(block) + 2  # account for the \n\n separator
    return paragraphs


@source_view_router.get("/{source_id}/view", response_model=None)
async def get_source_document_view(
    request: Request, db: DbDep, current_user: CurrentUser, source_id: uuid.UUID
) -> HTMLResponse:
    """Return rendered markdown HTML for Document View panel (HTMX target)."""
    try:
        source = await source_service.get_source(db, source_id, current_user.id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc

    paragraphs = _build_paragraphs_with_offsets(source.content)
    tmpl = get_templates()
    return HTMLResponse(
        tmpl.get_template("partials/source_view.html").render(
            {"source": source, "paragraphs": paragraphs, "request": request}
        )
    )


@router.delete("/{doc_id}/sources/{source_id}", response_model=None)
async def delete_source(
    request: Request, db: DbDep, current_user: CurrentUser, doc_id: uuid.UUID, source_id: uuid.UUID
) -> HTMLResponse | None:
    try:
        await source_service.delete_source(db, source_id, current_user.id)
        await db.commit()
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source not found") from exc

    if request.headers.get("HX-Request"):
        return HTMLResponse("")
    return None
