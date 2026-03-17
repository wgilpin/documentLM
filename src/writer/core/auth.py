"""FastAPI dependency for session-based authentication."""

import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.models.schemas import UserResponse

logger = get_logger(__name__)


class _RedirectToLogin(Exception):
    """Internal sentinel — converted to redirect in the dependency."""


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserResponse:
    """Return the authenticated user from the session cookie.

    Raises a 302 redirect to /auth/login if the session is missing or invalid.
    """
    from writer.services.auth_service import get_user_by_id

    user_id_str: str | None = request.session.get("user_id")
    if not user_id_str:
        logger.info("get_current_user: no user_id in session — redirecting to login")
        raise _redirect_response()

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        logger.warning("get_current_user: invalid user_id in session: %r", user_id_str)
        request.session.clear()
        raise _redirect_response() from None

    user = await get_user_by_id(db, user_id)
    if user is None:
        logger.warning("get_current_user: user_id=%s not found — clearing session", user_id)
        request.session.clear()
        raise _redirect_response()

    return user


def _redirect_response() -> Exception:
    from fastapi import HTTPException

    return HTTPException(
        status_code=302,
        headers={"Location": "/auth/login"},
    )
