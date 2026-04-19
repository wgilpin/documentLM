# Phase 0 Research: Chapter-Scoped Sources and Snippets

This phase resolves naming, schema, and UI mechanics decisions before implementation. The Technical Context in plan.md has no `NEEDS CLARIFICATION` markers — every choice below is grounded in either the existing spec-016 conventions or the documentLM Constitution.

## 1. Naming convention for join tables

**Decision**: New table is `chapter_sources` (ORM class `ChapterSource`). Existing table `chapter_snippets` (ORM class `ChapterSnippet`) is reused as-is.

**Rationale**: Spec-016 already shipped `chapter_snippets` (chapter-first ordering). The user-facing spec uses the lexically inverted form (`source_chapters`, `snippet_chapters`) as suggestive shorthand, but consistency across the codebase wins. Renaming the existing table would be a destructive migration with no functional benefit.

**Alternatives considered**:
- *Match user spec wording (`source_chapters`, `snippet_chapters`)*: rejected — would force a rename of `chapter_snippets`, breaking spec-016 service code and migration history for cosmetic reasons.
- *Use mixed naming (`chapter_snippets` + `source_chapters`)*: rejected — inconsistent within the same feature.

## 2. Reuse of existing `chapter_snippets` machinery

**Decision**: Keep the spec-016 model `ChapterSnippet` and the existing services (`assign_snippet_to_chapter`, `unassign_snippet_from_chapter`, `list_snippets_by_chapter`) intact. Build the new sources side as a parallel mirror, then add three new helpers used by both:

- `replace_<item>_chapter_associations(item_id, chapter_ids)` — used by retroactive edit.
- `list_<items>_with_scope(document_id, user_id, scope)` — supersedes the simple `list_<items>` for filter use.
- Extension of create flows to accept an optional `chapter_ids` list for atomic create-and-tag.

**Rationale**: Spec-016 covers the snippet-tagging primitive but does not provide (a) bulk replace for retroactive edit, (b) "document-level only" filter mode, or (c) tag-on-create. These are the three additions that ship the full UX. The existing endpoints stay backward-compatible.

**Alternatives considered**:
- *Inline N inserts/deletes from the UI*: rejected — multiple round-trips per save plus race conditions on concurrent edits. A single replace is atomic and trivially testable.

## 3. Filter scope encoding (URL parameter shape)

**Decision**: Use a single query parameter `scope` with values `all` (default), `doc-level`, or `chapter:<uuid>`. The list endpoints (`GET /api/documents/{doc_id}/sources`, `GET /api/documents/{doc_id}/snippets`) accept this and return the filtered set.

**Rationale**:
- One parameter is simpler than two (e.g. `chapter_id=… + mode=…`) and easier to validate as a discriminated string.
- The current snippet endpoint already accepts `chapter_id` as an optional UUID parameter — it'll be deprecated in favour of `scope=chapter:<uuid>` but the spec-016 callers are limited (the `snippet_bank.html` partial uses no chapter filter today), so the breakage is contained.
- Putting the chapter UUID inside the scope value keeps "no chapter" as a first-class state rather than an awkward null.

**Alternatives considered**:
- *Two params (`mode` + `chapter_id`)*: rejected — invalid combinations are possible (e.g. `mode=all` + a `chapter_id`), requires extra validation.
- *Path segments (e.g. `/sources/by-chapter/<uuid>`)*: rejected — multiplies the endpoint count, breaks the single-handler simplicity.

## 4. Chapter picker UI mechanics

**Decision**: A reusable Jinja partial `partials/chapter_picker.html` rendering a `<details>` element containing a checkbox per chapter. The form field name is `chapter_ids` (multiple values per name — standard HTML form encoding). For the retroactive editor, the same partial is wrapped in a popover that POSTs to a new `PUT /api/documents/{doc_id}/sources/{source_id}/chapters` endpoint accepting a JSON array of chapter UUIDs.

**Rationale**:
- `<details>` is a built-in disclosure widget — no JS, matches the constitution's minimise-JS rule.
- HTMX form encoding sends `chapter_ids=A&chapter_ids=B` for multi-checkbox fields, which FastAPI parses cleanly into `list[uuid.UUID]`.
- A single shared partial avoids drift between the add-source dialog, snippet-save flow, and retroactive editors.

**Alternatives considered**:
- *Custom JS multi-select with chips*: rejected — violates the minimise-JS rule and adds complexity for no functional gain.
- *Modal dialogs for editing*: rejected — heavier than needed for a checkbox set; popover-style `<details>` keeps the user in context.

## 5. Auto-default filter on chapter context change (FR-019, FR-020)

