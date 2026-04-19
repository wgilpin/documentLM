"""Unit tests for filter scope parsing."""

import uuid

import pytest

from writer.models.schemas import FilterScopeAll, FilterScopeChapter, FilterScopeDocLevel
from writer.services.filter_scope import FilterScopeParseError, parse_filter_scope


def test_parse_all_returns_filter_scope_all() -> None:
    scope = parse_filter_scope("all")
    assert isinstance(scope, FilterScopeAll)
    assert scope.kind == "all"


def test_parse_doc_level_returns_filter_scope_doc_level() -> None:
    scope = parse_filter_scope("doc-level")
    assert isinstance(scope, FilterScopeDocLevel)
    assert scope.kind == "doc-level"


def test_parse_chapter_uuid_returns_filter_scope_chapter() -> None:
    chapter_id = uuid.uuid4()
    scope = parse_filter_scope(f"chapter:{chapter_id}")
    assert isinstance(scope, FilterScopeChapter)
    assert scope.chapter_id == chapter_id


def test_parse_empty_string_raises() -> None:
    with pytest.raises(FilterScopeParseError):
        parse_filter_scope("")


def test_parse_unknown_kind_raises() -> None:
    with pytest.raises(FilterScopeParseError):
        parse_filter_scope("everything")


def test_parse_chapter_without_uuid_raises() -> None:
    with pytest.raises(FilterScopeParseError):
        parse_filter_scope("chapter:")


def test_parse_chapter_with_invalid_uuid_raises() -> None:
    with pytest.raises(FilterScopeParseError):
        parse_filter_scope("chapter:not-a-uuid")


def test_parse_doc_level_with_suffix_raises() -> None:
    with pytest.raises(FilterScopeParseError):
        parse_filter_scope("doc-level:garbage")
