"""Integration tests for complete user data isolation.

Run with: docker-compose up -d postgres && uv run pytest tests/integration/
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from writer.core.config import settings
from writer.core.database import Base
from writer.models import db as _db_models  # noqa: F401 — register all ORM models


@pytest_asyncio.fixture()
async def db() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session  # type: ignore[misc]
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture()
async def two_users(db: AsyncSession) -> tuple[object, object]:  # type: ignore[misc]
    from writer.services.auth_service import create_invite_codes, register_user

    codes = await create_invite_codes(db, count=2)
    await db.flush()
    user_a = await register_user(db, codes[0], "user_a@example.com", "passwordA123")
    await db.flush()
    user_b = await register_user(db, codes[1], "user_b@example.com", "passwordB123")
    await db.flush()
    return user_a, user_b


class TestDocumentIsolation:
    async def test_list_only_returns_own_documents(
        self, db: AsyncSession, two_users: tuple[object, object]
    ) -> None:
        from writer.models.schemas import DocumentCreate
        from writer.services.document_service import create_document, list_documents

        user_a, user_b = two_users
        await create_document(db, DocumentCreate(title="A's doc"), user_a.id)  # type: ignore[union-attr]
        await db.flush()

        docs_b = await list_documents(db, user_b.id)  # type: ignore[union-attr]
        assert all(d.title != "A's doc" for d in docs_b)

    async def test_get_another_users_doc_raises_not_found(
        self, db: AsyncSession, two_users: tuple[object, object]
    ) -> None:
        from writer.models.schemas import DocumentCreate
        from writer.services.document_service import (
            DocumentNotFoundError,
            create_document,
            get_document,
        )

        user_a, user_b = two_users
        doc_a = await create_document(db, DocumentCreate(title="Private to A"), user_a.id)  # type: ignore[union-attr]
        await db.flush()

        with pytest.raises(DocumentNotFoundError):
            await get_document(db, doc_a.id, user_b.id)  # type: ignore[union-attr]

    async def test_list_sources_only_returns_own(
        self, db: AsyncSession, two_users: tuple[object, object]
    ) -> None:
        from writer.models.enums import SourceType
        from writer.models.schemas import DocumentCreate, SourceCreate
        from writer.services.document_service import create_document
        from writer.services.source_service import add_source, list_sources

        user_a, user_b = two_users
        doc_a = await create_document(db, DocumentCreate(title="A doc"), user_a.id)  # type: ignore[union-attr]
        await db.flush()
        await add_source(
            db,
            SourceCreate(
                document_id=doc_a.id,
                source_type=SourceType.note,
                title="A's source",
                content="secret content",
            ),
            user_a.id,  # type: ignore[union-attr]
        )
        await db.flush()

        doc_b = await create_document(db, DocumentCreate(title="B doc"), user_b.id)  # type: ignore[union-attr]
        await db.flush()
        sources_b = await list_sources(db, doc_b.id, user_b.id)  # type: ignore[union-attr]
        assert len(sources_b) == 0
