"""Shared fixtures for end-to-end Playwright tests.

No database required. The live_server fixture starts the real FastAPI app in a
background thread with get_current_user, document_service.get_document, and
settings_service.get_settings all patched to return in-memory stubs.
"""

import socket
import threading
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import uvicorn

from writer.core.auth import get_current_user
from writer.core.config import settings
from writer.main import app
from writer.models.schemas import DocumentResponse, UserResponse, UserSettingsResponse

_TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_TEST_DOC_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_TEST_USER = UserResponse(
    id=_TEST_USER_ID,
    email="test@example.com",
    created_at=datetime.now(UTC),
)

_TEST_DOC = DocumentResponse(
    id=_TEST_DOC_ID,
    title="Test Document",
    content="Game Fundamentals\n\nSome content here for testing.",
    overview=None,
    is_private=False,
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)

_TEST_SETTINGS = UserSettingsResponse(
    display_name=None,
    language_code="en",
    ai_instructions=None,
    updated_at=datetime.now(UTC),
)


@pytest.fixture(scope="session")
def live_server():
    """Start the app with all DB calls patched out and return its base URL."""

    async def _get_current_user() -> UserResponse:
        return _TEST_USER

    app.dependency_overrides[get_current_user] = _get_current_user
    settings.dev_seed_doc_email = ""

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)

    with (
        patch("writer.main.document_service.get_document", AsyncMock(return_value=_TEST_DOC)),
        patch("writer.main.settings_service.get_settings", AsyncMock(return_value=_TEST_SETTINGS)),
        patch("writer.core.database._get_engine") as mock_engine,
    ):
        mock_engine.return_value.dispose = AsyncMock()
        thread.start()

        import time
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Test server failed to start")

        yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)
    app.dependency_overrides.clear()
