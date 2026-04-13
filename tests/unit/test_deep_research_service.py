"""Unit tests for deep_research_service — TDD, no remote API calls."""

from writer.services.deep_research_service import (
    extract_urls,
    parse_markdown_document,
)

# ---------------------------------------------------------------------------
# T002: extract_urls
# ---------------------------------------------------------------------------


def test_extract_urls_standard_link() -> None:
    markdown = "See [Google](https://google.com) for more."
    result = extract_urls(markdown)
    assert len(result) == 1
    assert result[0]["url"] == "https://google.com"
    assert result[0]["title"] == "Google"


def test_extract_urls_multiple_links() -> None:
    markdown = "See [Google](https://google.com) and [GitHub](https://github.com) for more."
    result = extract_urls(markdown)
    assert len(result) == 2
    urls = [r["url"] for r in result]
    assert "https://google.com" in urls
    assert "https://github.com" in urls


def test_extract_urls_dedup() -> None:
    markdown = "[Google](https://google.com) and again [Google](https://google.com)."
    result = extract_urls(markdown)
    assert len(result) == 1
    assert result[0]["url"] == "https://google.com"


def test_extract_urls_non_http_links_ignored() -> None:
    markdown = "[FTP link](ftp://example.com) and [relative](../page.html)"
    result = extract_urls(markdown)
    assert result == []


def test_extract_urls_display_text_equals_url_uses_domain() -> None:
    url = "https://cloud.google.com/discover/what-is-vibe-coding"
    markdown = f"[{url}]({url})"
    result = extract_urls(markdown)
    assert len(result) == 1
    assert result[0]["url"] == url
    assert result[0]["title"] == "cloud.google.com"


def test_extract_urls_empty_markdown() -> None:
    result = extract_urls("")
    assert result == []


def test_extract_urls_no_https_links() -> None:
    markdown = "Just plain text with no links here."
    result = extract_urls(markdown)
    assert result == []


def test_extract_urls_preserves_first_occurrence_title_on_dedup() -> None:
    markdown = "[First Title](https://example.com) then [Second Title](https://example.com)"
    result = extract_urls(markdown)
    assert len(result) == 1
    assert result[0]["title"] == "First Title"


# ---------------------------------------------------------------------------
# T003: parse_markdown_document
# ---------------------------------------------------------------------------


def test_parse_markdown_document_title_from_h1() -> None:
    content = "# My Research Title\n\nSome body text."
    result = parse_markdown_document(content, "my_file.md")
    assert result["title"] == "My Research Title"


def test_parse_markdown_document_title_from_h2() -> None:
    content = "## Section Title\n\nBody."
    result = parse_markdown_document(content, "my_file.md")
    assert result["title"] == "Section Title"


def test_parse_markdown_document_title_from_h3() -> None:
    content = "### Sub Section\n\nBody."
    result = parse_markdown_document(content, "my_file.md")
    assert result["title"] == "Sub Section"


def test_parse_markdown_document_filename_fallback() -> None:
    content = "No headings here, just body text."
    result = parse_markdown_document(content, "my_research.md")
    assert result["title"] == "my_research"


def test_parse_markdown_document_filename_fallback_no_md_extension() -> None:
    content = "No headings."
    result = parse_markdown_document(content, "research_doc")
    assert result["title"] == "research_doc"


def test_parse_markdown_document_body_equals_full_content() -> None:
    content = "# Title\n\nFull body content here.\n\nMore text."
    result = parse_markdown_document(content, "file.md")
    assert result["body"] == content


def test_parse_markdown_document_references_from_extract_urls() -> None:
    content = "# Title\n\nSee [Google](https://google.com)."
    result = parse_markdown_document(content, "file.md")
    assert len(result["references"]) == 1
    assert result["references"][0]["url"] == "https://google.com"


def test_parse_markdown_document_uses_first_heading() -> None:
    content = "# First Heading\n\n## Second Heading\n\nBody."
    result = parse_markdown_document(content, "file.md")
    assert result["title"] == "First Heading"


# ---------------------------------------------------------------------------
# T008: empty content and no-link edge cases
# ---------------------------------------------------------------------------


def test_parse_markdown_document_empty_content() -> None:
    result = parse_markdown_document("", "empty.md")
    assert result["body"] == ""
    assert result["references"] == []
    assert result["title"] == "empty"


def test_extract_urls_file_with_no_https_links_returns_empty() -> None:
    content = "# Heading\n\nSome text without any hyperlinks.\n\n- bullet\n- list"
    result = extract_urls(content)
    assert result == []
