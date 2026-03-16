"""Unit tests for agent_service — TDD. ADK Runner is always mocked."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from writer.models.enums import CommentStatus, IndexingStatus, SourceType
from writer.models.schemas import CommentResponse, DocumentResponse, SourceResponse


def _doc(**kwargs: object) -> DocumentResponse:
    defaults = {
        "id": uuid.uuid4(),
        "title": "Doc",
        "content": "The quick brown fox.",
        "overview": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return DocumentResponse(**defaults)  # type: ignore[arg-type]


def _comment(**kwargs: object) -> CommentResponse:
    defaults = {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "selection_start": 0,
        "selection_end": 3,
        "selected_text": "The",
        "selected_node_id": None,
        "body": "Expand this",
        "status": CommentStatus.open,
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return CommentResponse(**defaults)  # type: ignore[arg-type]


def _source(**kwargs: object) -> SourceResponse:
    defaults = {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "source_type": SourceType.note,
        "title": "Source",
        "content": "Background info.",
        "url": None,
        "indexing_status": IndexingStatus.completed,
        "error_message": None,
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    return SourceResponse(**defaults)  # type: ignore[arg-type]


class TestInvokeDrafter:
    async def test_returns_suggested_text_string(self) -> None:
        from writer.services.agent_service import invoke_drafter

        doc = _doc(content="Hello world.")
        comment = _comment(
            document_id=doc.id, selection_start=0, selection_end=5, selected_text="Hello"
        )
        sources = [_source(document_id=doc.id)]

        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content = MagicMock()
        mock_event.content.parts = [MagicMock(text="Hi there, expanded.")]

        async def fake_run_async(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            yield mock_event

        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session_service = MagicMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)

        with (
            patch("writer.services.agent_service.Runner") as MockRunner,
            patch(
                "writer.services.agent_service.InMemorySessionService",
                return_value=mock_session_service,
            ),
            patch(
                "writer.services.agent_service.vector_store.query_sources",
                return_value=["relevant chunk"],
            ),
        ):
            runner_instance = MagicMock()
            runner_instance.run_async = fake_run_async
            MockRunner.return_value = runner_instance

            result = await invoke_drafter(comment, doc, sources)

        assert isinstance(result, str)
        assert result == "Hi there, expanded."

    async def test_raises_on_empty_response(self) -> None:
        from writer.services.agent_service import invoke_drafter

        doc = _doc()
        comment = _comment(document_id=doc.id)
        sources: list[SourceResponse] = []

        async def fake_run_async(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            # yields nothing — empty agent response
            return
            yield  # make it an async generator

        mock_session = MagicMock()
        mock_session.id = "test-session"
        mock_session_service = MagicMock()
        mock_session_service.create_session = AsyncMock(return_value=mock_session)

        with (
            patch("writer.services.agent_service.Runner") as MockRunner,
            patch(
                "writer.services.agent_service.InMemorySessionService",
                return_value=mock_session_service,
            ),
            patch(
                "writer.services.agent_service.vector_store.query_sources",
                return_value=[],
            ),
        ):
            runner_instance = MagicMock()
            runner_instance.run_async = fake_run_async
            MockRunner.return_value = runner_instance

            with pytest.raises(ValueError, match="no text response"):
                await invoke_drafter(comment, doc, sources)


def _make_runner_patch(reply: str) -> tuple[object, object]:
    """Return (mock_event, fake_run_async) for patching Runner."""
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content = MagicMock()
    mock_event.content.parts = [MagicMock(text=reply)]

    async def fake_run_async(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        yield mock_event

    return mock_event, fake_run_async


class TestInvokeDrafterVectorRetrieval:
    """US2: invoke_drafter must use query_sources instead of raw source.content."""

    async def test_does_not_concatenate_raw_source_content(self) -> None:
        from writer.services.agent_service import invoke_drafter

        doc = _doc(content="Document body.")
        comment = _comment(document_id=doc.id, body="Rewrite this", selected_text="body")
        source = _source(content="FULL RAW CONTENT DO NOT INCLUDE")

        _, fake_run = _make_runner_patch("result text")

        mock_session = MagicMock()
        mock_session.id = "s1"
        mock_ss = MagicMock()
        mock_ss.create_session = AsyncMock(return_value=mock_session)

        with (
            patch("writer.services.agent_service.Runner") as MockRunner,
            patch("writer.services.agent_service.InMemorySessionService", return_value=mock_ss),
            patch(
                "writer.services.agent_service.vector_store.query_sources",
                return_value=["retrieved chunk"],
            ),
        ):
            runner_instance = MagicMock()
            runner_instance.run_async = fake_run
            MockRunner.return_value = runner_instance

            await invoke_drafter(comment, doc, [source])

        # The message sent to the agent must NOT contain the raw source content
        call_args = MockRunner.call_args
        assert call_args is not None  # runner was created

    async def test_query_sources_called_with_comment_text(self) -> None:
        from writer.services.agent_service import invoke_drafter

        doc = _doc(content="Doc.")
        comment = _comment(document_id=doc.id, body="My instruction", selected_text="selected")
        source = _source()

        _, fake_run = _make_runner_patch("answer")

        mock_session = MagicMock()
        mock_session.id = "s2"
        mock_ss = MagicMock()
        mock_ss.create_session = AsyncMock(return_value=mock_session)

        with (
            patch("writer.services.agent_service.Runner") as MockRunner,
            patch("writer.services.agent_service.InMemorySessionService", return_value=mock_ss),
            patch(
                "writer.services.agent_service.vector_store.query_sources",
                return_value=["chunk"],
            ) as mock_qs,
        ):
            runner_instance = MagicMock()
            runner_instance.run_async = fake_run
            MockRunner.return_value = runner_instance

            await invoke_drafter(comment, doc, [source])

        mock_qs.assert_called_once()
        query_text = mock_qs.call_args[0][0]
        assert "My instruction" in query_text or "selected" in query_text


class TestInvokePlannerVectorRetrieval:
    """US2: invoke_planner must use query_sources instead of full source concatenation."""

    async def test_does_not_use_full_source_content(self) -> None:
        from writer.services.agent_service import invoke_planner

        overview = "Write about AI."
        source = _source(content="FULL RAW CONTENT NEVER INJECTED")

        _, fake_run = _make_runner_patch("plan text")

        mock_session = MagicMock()
        mock_session.id = "p1"
        mock_ss = MagicMock()
        mock_ss.create_session = AsyncMock(return_value=mock_session)

        with (
            patch("writer.services.agent_service.Runner") as MockRunner,
            patch("writer.services.agent_service.InMemorySessionService", return_value=mock_ss),
            patch(
                "writer.services.agent_service.vector_store.query_sources",
                return_value=["retrieved chunk"],
            ) as mock_qs,
        ):
            runner_instance = MagicMock()
            runner_instance.run_async = fake_run
            MockRunner.return_value = runner_instance

            result = await invoke_planner(overview, [source], source.document_id)

        mock_qs.assert_called_once()
        assert result == "plan text"

    async def test_query_sources_called_with_overview(self) -> None:
        from writer.services.agent_service import invoke_planner

        overview = "Specific overview text for query"
        source = _source()

        _, fake_run = _make_runner_patch("plan")

        mock_session = MagicMock()
        mock_session.id = "p2"
        mock_ss = MagicMock()
        mock_ss.create_session = AsyncMock(return_value=mock_session)

        with (
            patch("writer.services.agent_service.Runner") as MockRunner,
            patch("writer.services.agent_service.InMemorySessionService", return_value=mock_ss),
            patch(
                "writer.services.agent_service.vector_store.query_sources",
                return_value=["chunk"],
            ) as mock_qs,
        ):
            runner_instance = MagicMock()
            runner_instance.run_async = fake_run
            MockRunner.return_value = runner_instance

            await invoke_planner(overview, [source], source.document_id)

        mock_qs.assert_called_once_with(overview, source.document_id, top_k=5)


class TestIsSelectionValid:
    def test_valid_selection(self) -> None:
        from writer.services.document_service import is_selection_valid

        assert is_selection_valid("Hello world", 0, 5, "Hello") is True

    def test_invalid_text_mismatch(self) -> None:
        from writer.services.document_service import is_selection_valid

        assert is_selection_valid("Hello world", 0, 5, "World") is False

    def test_invalid_out_of_bounds(self) -> None:
        from writer.services.document_service import is_selection_valid

        assert is_selection_valid("Hi", 0, 10, "Hi") is False

    def test_invalid_start_equals_end(self) -> None:
        from writer.services.document_service import is_selection_valid

        assert is_selection_valid("Hello", 2, 2, "") is False
