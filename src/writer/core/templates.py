"""Shared Jinja2Templates instance with custom filters."""

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup

_md = MarkdownIt()


def _render_markdown(text: str) -> Markup:
    return Markup(_md.render(text))


templates = Jinja2Templates(directory="src/writer/templates")
templates.env.filters["markdown"] = _render_markdown
