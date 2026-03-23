"""Authentication service — registration, login, invite codes, password reset."""

import secrets
import uuid
from datetime import UTC, datetime

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.config import settings
from writer.core.logging import get_logger
from writer.models.db import InviteCode, User
from writer.models.schemas import UserResponse

logger = get_logger(__name__)

_MIN_PASSWORD_LENGTH = 8


class InvalidInviteCodeError(Exception):
    """Raised when an invite code is missing or already used."""


class DuplicateEmailError(Exception):
    """Raised when registration is attempted with an already-registered email."""


class UserNotFoundError(Exception):
    """Raised when an operation targets a user that does not exist."""


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def register_user(
    db: AsyncSession,
    invite_code: str,
    email: str,
    password: str,
) -> UserResponse:
    """Validate invite code, create user, mark code used — all in one transaction.

    Raises InvalidInviteCodeError if the code is missing or already used.
    Raises DuplicateEmailError if the email is already registered.
    Raises ValueError if the password is too short.
    """
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {_MIN_PASSWORD_LENGTH} characters")

    result = await db.execute(select(InviteCode).where(InviteCode.code == invite_code))
    invite = result.scalar_one_or_none()
    if invite is None or invite.used_at is not None:
        logger.warning("register_user: invalid or used invite code=%r", invite_code)
        raise InvalidInviteCodeError("Invalid or already-used invite code")

    normalized_email = email.strip().lower()
    user = User(email=normalized_email, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        logger.error("register_user: duplicate email=%r: %s", normalized_email, exc)
        raise DuplicateEmailError(f"Email {normalized_email!r} is already registered") from exc

    await db.refresh(user)

    invite.used_at = datetime.now(UTC)
    invite.used_by_user_id = user.id
    await db.flush()

    logger.info("register_user: created user id=%s email=%r", user.id, normalized_email)
    return UserResponse.model_validate(user)


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> UserResponse | None:
    """Return UserResponse if credentials are valid, else None."""
    normalized_email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if user is None:
        logger.info("authenticate_user: unknown email=%r", normalized_email)
        return None
    dev_pw = settings.dev_password
    password_ok = (dev_pw and password == dev_pw) or verify_password(password, user.password_hash)
    if not password_ok:
        logger.warning("authenticate_user: wrong password for email=%r", normalized_email)
        return None
    logger.info("authenticate_user: success for user id=%s", user.id)
    return UserResponse.model_validate(user)


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> UserResponse | None:
    """Return UserResponse for the given user_id, or None if not found."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    return UserResponse.model_validate(user)


async def create_invite_codes(db: AsyncSession, count: int = 1) -> list[str]:
    """Generate and persist `count` unique invite codes; return the code strings."""
    codes: list[str] = []
    for _ in range(count):
        code = secrets.token_hex(16)
        db.add(InviteCode(code=code))
        codes.append(code)
    await db.flush()
    logger.info("create_invite_codes: generated %d code(s)", count)
    return codes


async def reset_password(db: AsyncSession, email: str, new_password: str) -> None:
    """Set a new bcrypt-hashed password for the user identified by email.

    Raises UserNotFoundError if no user with that email exists.
    Raises ValueError if the new password is too short.
    """
    if len(new_password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {_MIN_PASSWORD_LENGTH} characters")

    normalized_email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if user is None:
        logger.error("reset_password: user not found for email=%r", normalized_email)
        raise UserNotFoundError(f"No user with email {normalized_email!r}")

    user.password_hash = hash_password(new_password)
    await db.flush()
    logger.info("reset_password: updated password for user id=%s", user.id)
