"""Content fetcher — fetches and extracts clean text from a URL (HTML or PDF)."""

from io import BytesIO

import httpx
from bs4 import BeautifulSoup

from writer.core.logging import get_logger

logger = get_logger(__name__)

_USER_AGENT = "Mozilla/5.0 (compatible; writer-bot/1.0)"
_TIMEOUT = 15.0

_NOISE_TAGS = ["nav", "aside", "header", "footer", "script", "style"]


async def fetch_url_content(url: str) -> str:
    """Fetch a URL and return extracted text content.

    For HTML: extracts <article>, then <main>, then <body>,
    stripping <nav>, <aside>, <header>, <footer>, <script>, <style>.
    For PDF: extracts text from all pages via pypdf.

    Raises httpx.HTTPError on network/HTTP failure.
    """
    logger.info("Fetching url=%s", url)

    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        response = await client.get(url, headers={"User-Agent": _USER_AGENT})

    logger.info(
        "Fetched url=%s status=%d content-type=%s size=%d bytes",
        url,
        response.status_code,
        response.headers.get("content-type", "unknown"),
        len(response.content),
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "application/pdf" in content_type:
        logger.info("Extracting PDF content from url=%s", url)
        text = _extract_pdf(response.content)
        logger.info("Extracted PDF text (len=%d) from url=%s", len(text), url)
        return text

    logger.info("Extracting HTML content from url=%s", url)
    text = _extract_html(response.text)
    logger.info("Extracted HTML text (len=%d) from url=%s", len(text), url)
    return text


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    page_count = len(reader.pages)
    logger.debug("PDF has %d pages", page_count)

    pages = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        logger.debug("PDF page %d/%d extracted %d chars", i + 1, page_count, len(page_text))
        pages.append(page_text)

    return "\n".join(pages)


def _extract_html(html: str) -> str:
    logger.debug("Parsing HTML (raw len=%d)", len(html))
    soup = BeautifulSoup(html, "html.parser")

    removed = 0
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
        removed += 1
    logger.debug("Removed %d noise elements (%s)", removed, ", ".join(_NOISE_TAGS))

    article = soup.find("article")
    main = soup.find("main")
    target = article or main or soup.body

    if target is None:
        logger.warning("No suitable content element found in HTML")
        return ""

    chosen = "article" if article else ("main" if main else "body")
    logger.debug("Extracting text from <%s>", chosen)

    text = target.get_text(separator="\n", strip=True)
    logger.debug("Extracted %d chars from <%s>", len(text), chosen)
    return text
