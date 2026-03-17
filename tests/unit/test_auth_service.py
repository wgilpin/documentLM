"""Unit tests for auth_service — TDD (write first, confirm fail, then implement)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from writer.models.schemas import UserResponse


def _make_user(**kwargs: object) -> MagicMock:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "password_hash": "$2b$12$fakehash",
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    user = MagicMock()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _make_invite(used_at: object = None) -> MagicMock:
    invite = MagicMock()
    invite.id = uuid.uuid4()
    invite.code = "a" * 32
    invite.used_at = used_at
    invite.used_by_user_id = None
    return invite


class TestHashPassword:
    def test_returns_string(self) -> None:
        from writer.services.auth_service import hash_password

        result = hash_password("mysecretpass")
        assert isinstance(result, str)

    def test_not_plaintext(self) -> None:
        from writer.services.auth_service import hash_password

        result = hash_password("mysecretpass")
        assert result != "mysecretpass"

    def test_different_hash_each_call(self) -> None:
        from writer.services.auth_service import hash_password

        h1 = hash_password("mysecretpass")
        h2 = hash_password("mysecretpass")
        assert h1 != h2  # bcrypt salts


class TestVerifyPassword:
    def test_correct_password_returns_true(self) -> None:
        from writer.services.auth_service import hash_password, verify_password

        hashed = hash_password("correct_pass")
        assert verify_password("correct_pass", hashed) is True

    def test_wrong_password_returns_false(self) -> None:
        from writer.services.auth_service import hash_password, verify_password

        hashed = hash_password("correct_pass")
        assert verify_password("wrong_pass", hashed) is False


class TestRegisterUser:
    async def test_register_with_valid_code_creates_user(self) -> None:
        from writer.services.auth_service import register_user

        db = AsyncMock()
        invite = _make_invite()
        user = _make_user()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = invite
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        import contextlib

        def _refresh(obj: object) -> None:
            for k, v in vars(user).items():
                if not k.startswith("_"):
                    with contextlib.suppress(Exception):
                        setattr(obj, k, v)

        db.refresh = AsyncMock(side_effect=_refresh)

        with patch("writer.services.auth_service.User") as MockUser:
            MockUser.return_value = user
            result = await register_user(db, "a" * 32, "test@example.com", "password123")

        assert isinstance(result, UserResponse)
        db.add.assert_called()

    async def test_register_with_used_code_raises(self) -> None:
        from writer.services.auth_service import InvalidInviteCodeError, register_user

        db = AsyncMock()
        invite = _make_invite(used_at=datetime.now(UTC))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = invite
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(InvalidInviteCodeError):
            await register_user(db, "a" * 32, "test@example.com", "password123")

    async def test_register_with_missing_code_raises(self) -> None:
        from writer.services.auth_service import InvalidInviteCodeError, register_user

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(InvalidInviteCodeError):
            await register_user(db, "nonexistent", "test@example.com", "password123")

    async def test_register_short_password_raises(self) -> None:
        from writer.services.auth_service import register_user

        db = AsyncMock()
        with pytest.raises(ValueError, match="password"):
            await register_user(db, "a" * 32, "test@example.com", "short")

    async def test_register_duplicate_email_raises(self) -> None:
        from sqlalchemy.exc import IntegrityError

        from writer.services.auth_service import DuplicateEmailError, register_user

        db = AsyncMock()
        invite = _make_invite()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = invite
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

        with (
            patch("writer.services.auth_service.User"),
            pytest.raises(DuplicateEmailError),
        ):
            await register_user(db, "a" * 32, "already@example.com", "password123")


class TestAuthenticateUser:
    async def test_correct_credentials_returns_user(self) -> None:
        from writer.services.auth_service import authenticate_user, hash_password

        db = AsyncMock()
        pw = "correct_password"
        user = _make_user(password_hash=hash_password(pw))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        db.execute = AsyncMock(return_value=mock_result)

        result = await authenticate_user(db, "test@example.com", pw)
        assert result is not None
        assert isinstance(result, UserResponse)

    async def test_wrong_password_returns_none(self) -> None:
        from writer.services.auth_service import authenticate_user, hash_password

        db = AsyncMock()
        user = _make_user(password_hash=hash_password("correct_password"))

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        db.execute = AsyncMock(return_value=mock_result)

        result = await authenticate_user(db, "test@example.com", "wrong_password")
        assert result is None

    async def test_unknown_email_returns_none(self) -> None:
        from writer.services.auth_service import authenticate_user

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await authenticate_user(db, "nobody@example.com", "any_password")
        assert result is None


class TestCreateInviteCodes:
    async def test_returns_correct_count(self) -> None:
        from writer.services.auth_service import create_invite_codes

        db = AsyncMock()
        db.flush = AsyncMock()

        result = await create_invite_codes(db, count=3)
        assert len(result) == 3

    async def test_returns_32_char_hex_strings(self) -> None:
        from writer.services.auth_service import create_invite_codes

        db = AsyncMock()
        db.flush = AsyncMock()

        result = await create_invite_codes(db, count=2)
        for code in result:
            assert len(code) == 32
            assert all(c in "0123456789abcdef" for c in code)

    async def test_all_codes_unique(self) -> None:
        from writer.services.auth_service import create_invite_codes

        db = AsyncMock()
        db.flush = AsyncMock()

        result = await create_invite_codes(db, count=5)
        assert len(set(result)) == 5

    async def test_codes_persisted_to_db(self) -> None:
        from writer.services.auth_service import create_invite_codes

        db = AsyncMock()
        db.flush = AsyncMock()

        await create_invite_codes(db, count=2)
        assert db.add.call_count == 2


class TestResetPassword:
    async def test_updates_hash_for_known_email(self) -> None:
        from writer.services.auth_service import reset_password

        db = AsyncMock()
        user = _make_user()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        await reset_password(db, "test@example.com", "newpassword123")

        assert user.password_hash != "newpassword123"  # must be hashed
        assert user.password_hash != "$2b$12$fakehash"  # must have changed
        db.flush.assert_called()

    async def test_unknown_email_raises(self) -> None:
        from writer.services.auth_service import UserNotFoundError, reset_password

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(UserNotFoundError):
            await reset_password(db, "nobody@example.com", "newpassword123")

    async def test_short_password_raises(self) -> None:
        from writer.services.auth_service import reset_password

        db = AsyncMock()
        with pytest.raises(ValueError, match="password"):
            await reset_password(db, "test@example.com", "short")