**Decision**: The auto-default lives in the existing `active_chapter_id` template variable already passed to `document.html`. When the page renders (or a chapter card swaps to the editor view), the source-list and snippet-bank `hx-get` request URL includes `scope=chapter:<active_id>` as the initial value. Manual override is a session-only state held in the `<select>`'s value (no persistence required per spec assumptions). When the user navigates to a different chapter, the snippet-bank/source-list partial re-renders with the new default, which clears any prior manual override.

**Rationale**:
- `active_chapter_id` already exists from spec-016 (used in `document.html` line 283), so no new server-side plumbing is required to detect chapter context.
- "Manual override expires when context changes" is the simplest possible state machine and matches FR-020 verbatim.
- No persistence avoids a new `user_settings`-style row per pane.

**Alternatives considered**:
- *Persist filter state per user/document*: rejected — adds a new table for a Phase 1 feature that explicitly assumes session-scoped state.
- *Client-side localStorage*: rejected — violates the minimise-JS rule and creates a new untestable surface.

## 6. Behaviour on chapter deletion (FR-005, FR-021)

**Decision**: Rely on `ON DELETE CASCADE` on the `chapter_id` FK in both `chapter_sources` and `chapter_snippets`. Items become document-level automatically when their last association is removed. The UI handles the "active filter on now-deleted chapter" case by detecting (server-side) that the requested `chapter:<uuid>` no longer exists and silently falling back to `scope=all`.

**Rationale**:
- Cascade is the most reliable mechanism for FR-005 — no service-layer cleanup logic to maintain.
- The fallback for an orphaned filter is one extra `SELECT EXISTS` per filtered request; cheap.

**Alternatives considered**:
- *Service-layer cascade*: rejected — would require a hook in `delete_chapter` that's easy to forget; FK cascade is enforced by the database.
- *Hard error on stale filter UUID*: rejected — would be a confusing UX after a chapter delete.

## 7. Retroactive editing surface

**Decision**: A "tags" affordance on each source row and snippet card opens a popover containing the same `chapter_picker.html` partial. On change, the popover submits `PUT /api/documents/{doc_id}/sources/{source_id}/chapters` (or `…/snippets/{snippet_id}/chapters`) with the full new list of chapter IDs. The endpoint replaces the entire association set in one transaction.

**Rationale**:
- Replace-set semantics is simpler to reason about than diff-based add/remove from the client.
- One round-trip per edit. The user's individual checkbox toggles batch into a single submit (using `<form>` + an "Apply" button rather than `hx-trigger="change"` per box).

**Alternatives considered**:
- *Auto-apply per-checkbox change*: rejected — N round-trips, racy on slow networks, harder to undo if the user changes their mind mid-edit.
- *Inline-only editing (no popover)*: rejected — would make the source/snippet rows visually noisy.

## 8. Test strategy (Constitution II compliance)

**Decision**: TDD covers four new/extended service-layer functions:

- `source_service.assign_source_to_chapter` (new)
- `source_service.unassign_source_from_chapter` (new)
- `source_service.list_sources_by_scope` (new — handles `all` / `doc-level` / `chapter:<uuid>`)
- `source_service.replace_source_chapter_associations` (new)
- `snippet_service.list_snippets_by_scope` (new — extends existing `list_snippets_by_chapter` with `doc-level` mode)
- `snippet_service.replace_snippet_chapter_associations` (new)
- `snippet_service.create_snippet` (extended to accept `chapter_ids`)

No tests for: API endpoints (per Constitution II.b), Jinja templates (per II.b), Alembic migration (out of TDD scope). The migration is exercised end-to-end during the quickstart run.

**Rationale**: Aligns with Constitution II — service-layer logic is the correctness gate; endpoints and UI are validated via the quickstart manual run.

## 9. Migration safety on populated databases (FR-025)

**Decision**: The Alembic migration creates `chapter_sources` only — no data migration. `chapter_snippets` already exists from spec-016. Pre-existing sources and snippets remain untagged (no rows in either join table) and are therefore document-level by default, satisfying FR-024 with no backfill.

**Rationale**: Pure additive schema change; safe to run on any populated DB. No downtime, no backfill script.

## Open Questions Carried into Phase 1

None. All Phase 1 design decisions are resolved.

## Open Questions Deferred to Later Phases

The following from the broader exploration ([.exploration/chapter-scoped-research.md](../../.exploration/chapter-scoped-research.md)) are explicitly out of scope for Phase 1 and remain unresolved:

- Snippet embeddings for semantic search (Phase 2).
- Spillover UX copy ("N matches in other chapters") (Phase 2).
- Discover-route selection UI (Phase 3).
- Discover cost/latency controls (Phase 3).
- Auto-tag-on-create policy (Phase 2 or later — Phase 1 explicitly does not auto-tag).
