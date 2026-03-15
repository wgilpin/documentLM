"""TipTap JSON ↔ markdown bidirectional converters.

tiptap_to_markdown: converts TipTap JSON string → markdown for LLM prompts.
markdown_to_tiptap: converts markdown string → TipTap JSON with fresh UUIDs for saving.
"""

import json
import uuid

from markdown_it import MarkdownIt


def _uid() -> str:
    return str(uuid.uuid4())


# ── TipTap JSON → markdown ────────────────────────────────────────────────────

_MARK_WRAP = {"bold": ("**", "**"), "italic": ("_", "_"), "code": ("`", "`")}


def _render(node: dict) -> str:  # type: ignore[type-arg]
    t = node.get("type", "")
    ch = node.get("content", [])

    if t == "doc":
        return "\n\n".join(_render(c) for c in ch)

    if t == "heading":
        level = node.get("attrs", {}).get("level", 1)
        return "#" * level + " " + "".join(_render(c) for c in ch)

    if t == "paragraph":
        return "".join(_render(c) for c in ch)

    if t == "text":
        text = node.get("text", "")
        for mark in node.get("marks", []):
            o, c = _MARK_WRAP.get(mark["type"], ("", ""))
            text = f"{o}{text}{c}"
        return text

    if t == "hardBreak":
        return "\n"

    if t == "bulletList":
        return "\n".join("- " + _render_list_item(item) for item in ch)

    if t == "orderedList":
        return "\n".join(f"{i + 1}. " + _render_list_item(ch[i]) for i in range(len(ch)))

    if t == "listItem":
        return _render_list_item(node)

    if t == "blockquote":
        inner = "\n\n".join(_render(c) for c in ch)
        return "\n".join("> " + line for line in inner.splitlines())

    if t == "codeBlock":
        lang = node.get("attrs", {}).get("language", "") or ""
        code = "".join(_render(c) for c in ch)
        return f"```{lang}\n{code}\n```"

    return "".join(_render(c) for c in ch)


def _render_list_item(node: dict) -> str:  # type: ignore[type-arg]
    return "".join(_render(c) for c in node.get("content", []))


def tiptap_to_markdown(content: str) -> str:
    """TipTap JSON string → markdown string for LLM prompts."""
    if not content:
        return ""
    try:
        return _render(json.loads(content))
    except (json.JSONDecodeError, KeyError):
        return content


# ── markdown → TipTap JSON ────────────────────────────────────────────────────

_md = MarkdownIt()


def _tokens_to_nodes(tokens: list) -> list[dict]:  # type: ignore[type-arg]
    nodes: list[dict] = []  # type: ignore[type-arg]
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == "heading_open":
            level = int(tok.tag[1])
            inline = tokens[i + 1]
            children = _inline_tokens(inline.children or [])
            nodes.append({"type": "heading", "attrs": {"level": level, "id": _uid()},
                          "content": children})
            i += 3
            continue

        if tok.type == "paragraph_open":
            inline = tokens[i + 1]
            children = _inline_tokens(inline.children or [])
            nodes.append({"type": "paragraph", "attrs": {"id": _uid()}, "content": children})
            i += 3
            continue

        if tok.type == "bullet_list_open":
            items, i = _list_items(tokens, i + 1, "bullet_list_close")
            nodes.append({"type": "bulletList", "attrs": {"id": _uid()}, "content": items})
            continue

        if tok.type == "ordered_list_open":
            items, i = _list_items(tokens, i + 1, "ordered_list_close")
            nodes.append({"type": "orderedList", "attrs": {"id": _uid()}, "content": items})
            continue

        if tok.type == "blockquote_open":
            inner, i = _block_until(tokens, i + 1, "blockquote_close")
            nodes.append({"type": "blockquote", "attrs": {"id": _uid()},
                          "content": _tokens_to_nodes(inner)})
            continue

        if tok.type == "fence":
            lang = tok.info.strip() if tok.info else ""
            nodes.append({"type": "codeBlock", "attrs": {"language": lang, "id": _uid()},
                          "content": [{"type": "text", "text": tok.content.rstrip("\n")}]})
            i += 1
            continue

        i += 1

    return nodes


def _inline_tokens(children: list) -> list[dict]:  # type: ignore[type-arg]
    nodes: list[dict] = []  # type: ignore[type-arg]
    active_marks: list[dict] = []  # type: ignore[type-arg]

    for tok in children:
        if tok.type == "softbreak":
            nodes.append({"type": "hardBreak"})
            continue

        if tok.type == "code_inline":
            nodes.append({"type": "text", "marks": [{"type": "code"}], "text": tok.content})
            continue

        if tok.type in ("strong_open", "em_open"):
            active_marks.append({"type": "bold" if tok.type == "strong_open" else "italic"})
            continue

        if tok.type in ("strong_close", "em_close"):
            if active_marks:
                active_marks.pop()
            continue

        if tok.type == "text" and tok.content:
            node: dict = {"type": "text", "text": tok.content}  # type: ignore[type-arg]
            if active_marks:
                node["marks"] = list(active_marks)
            nodes.append(node)

    return nodes


def _list_items(tokens: list, start: int, close_type: str) -> tuple[list, int]:  # type: ignore[type-arg]
    items: list[dict] = []  # type: ignore[type-arg]
    i = start
    while i < len(tokens) and tokens[i].type != close_type:
        tok = tokens[i]
        if tok.type == "list_item_open":
            inner, i = _block_until(tokens, i + 1, "list_item_close")
            items.append({"type": "listItem", "attrs": {"id": _uid()},
                          "content": _tokens_to_nodes(inner)})
        else:
            i += 1
    return items, i + 1


def _block_until(tokens: list, start: int, close_type: str) -> tuple[list, int]:  # type: ignore[type-arg]
    collected = []
    i = start
    depth = 0
    open_type = close_type.replace("close", "open")
    while i < len(tokens):
        if tokens[i].type == open_type:
            depth += 1
        if tokens[i].type == close_type:
            if depth == 0:
                return collected, i + 1
            depth -= 1
        collected.append(tokens[i])
        i += 1
    return collected, i


def markdown_to_tiptap(markdown: str) -> str:
    """Convert a markdown string to TipTap JSON with fresh UUIDs."""
    tokens = _md.parse(markdown or "")
    nodes = _tokens_to_nodes(tokens)
    if not nodes:
        nodes = [{"type": "paragraph", "attrs": {"id": _uid()}, "content": []}]
    return json.dumps({"type": "doc", "content": nodes})
