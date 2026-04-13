# Research: Bounded Generation & Curation Workflow

**Feature**: 015-bounded-generation
**Phase**: Phase 0 — Research & Unknowns Resolution
**Date**: 2026-04-13

---

## Decision 1: PDF → Markdown Extraction Library

**Decision**: Use `pymupdf4llm` (wraps PyMuPDF / fitz) for PDF-to-Markdown conversion.

**Rationale**:

- Explicitly requested by user: "using PyMuPDF4LLM for pdf→ markdown processing"
- `pymupdf4llm.to_markdown(fitz.open(path_or_bytes))` produces structured markdown with headings, tables, and inline formatting extracted from the native PDF text layer.
- Lightweight — no model weights, no network calls, purely native text extraction.
- Replaces the existing `pypdf` extraction in `source_service._extract_pdf_text`.
- Output markdown is stored in `Source.content` (replaces plain text).

**Alternatives considered**:

- `pypdf` (current): plain text only, loses heading structure — rejected.
- Vision-based OCR models (e.g. surya, nougat): too heavy, against spec constraints — rejected.

**Implementation note**:

- Add `pymupdf4llm` to `src/writer/pyproject.toml` (writer package, not core).
- The `pypdf` dependency can remain or be removed; `pymupdf4llm` installs `pymupdf` (fitz) internally.
- Scanned/image-only PDFs return empty content from PyMuPDF; the service should detect this and surface an error rather than silently returning an empty source.
- The existing `indexer.py` chunk pipeline works unchanged — `chunk_sentences` operates on the markdown string, producing markdown-aware chunks.

---

## Decision 2: Snippet Anchor / Deep-Link Strategy

