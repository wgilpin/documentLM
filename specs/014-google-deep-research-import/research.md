# Research: Import Google Deep Research

**Feature**: 014-google-deep-research-import  
**Date**: 2026-04-12

---

## 1. Markdown Reference Format (from sample file)

**Decision**: Extract URLs from the `#### Works cited` section using a standard Markdown link regex: `\[([^\]]+)\]\((https?://[^)]+)\)`.

**Rationale**: The sample file (`docs/AI Product Management in Rapid Development.md`) confirms the format. References appear as numbered list items, each containing one Markdown hyperlink. The URL is in the `(...)` portion; the display text in `[...]` can serve as the source title. The section heading is `#### Works cited`.

**Observed patterns in sample:**
- Standard: `1. Title, accessed on date, [display text](https://...)` — extract href as URL, display text as title
- Bare anchor: `7. accessed on date, [https://url](https://url#anchor)` — both display and href are the same URL; use the domain as title fallback
- 39 references in one doc — confirms 20+ scale assumption is conservative

**Alternatives considered**: Searching the entire document for any `[text](url)` — rejected because the body text also contains inline links that are not references. Scoping to the Works Cited section is more reliable.

**Scope decision**: Extract URLs from the entire document (not just Works Cited section). This is simpler and handles documents that embed references inline rather than in a bibliography. Non-http links (e.g., anchors, mailto) are filtered out by the `https?://` prefix requirement.

---

## 2. Existing Source Ingestion Pipeline

**Decision**: Reuse `source_service.add_source()` for each reference URL and `source_service.add_source()` with `SourceType.note` for the document body. Trigger `run_indexing()` as a background task for each.

**Rationale**: `add_source()` already handles URL deduplication within the same `document_id` + `user_id` (lines 45–56 of `source_service.py`) — this covers both FR-006 (within-import dedup) and FR-006a (workspace dedup) with zero new code.

**Existing flow**:
1. `add_source()` → inserts `Source` row, returns `SourceResponse`
2. `run_indexing(source_id, db, user_id)` → background task → chunks + indexes into ChromaDB, updates `indexing_status`

**No new DB schema or model changes required.**

---

## 3. Source Type for Document Body

**Decision**: Use `SourceType.note` for the research document body content.

**Rationale**: There is no `markdown` source type in the existing enum (`url`, `pdf`, `note`). The document body is unstructured text, which maps cleanly to `note`. Adding a new enum value would require a DB migration and is unnecessary for a prototype.

**Alternatives considered**: Adding `SourceType.markdown` — rejected (YAGNI; migrations add friction; `note` is functionally identical for ingestion).

---

## 4. File Upload Mechanism

**Decision**: New FastAPI endpoint `POST /api/documents/{doc_id}/sources/import-deep-research` accepting `UploadFile` (`.md` file). Returns HTMX-compatible HTML fragments for each created source.

**Rationale**: The existing `add_source` endpoint handles individual sources; batch import needs a dedicated endpoint. HTMX `hx-swap="beforeend"` on `#source-list` can handle multiple fragments returned in a single response.

**File size**: No explicit limit set — the prototype relies on FastAPI's default request size limit. A 100-reference doc is well under any practical limit.

---

## 5. UI Pattern — Instructions Modal + File Picker

**Decision**: `<dialog>` element triggered by a button in the sources panel. Modal contains: step-by-step instructions, a file `<input type="file" accept=".md">`, and a submit button. Submit posts via HTMX to the import endpoint.

**Rationale**: The app already uses `<dialog>` for modals (`source-note-modal`, `delete-confirm-dialog`, `settings-dialog`, `command-modal`). This pattern keeps JS minimal — only the `showModal()` call needed, which can be an `onclick` attribute on the trigger button (consistent with existing patterns in the template).

**Error display**: Inline error in the modal (matching clarification Q1 answer). If the server returns an error status, HTMX retargets an error `<div>` inside the modal.

---

## 6. Progress Feedback

**Decision**: Each source is inserted and returned as an HTML fragment immediately. The existing `indexing_status` field (`pending` → `processing` → `completed`/`failed`) on the `Source` model tracks background ingestion. No new polling mechanism is needed for this prototype.

**Rationale**: The spec requires the user to see ingestion progress (FR-008) but SC-005 only requires no UI degradation — polling per source would add complexity. For the prototype, sources appearing immediately in the list with `pending` status is acceptable. A future feature could add live status polling.

---

## 7. New Service: `deep_research_service.py`

**Decision**: Create `src/writer/services/deep_research_service.py` with two pure functions:
- `parse_markdown_document(content: str) -> DeepResearchParseResult` — returns document title + body text + list of `ExtractedReference` (title + url)
- `extract_urls(markdown: str) -> list[ExtractedReference]` — finds all `[text](https://...)` links, deduplicates by URL

**Rationale**: Keeps parsing logic isolated and unit-testable (TDD). The API endpoint stays thin.

**No ADK agents introduced** — parsing is deterministic, not AI-driven.
