"""Unit tests for invoke_bounded_drafter — TDD."""

from unittest.mock import AsyncMock, patch

import pytest


class TestInvokeBoundedDrafter:
    async def test_returns_generated_text(self) -> None:
        from writer.services.agent_service import invoke_bounded_drafter

        snippets = [("Residents reported health issues", "Interview Transcripts 2024")]
        intent = "Synthesise evidence of health impacts"
        cursor_context = "## Health Impact\n\n"
        document_content = "# Report\n\n## Introduction\n\nSome intro text."

        with patch(
            "writer.services.agent_service.run_agent_text",
            new=AsyncMock(return_value="generated text"),
        ):
            result = await invoke_bounded_drafter(
                snippets=snippets,
                intent=intent,
                cursor_context=cursor_context,
                document_content=document_content,
            )

        assert result == "generated text"

    async def test_prompt_contains_document_content(self) -> None:
        from writer.services.agent_service import invoke_bounded_drafter

        document_content = "# Full Document Content\n\nWith paragraphs."
        captured_messages: list[str] = []

        async def capture_call(agent: object, message: str, *args: object, **kwargs: object) -> str:
            captured_messages.append(message)
            return "response"

        with patch("writer.services.agent_service.run_agent_text", side_effect=capture_call):
            await invoke_bounded_drafter(
                snippets=[],
                intent="Write something",
                cursor_context="",
                document_content=document_content,
            )

        assert len(captured_messages) == 1
        assert document_content in captured_messages[0]

    async def test_prompt_contains_snippet_with_source_title(self) -> None:
        from writer.services.agent_service import invoke_bounded_drafter

        snippets = [("Key finding text", "Research Paper 2024")]
        captured_messages: list[str] = []

        async def capture_call(agent: object, message: str, *args: object, **kwargs: object) -> str:
            captured_messages.append(message)
            return "response"

        with patch("writer.services.agent_service.run_agent_text", side_effect=capture_call):
            await invoke_bounded_drafter(
                snippets=snippets,
                intent="Summarise findings",
                cursor_context="",
                document_content="doc content",
            )

        assert "Key finding text" in captured_messages[0]
        assert "Research Paper 2024" in captured_messages[0]

    async def test_prompt_contains_cursor_context(self) -> None:
        from writer.services.agent_service import invoke_bounded_drafter

        cursor_context = "## Climate Change\n\nThe following section discusses..."
        captured_messages: list[str] = []

        async def capture_call(agent: object, message: str, *args: object, **kwargs: object) -> str:
            captured_messages.append(message)
            return "response"

        with patch("writer.services.agent_service.run_agent_text", side_effect=capture_call):
            await invoke_bounded_drafter(
                snippets=[],
                intent="Write an analysis",
                cursor_context=cursor_context,
                document_content="doc",
            )

        assert cursor_context in captured_messages[0]

    async def test_prompt_contains_intent(self) -> None:
        from writer.services.agent_service import invoke_bounded_drafter

        intent = "Synthesise these quotes to highlight a contradiction"
        captured_messages: list[str] = []

        async def capture_call(agent: object, message: str, *args: object, **kwargs: object) -> str:
            captured_messages.append(message)
            return "response"

        with patch("writer.services.agent_service.run_agent_text", side_effect=capture_call):
            await invoke_bounded_drafter(
                snippets=[],
                intent=intent,
                cursor_context="",
                document_content="doc",
            )

        assert intent in captured_messages[0]

    async def test_zero_snippets_still_calls_agent(self) -> None:
        from writer.services.agent_service import invoke_bounded_drafter

        with patch(
            "writer.services.agent_service.run_agent_text",
            new=AsyncMock(return_value="generated"),
        ) as mock_agent:
            result = await invoke_bounded_drafter(
                snippets=[],
                intent="Write something about climate",
                cursor_context="",
                document_content="document",
            )

        mock_agent.assert_called_once()
        assert result == "generated"

    async def test_empty_intent_raises_value_error(self) -> None:
        from writer.services.agent_service import invoke_bounded_drafter

        with pytest.raises(ValueError, match="intent"):
            await invoke_bounded_drafter(
                snippets=[],
                intent="",
                cursor_context="",
                document_content="doc",
            )
