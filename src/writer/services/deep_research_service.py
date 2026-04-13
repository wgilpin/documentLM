"""Parse Google Deep Research Markdown exports into structured data."""

import re
from typing import TypedDict
from urllib.parse import urlparse

from writer.core.logging import get_logger

logger = get_logger(__name__)

_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)", re.MULTILINE)


class ExtractedReference(TypedDict):
    title: str
    url: str


class DeepResearchParseResult(TypedDict):
    title: str
    body: str
    references: list[ExtractedReference]


def extract_urls(markdown: str) -> list[ExtractedReference]:
    """Extract and deduplicate https:// URLs from Markdown link syntax.

    Display text equal to the full URL is replaced with the domain name.
    """
    seen: dict[str, ExtractedReference] = {}
    for display_text, url in _LINK_RE.findall(markdown):
        if url in seen:
            continue
        title = display_text
        if display_text == url:
            parsed = urlparse(url)
            title = parsed.netloc or url
        seen[url] = ExtractedReference(title=title, url=url)
    result = list(seen.values())
    logger.debug("extract_urls: found %d unique URLs", len(result))
    return result


def parse_markdown_document(content: str, filename: str) -> DeepResearchParseResult:
    """Parse a Deep Research Markdown export into title, body, and references.

    Title is taken from the first H1/H2/H3 heading, or falls back to the
    filename with the .md extension stripped.
    """
    heading_match = _HEADING_RE.search(content)
    title = heading_match.group(1).strip() if heading_match else filename.removesuffix(".md")

    references = extract_urls(content)
    logger.debug("parse_markdown_document: title=%r, references=%d", title, len(references))
    return DeepResearchParseResult(title=title, body=content, references=references)
