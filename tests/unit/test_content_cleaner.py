"""Unit tests for LLM-based content cleaning — TDD."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from documentlm_core.services.content_cleaner import _parse_line_range, clean_content

_RAW_MARKDOWN = """\
# Navigation
- Home
- About
- Contact

# The Actual Article Title

This is the main content of the article. It contains several paragraphs
of important information that should be preserved.

## Section Two

More substantive content here.

## Footer
- Privacy Policy
- Terms of Service
- Cookie Settings"""


class TestParseLineRange:
    def test_valid_range(self) -> None:
        assert _parse_line_range("5 20", 25) == (4, 20)

    def test_clamps_to_bounds(self) -> None:
        assert _parse_line_range("0 100", 25) == (0, 25)

    def test_returns_none_on_garbage(self) -> None:
        assert _parse_line_range("not numbers", 25) is None

    def test_returns_none_on_single_number(self) -> None:
        assert _parse_line_range("5", 25) is None

    def test_returns_none_on_inverted_range(self) -> None:
        assert _parse_line_range("20 5", 25) is None


class TestCleanContent:
    async def test_returns_sliced_content(self) -> None:
        # Lines 5-20 cover the article title through "More substantive content here."
        mock_response = MagicMock()
        mock_response.text = "5 20"

        with patch("documentlm_core.services.content_cleaner._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            result = await clean_content(_RAW_MARKDOWN)

        assert "The Actual Article Title" in result
        assert "More substantive content here." in result
        assert "Navigation" not in result

    async def test_falls_back_on_api_error(self) -> None:
        with patch("documentlm_core.services.content_cleaner._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=RuntimeError("API unavailable")
            )
            result = await clean_content(_RAW_MARKDOWN)

        assert result == _RAW_MARKDOWN

    async def test_falls_back_on_empty_response(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "   "

        with patch("documentlm_core.services.content_cleaner._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            result = await clean_content(_RAW_MARKDOWN)

        assert result == _RAW_MARKDOWN

    async def test_falls_back_on_unparseable_response(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "Here is the cleaned content..."

        with patch("documentlm_core.services.content_cleaner._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            result = await clean_content(_RAW_MARKDOWN)

        assert result == _RAW_MARKDOWN

    async def test_returns_none_when_content_missing(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "MISSING"

        with patch("documentlm_core.services.content_cleaner._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            result = await clean_content(_RAW_MARKDOWN)

        assert result is None

    async def test_skips_llm_for_short_content(self) -> None:
        short = "A brief note."

        with patch("documentlm_core.services.content_cleaner._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock()
            result = await clean_content(short)

        mock_client.aio.models.generate_content.assert_not_called()
        assert result == short

    async def test_falls_back_when_over_stripped(self) -> None:
        """If LLM selects a range covering <50% of content, assume it over-cleaned."""
        mock_response = MagicMock()
        # Only lines 5-6 — far too little
        mock_response.text = "5 6"

        with patch("documentlm_core.services.content_cleaner._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            result = await clean_content(_RAW_MARKDOWN)

        assert result == _RAW_MARKDOWN

    async def test_falls_back_on_timeout(self) -> None:
        async def hang_forever(**kwargs: object) -> None:
            await asyncio.sleep(999)

        with (
            patch("documentlm_core.services.content_cleaner._client") as mock_client,
            patch("documentlm_core.services.content_cleaner._TIMEOUT_SECONDS", 0.01),
        ):
            mock_client.aio.models.generate_content = hang_forever
            result = await clean_content(_RAW_MARKDOWN)

        assert result == _RAW_MARKDOWN

    async def test_uses_configured_model(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "1 20"

        with (
            patch("documentlm_core.services.content_cleaner._client") as mock_client,
            patch("documentlm_core.services.content_cleaner.settings") as mock_settings,
        ):
            mock_settings.gemini_model = "gemini-test-model"
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            await clean_content(_RAW_MARKDOWN)

        mock_client.aio.models.generate_content.assert_called_once()
        call_kwargs = mock_client.aio.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-test-model"
