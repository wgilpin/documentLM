"""Unit tests for Settings configuration validation."""

import logging

import pytest

from writer.core.config import Settings


def test_undo_buffer_size_valid() -> None:
    s = Settings(undo_buffer_size=500)
    assert s.undo_buffer_size == 500


def test_undo_buffer_size_default() -> None:
    s = Settings()
    assert s.undo_buffer_size == 1000


def test_undo_buffer_size_zero_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="writer.core.config"):
        s = Settings(undo_buffer_size=0)
    assert s.undo_buffer_size == 1000
    assert "UNDO_BUFFER_SIZE" in caplog.text


def test_undo_buffer_size_negative_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="writer.core.config"):
        s = Settings(undo_buffer_size=-5)
    assert s.undo_buffer_size == 1000
    assert "UNDO_BUFFER_SIZE" in caplog.text


def test_undo_buffer_size_non_numeric_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="writer.core.config"):
        s = Settings(undo_buffer_size="banana")
    assert s.undo_buffer_size == 1000
    assert "UNDO_BUFFER_SIZE" in caplog.text
