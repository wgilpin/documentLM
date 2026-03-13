"""Integration tests using a real PostgreSQL database (Docker).

Run with: docker-compose up -d postgres && uv run pytest tests/integration/
Requires DATABASE_URL env var pointing to a test-ready PostgreSQL instance.
"""


import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from writer.core.config import settings
from writer.core.database import Base
from writer.models import db as _db_models  # noqa: F401 — register all ORM models
from writer.models.enums import SourceType
from writer.models.schemas import DocumentCreate, SourceCreate
from writer.services import document_service, source_service


@pytest_asyncio.fixture()
async def db():  # type: ignore[no-untyped-def]
    _engine = create_async_engine(settings.database_url, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await _engine.dispose()


class TestDocumentRoundTrip:
    async def test_create_and_read_document(self, db: AsyncSession) -> None:
        data = DocumentCreate(title="Integration Test Doc", content="Hello DB")
        doc = await document_service.create_document(db, data)
        await db.flush()

        fetched = await document_service.get_document(db, doc.id)
        assert fetched.title == "Integration Test Doc"
        assert fetched.content == "Hello DB"

    async def test_update_document(self, db: AsyncSession) -> None:
        from writer.models.schemas import DocumentUpdate

        data = DocumentCreate(title="To Update", content="old")
        doc = await document_service.create_document(db, data)
        await db.flush()

        updated = await document_service.update_document(
            db, doc.id, DocumentUpdate(content="new content")
        )
        assert updated.content == "new content"

    async def test_delete_document(self, db: AsyncSession) -> None:
        from writer.services.document_service import DocumentNotFoundError

        data = DocumentCreate(title="To Delete")
        doc = await document_service.create_document(db, data)
        await db.flush()

        await document_service.delete_document(db, doc.id)
        await db.flush()

        with pytest.raises(DocumentNotFoundError):
            await document_service.get_document(db, doc.id)


class TestSourceRoundTrip:
    async def test_add_and_list_source(self, db: AsyncSession) -> None:
        doc_data = DocumentCreate(title="Source Test Doc")
        doc = await document_service.create_document(db, doc_data)
        await db.flush()

        src_data = SourceCreate(
            document_id=doc.id, source_type=SourceType.note, title="My Note", content="notes here"
        )
        src = await source_service.add_source(db, src_data)
        await db.flush()

        sources = await source_service.list_sources(db, doc.id)
        assert any(s.id == src.id for s in sources)

    async def test_delete_source(self, db: AsyncSession) -> None:
        from writer.services.source_service import SourceNotFoundError

        doc_data = DocumentCreate(title="Delete Source Doc")
        doc = await document_service.create_document(db, doc_data)
        await db.flush()

        src_data = SourceCreate(
            document_id=doc.id, source_type=SourceType.note, title="Del Note", content="x"
        )
        src = await source_service.add_source(db, src_data)
        await db.flush()

        await source_service.delete_source(db, src.id)
        await db.flush()

        with pytest.raises(SourceNotFoundError):
            await source_service.delete_source(db, src.id)
