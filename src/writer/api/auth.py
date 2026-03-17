"""Authentication routes — login, register, logout."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from writer.core.database import get_db
from writer.core.logging import get_logger
from writer.core.templates import templates
from writer.services.auth_service import (
    DuplicateEmailError,
    InvalidInviteCodeError,
    authenticate_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)  # type: ignore[return-value]
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_model=None)
async def login(
    request: Request,
    db: DbDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> RedirectResponse | HTMLResponse:
    user = await authenticate_user(db, email, password)
    if user is None:
        logger.warning("login: failed attempt for email=%r", email)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password.", "email": email},
            status_code=200,
        )
    request.session["user_id"] = str(user.id)
    logger.info("login: success for user id=%s", user.id)
    return RedirectResponse(url="/", status_code=302)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)  # type: ignore[return-value]
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_model=None)
async def register(
    request: Request,
    db: DbDep,
    invite_code: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> RedirectResponse | HTMLResponse:
    try:
        user = await register_user(db, invite_code, email, password)
    except InvalidInviteCodeError:
        logger.warning("register: invalid invite code used")
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Invalid or already-used invite code.",
                "email": email,
                "invite_code": invite_code,
            },
            status_code=200,
        )
    except DuplicateEmailError:
        logger.warning("register: duplicate email=%r", email)
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "That email address is already registered.",
                "email": email,
                "invite_code": invite_code,
            },
            status_code=200,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": str(exc),
                "email": email,
                "invite_code": invite_code,
            },
            status_code=200,
        )

    await db.commit()
    request.session["user_id"] = str(user.id)
    logger.info("register: created and logged in user id=%s", user.id)
    return RedirectResponse(url="/", status_code=302)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    logger.info("logout: session cleared")
    return RedirectResponse(url="/auth/login", status_code=302)