**Decision**: Store `char_offset: int` (start of the user's selection within `Source.content`) as the anchor.

**Rationale**:

- The Document View renders `Source.content` (markdown string) in a scrollable panel.
- When the user highlights text, the browser selection gives a character offset within the rendered text.
- Storing this offset as an integer is the simplest reversible anchor: on "go to source", the frontend scrolls to the element containing that character offset.
- Heading-based anchors are unreliable (headings may repeat; non-PDF sources have no headings).
- Chunk-index anchors require the frontend to know the chunking algorithm — too much coupling.

**Alternatives considered**:

- Heading text anchor: fragile for non-structured sources — rejected.
- Chunk index: couples frontend to chunking algorithm — rejected.
- xpath / DOM: frontend-specific, not storable in DB portably — rejected.

---

## Decision 3: Semantic Search Results with Source Metadata

**Decision**: Add a new `query_sources_with_metadata` function in `documentlm_core`'s vector store that returns `list[ChunkResult]` (a TypedDict with `text` and `source_id`).

**Rationale**:

- The existing `query_sources` returns `list[str]` (text only). For the Snippet Bank search, we need `source_id` alongside each result so the user knows which document the passage came from.
- ChromaDB's `collection.query()` already returns `metadatas` — adding a new function avoids breaking existing callers.
- `ChunkResult` as a `TypedDict` satisfies the Strong Typing principle (no plain dicts).

**Alternatives considered**:

- Modify `query_sources` return type: breaks existing callers — rejected.
- Return raw ChromaDB result dicts: violates no-plain-dicts rule — rejected.

---

## Decision 4: Snippet Bank Scope

**Decision**: Snippets are scoped to `document_id`. Each document acts as a workspace; a user's snippets are per-document.

**Rationale**:

- The spec says "active Snippet Bank for the current workspace". In this app, a workspace is a document. Scoping by `document_id` + `user_id` is consistent with how all other entities (sources, comments) are scoped.
- Multi-user snippet sharing is explicitly out of scope.

---

## Decision 5: Bounded Generation — Snippet and Intent Optionality

**Decision**: Snippets are **optional** for generation. The intent string is **required** when the user invokes AI generation, but the user may always dismiss the bundling UI and type directly instead.

**Rationale**:

- User story 4 was updated (system-confirmed intentional) to "optionally choose" snippets — snippet selection is not required to trigger generation.
- Intent remains mandatory for the generation path: if you invoke the AI, you must tell it what to do. The escape hatch is not to provide intent but to dismiss the UI entirely and type manually.
- Practical effect: the generation endpoint rejects requests with an empty intent string (422). The UI disables the "Generate" button until intent is non-empty. The bundling UI has a visible "cancel / type myself" affordance.

**Note for implementers**: FR-016 relaxed (optional snippets), FR-017 preserved with clarification (intent required *if* generating). The `BoundedGenerateRequest` schema keeps `min_length=1` on `intent`.

---

## Decision 6: Bounded Generation — New Agent Function vs. Reusing Drafter

**Decision**: Add a new `invoke_bounded_drafter` function to `writer/services/agent_service.py`, reusing the existing `drafter_agent` and `run_agent_text` infrastructure but with a different message format.

**Rationale**:

- The existing `invoke_drafter` gathers chunks automatically via vector search and takes a `Comment` as input. Bounded generation takes explicit `snippet_texts` + `intent` — a fundamentally different call shape.
- Adding a new function avoids modifying the existing comment-based flow.
- The underlying `drafter_agent` and `run_agent_text` are unchanged.

**Message format for bounded drafter**:

```text
--- FULL DOCUMENT ---
[document.content]
--- END DOCUMENT ---

--- EVIDENCE SNIPPETS ---
[snippet 1 text] (Source: [source title])
[snippet 2 text] (Source: [source title])
--- END EVIDENCE SNIPPETS ---

--- INSERTION POINT ---
[cursor_context — the heading or surrounding text where the new content will be inserted]
--- END INSERTION POINT ---

Intent: [user intent string]

Write the text described by the intent. Use the evidence snippets as your factual basis. Use the full document to avoid repeating content that is already present and to maintain the document's focus and tone.
```

If the document is chapter-structured (headings at the h1/h2 level), the caller should summarise chapters other than the current one rather than passing the full content verbatim, to stay within context limits. The `cursor_context` field identifies which chapter the insertion is within.

---

## Decision 7: Bounded Generation Result — Integration with Editor Suggestion State

**Decision**: The `POST /api/documents/{doc_id}/bounded-generate` endpoint returns a `BoundedGenerationResponse` (Pydantic model with `suggested_text: str`). The TipTap editor in `editor.js` receives this via HTMX and inserts the text using the existing `insertSuggestion` mechanism.

**Rationale**:

- The existing editor already has suggestion insert/accept/reject UI (built in feature 006 and maintained in `editor.js`/`editor.bundle.js`).
- Returning raw text and letting the editor handle the "Suggested" state reuses this mechanism without new DB persistence for the generation bundle (which is ephemeral per spec).
- No new DB table is needed for the generation result — the Suggestion table is not used here because bounded generation is triggered from an empty block, not a text selection.

---

## Decision 8: Side Panel Architecture (Document View + Snippet Bank)

**Decision**: Implement the side panel as a server-side rendered HTMX panel with two tab states. The Document View tab renders source markdown as HTML (server-rendered via `markdown` library). The Snippet Bank tab is rendered as a list of HTMX partial snippets.

**Rationale**:

- Consistent with the project's "minimize JS" principle.
- Tab switching via HTMX `hx-get` on tab buttons — no JS required.
- Source markdown is rendered server-side (Jinja2 template + `markdown` Python library) and displayed in a scrollable `<div>`. Scrolling to `char_offset` requires one small JS function in `editor.js` (acceptable).
- Snippet Bank is a standard HTMX list with delete and note-edit actions.

---

## Known Constraints

- `pymupdf4llm` must be added to `src/writer/pyproject.toml`. Core package is not affected.
- The `Source.content` field changes format (plain text → markdown) for new PDF sources. Existing sources retain plain text. No migration required for the `content` column itself.
- Search with metadata needs a new function in `documentlm_core` — this requires a small change to the core package.
- `editor.js` will require changes for the bundling UI and intent input; user must run `npm run build:dev` after any editor.js change.
