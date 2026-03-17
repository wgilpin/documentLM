"""Integration tests for auth_service against a real PostgreSQL database.

Run with: docker-compose up -d postgres && uv run pytest tests/integration/
Requires DATABASE_URL env var pointing to a test-ready PostgreSQL instance.
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


class TestRegistrationFlow:
    async def test_register_with_valid_invite_creates_user(self, db: AsyncSession) -> None:
        from writer.services.auth_service import create_invite_codes, register_user

        codes = await create_invite_codes(db, count=1)
        await db.flush()

        result = await register_user(db, codes[0], "new@example.com", "password123")

        assert result.email == "new@example.com"
        assert result.id is not None

    async def test_register_marks_code_as_used(self, db: AsyncSession) -> None:
        from sqlalchemy import select

        from writer.models.db import InviteCode
        from writer.services.auth_service import create_invite_codes, register_user

        codes = await create_invite_codes(db, count=1)
        await db.flush()

        await register_user(db, codes[0], "new2@example.com", "password123")
        await db.flush()

        result = await db.execute(select(InviteCode).where(InviteCode.code == codes[0]))
        invite = result.scalar_one_or_none()
        assert invite is not None
        assert invite.used_at is not None
        assert invite.used_by_user_id is not None

    async def test_register_with_used_code_rejected(self, db: AsyncSession) -> None:
        from writer.services.auth_service import (
            InvalidInviteCodeError,
            create_invite_codes,
            register_user,
        )

        codes = await create_invite_codes(db, count=1)
        await db.flush()

        await register_user(db, codes[0], "first@example.com", "password123")
        await db.flush()

        with pytest.raises(InvalidInviteCodeError):
            await register_user(db, codes[0], "second@example.com", "password123")

    async def test_register_with_duplicate_email_rejected(self, db: AsyncSession) -> None:
        from writer.services.auth_service import (
            DuplicateEmailError,
            create_invite_codes,
            register_user,
        )

        codes = await create_invite_codes(db, count=2)
        await db.flush()

        await register_user(db, codes[0], "dupe@example.com", "password123")
        await db.flush()

        with pytest.raises(DuplicateEmailError):
            await register_user(db, codes[1], "dupe@example.com", "password456")


class TestLoginFlow:
    async def test_login_with_correct_credentials_returns_user(self, db: AsyncSession) -> None:
        from writer.services.auth_service import (
            authenticate_user,
            create_invite_codes,
            register_user,
        )

        codes = await create_invite_codes(db, count=1)
        await db.flush()
        await register_user(db, codes[0], "login@example.com", "correctpass")
        await db.flush()

        result = await authenticate_user(db, "login@example.com", "correctpass")
        assert result is not None
        assert result.email == "login@example.com"

    async def test_login_with_wrong_password_returns_none(self, db: AsyncSession) -> None:
        from writer.services.auth_service import (
            authenticate_user,
            create_invite_codes,
            register_user,
        )

        codes = await create_invite_codes(db, count=1)
        await db.flush()
        await register_user(db, codes[0], "pwtest@example.com", "correctpass")
        await db.flush()

        result = await authenticate_user(db, "pwtest@example.com", "wrongpass")
        assert result is None

    async def test_login_unknown_email_returns_none(self, db: AsyncSession) -> None:
        from writer.services.auth_service import authenticate_user

        result = await authenticate_user(db, "nobody@example.com", "anypassword")
        assert result is None
