# Feature Specification: Semantic Search over Sources and Snippets (Phase 2)

**Feature Branch**: `018-semantic-search`
**Created**: 2026-04-20
**Status**: Draft
**Input**: User description: "Add semantic search over sources and snippets. Phase 2 of the chapter-scoped research initiative captured in [.exploration/chapter-scoped-research.md](../../.exploration/chapter-scoped-research.md). Assumes Phase 1 (spec 017, `source_chapters` + `snippet_chapters` join tables) is in place. Discover, cached source summaries, and LLM-over-RAG actions are out of scope."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Search the current document for matching sources and snippets (Priority: P1)

A writer has accumulated many sources and snippets in a long-running document and can no longer find a specific idea by scrolling the sidebar. They type a natural-language query ("diminishing returns in team size") into a single search input and get two ranked lists back: matching sources (with the best matching excerpt previewed) and matching snippets (with the snippet text and its origin source). Clicking a result jumps to that source or snippet in the existing sidebar panes — no new detail view is introduced.

**Why this priority**: This is the core value of the feature. Without it, the flat lists from Phase 1 are filterable but not findable. Turning the sidebar into a searchable research corpus is the whole point of Phase 2, and it is independently shippable the moment the two ranked lists render and click-through works — scoping behaviour (Story 2) can be deferred without making the feature useless.

**Independent Test**: Seed a document with several sources and snippets whose content covers distinct topics. Issue a query that semantically matches a subset of the corpus. Verify the writer sees two clearly separated result groups ranked by similarity, that each source hit shows the best-matching excerpt and each snippet hit shows its text + source attribution, and that clicking a result reveals the corresponding item in the existing sources or snippets pane.

**Acceptance Scenarios**:

1. **Given** a document with indexed sources and snippets covering several topics, **When** the writer enters a natural-language query in the search input, **Then** the writer sees two separately ranked lists — Sources and Snippets — each ordered by similarity score, with items below a minimum similarity threshold excluded.
2. **Given** a search result list is displayed, **When** the writer clicks a source hit, **Then** that source is revealed in the sources pane (selected, expanded, or scrolled into view as appropriate).
3. **Given** a search result list is displayed, **When** the writer clicks a snippet hit, **Then** that snippet is revealed in the snippets pane in the same way.
4. **Given** a source appears in the result list, **When** the result is rendered, **Then** it shows the source title together with the best-matching excerpt from that source (not an arbitrary chunk).
5. **Given** a snippet appears in the result list, **When** the result is rendered, **Then** it shows the snippet text, the title of the source it was taken from, and the chapter it is tagged to if any (otherwise "document-level").
6. **Given** the writer issues a query with no matching items above the similarity threshold, **When** the search returns, **Then** both result lists display a clear empty state naming the query and the active scope.

---

### User Story 2 - Scope the search to the chapter currently being edited (Priority: P2)

When the writer is editing inside a specific chapter, the search should default to that chapter's scope: only items tagged to that chapter, plus document-level items (items with no chapter tags), are considered. The writer can override the scope to "entire document" from the search UI, and when a narrower scope is active the UI surfaces a count of additional matches that exist outside the scope ("12 in this chapter, 4 in others") with a one-click broaden.

**Why this priority**: This is the payoff of the chapter-scoping primitive from Phase 1. Without it, the search still works but returns the whole document's hits every time, which is noisier than it needs to be when the writer has a focused editing context. It is deliberately a follow-on story so that Story 1 can ship alone if needed.

**Independent Test**: With Phase 1 tagging populated, place the caret inside a chapter that has tagged sources and snippets, plus some untagged (document-level) items. Issue a query whose matches exist in the focused chapter, in other chapters, and at document level. Verify the default scope is the focused chapter, document-level items are included, other-chapter hits are excluded, and a spillover count is visible. Toggle to "entire document" and verify all hits return without re-typing the query.

**Acceptance Scenarios**:

1. **Given** the writer is editing inside a chapter, **When** they open the search UI, **Then** the scope selector defaults to that chapter (label includes the chapter title).
2. **Given** the scope is set to the current chapter, **When** the writer runs a query, **Then** only items tagged to that chapter or tagged to no chapter (document-level) appear in the result lists.
3. **Given** the current-chapter scope is active and additional matches exist outside it, **When** the results render, **Then** a spillover indicator shows the counts (e.g. "12 in this chapter, 4 in other chapters") with a visible broaden action.
4. **Given** a spillover indicator is shown, **When** the writer activates the broaden action, **Then** the scope changes to "entire document" and all matches (including the previously excluded ones) appear — without the writer re-typing the query or re-running the search manually.
5. **Given** the writer is at document level (caret not inside any chapter), **When** they open the search UI, **Then** the scope selector defaults to "entire document".
6. **Given** the writer overrides the scope to "entire document", **When** the writer later returns the caret to a chapter, **Then** the scope selector resets to that chapter's default on the next search interaction (override is per-search, not sticky across chapter context changes).
7. **Given** the document has zero chapters, **When** the writer opens the search UI, **Then** the scope selector is hidden (or rendered as a no-op) and all searches run document-wide.

---

### User Story 3 - Snippet embeddings are generated so snippets are searchable (Priority: P1)

For snippets to appear in semantic search results at all, each snippet must be represented in the same vector space as source chunks. Snippet embeddings are generated automatically when a snippet is created, and a one-time backfill embeds existing snippets so pre-existing corpora are searchable on day one.

**Why this priority**: This is a prerequisite for Story 1 as soon as snippets are in scope. It is called out as a separate story because it is independently testable (embedding coverage can be asserted without a search UI) and because the backfill is a distinct deployment concern. Without it, Story 1 ships with an empty snippets result list.

**Independent Test**: Deploy the feature onto a populated database, run the backfill, and verify that every snippet has an embedding recorded. Then create a new snippet and verify its embedding is generated without user action.

**Acceptance Scenarios**:

1. **Given** a snippet is created, **When** the save completes, **Then** an embedding representing the snippet's text is available in the vector store, generated using the same embedding model as source chunks.
2. **Given** the feature is deployed onto a database that already contains snippets, **When** the one-time backfill has been run, **Then** 100% of pre-existing snippets have embeddings.
3. **Given** a snippet embedding fails to generate (for example because the underlying model is temporarily unavailable), **When** the failure occurs, **Then** the snippet itself is still saved successfully and the embedding is retried in the background; the snippet is simply not searchable until the embedding is produced.
4. **Given** a snippet is deleted, **When** the deletion completes, **Then** its embedding is removed from the vector store (no orphan snippet hits).

---

### Edge Cases

- **Empty query**: The search UI must not issue a search for a blank or whitespace-only query. The result area stays cleared.
- **Very short query**: Single-word queries are allowed. No minimum length is enforced beyond "non-empty".
- **Document has only sources, no snippets (or vice versa)**: The missing type's result list renders as an explicit empty state ("No snippets match") rather than being hidden entirely, so the writer is not confused about whether the type was searched.
- **Document has no chapters**: Scope selector is hidden; all searches are document-wide; spillover indicator never appears.
- **No items above similarity threshold**: Both result lists show empty states that name the query. No "did you mean…" suggestions are offered.
- **Query typed while caret is between two chapters (e.g. in a document preamble)**: The default scope is "entire document" (no owning chapter).
- **Chapter the scope points to is deleted mid-session**: The next search falls back to "entire document" and the scope selector updates accordingly.
- **Source is in "pending" or "failed" indexing state**: It does not appear in source search results (only "completed" sources are searched), matching spec 005 behaviour.
- **Snippet whose embedding has not yet been generated (e.g. brand new, or retry pending)**: It does not appear in snippet search results. Snippet detail views are unaffected.
- **Very long query**: Queries beyond a reasonable length (assumed 500 characters; exact ceiling is an implementation detail) are truncated with a non-blocking notice; search still runs.

## Requirements *(mandatory)*

### Functional Requirements

#### Search input and results

- **FR-001**: The system MUST provide a search input, reachable from the current document view, that accepts a free-form natural-language query.
- **FR-002**: The system MUST NOT treat chapter titles, source titles, or other structural identifiers as special-case queries — all input is handled uniformly as a semantic query.
- **FR-003**: The system MUST return two separate, independently ranked result groups per query: one for matching sources and one for matching snippets.
- **FR-004**: The system MUST rank results within each group by semantic similarity, highest first.
- **FR-005**: The system MUST exclude results whose similarity falls below a configurable minimum threshold (noise floor).
- **FR-006**: The system MUST NOT merge the two result groups into a single combined list.
- **FR-007**: Each source result MUST display the source title and the best-matching excerpt from that source as a preview.
- **FR-008**: Each snippet result MUST display the snippet's text, the title of its originating source, and the chapter it is tagged to (or a "document-level" indicator when the snippet has no chapter associations).
- **FR-009**: Clicking a result MUST reveal that source or snippet within the existing sidebar pane (sources pane for source results, snippets pane for snippet results); the system MUST NOT introduce a new detail view solely for search results.
- **FR-010**: When a query returns zero items in a group (because there are no items of that type in the corpus, or none pass the threshold), that group MUST show an explicit empty state rather than being omitted.
- **FR-011**: The search operation MUST be read-only and MUST NOT modify any source, snippet, or chapter state.

#### Chapter scoping

- **FR-012**: When the writer's editing context is inside a specific chapter at the moment search is initiated, the default scope MUST be "current chapter" — meaning items tagged to that chapter PLUS items with no chapter associations (document-level).
- **FR-013**: When the writer's editing context is at document level (no owning chapter), the default scope MUST be "entire document".
- **FR-014**: The search UI MUST expose a scope control that allows the writer to switch between the current-chapter scope (when applicable) and "entire document".
- **FR-015**: When the scope is "current chapter" and additional matches exist outside that scope, the UI MUST display a spillover indicator showing the count of in-scope matches and the count of out-of-scope matches (e.g. "12 in this chapter, 4 in other chapters").
- **FR-016**: The spillover indicator MUST offer a one-click action to broaden the scope to "entire document"; this action MUST apply to the already-returned result set (change of filter) and MUST NOT require the writer to re-type or re-submit the query.
- **FR-017**: When the document contains zero chapters, the scope control MUST be hidden (or otherwise rendered as a no-op) and searches MUST be document-wide.
- **FR-018**: Scope overrides (switching to "entire document" manually) MUST persist only for the current search interaction; when the writer's editing context next changes chapter, the default scope MUST reset to the new chapter on the next search.

#### Embeddings for snippets

- **FR-019**: The system MUST generate an embedding for every snippet at creation time using the same embedding model that spec 005 uses for source chunks, so source and snippet similarity scores are comparable within the same vector space.
- **FR-020**: The system MUST remove a snippet's embedding from the vector store when the snippet is deleted.
- **FR-021**: A one-time backfill MUST be provided that generates embeddings for every snippet that existed before the feature was deployed.
- **FR-022**: If embedding generation fails for a snippet, the snippet MUST still be saved; the system MUST retry embedding in the background and MUST log the failure. A snippet without an embedding MUST NOT appear in snippet search results until its embedding exists.

#### Performance and behaviour

- **FR-023**: A search over a corpus of a few hundred sources and snippets within a single document MUST return results in under one second under normal operating conditions.
- **FR-024**: The search MUST operate entirely within the current document's corpus; cross-document search is not supported.
- **FR-025**: A source whose indexing status is not "completed" MUST NOT appear in source search results (consistent with spec 005).

### Key Entities *(include if feature involves data)*

- **Search Query**: A free-form natural-language string provided by the writer. Has no persistent identity; not stored beyond the lifetime of the search interaction.
- **Scope**: The chapter-based filter applied to a search. One of "current chapter" (only meaningful when the writer is editing inside a chapter) or "entire document". Carries a reference to the owning chapter when the scope is chapter-bound.
- **Source Result**: A ranked match against an indexed source. Carries the source identifier, the source title, the best-matching excerpt preview, and the similarity score used for ranking.
- **Snippet Result**: A ranked match against a snippet. Carries the snippet identifier, the snippet text, the originating source's identifier and title, the snippet's chapter association (if any), and the similarity score.
- **Spillover Counts**: Per-group counts of in-scope versus out-of-scope matches, shown only when the scope is "current chapter" and the document has at least one out-of-scope match.
- **Snippet Embedding**: A vector representation of a snippet's text, stored in the same vector space as source chunks. Linked one-to-one with a snippet and kept in sync with the snippet's text (created on save, updated on edit, removed on delete).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A writer with a corpus of a few hundred sources plus snippets in a single document receives ranked results within one second of submitting a query, at the 95th percentile.
- **SC-002**: For a seeded query with known-relevant items, at least one of the top 3 source results and at least one of the top 3 snippet results (where applicable) match the writer's intent in pilot usage.
- **SC-003**: When the writer is editing inside a chapter, the initial search result view reflects the "current chapter" scope on the first visible search — verified by inspection of the scope selector's default state.
- **SC-004**: When out-of-scope matches exist, the spillover indicator is present and accurate (shown counts equal the actual in-scope and out-of-scope match counts after the similarity threshold is applied).
- **SC-005**: Activating the broaden action expands the visible result set without re-issuing the underlying query (same query, different filter) — verified by observing a single query request per typed query, regardless of scope changes.
- **SC-006**: After deployment plus backfill, 100% of pre-existing snippets are searchable (have embeddings) within the corpus they belong to.
- **SC-007**: No source, snippet, or chapter association is modified as a consequence of running a search — verified by audit of persisted state before and after a batch of searches.
- **SC-008**: A document with zero chapters behaves as document-wide-only: the scope selector is not shown and no spillover indicator ever appears.

## Assumptions

- **Phase 1 is deployed**: Chapter associations for sources and snippets (from spec 017) exist and are populated; this spec treats their presence as a given.
- **Source embeddings reused as-is**: Source chunk embeddings, chunking strategy, and vector store configuration from spec 005 are reused without change. Snippet embeddings adopt the same embedding model so the two kinds of results are directly comparable in the same vector space.
- **Editing context is detectable**: The system can determine which chapter (if any) contains the writer's caret at the moment a search is initiated, reusing the editing-context signal from specs 016 and 017.
- **Threshold tuning is an implementation concern**: The minimum similarity threshold and the per-group result cap (top-N per group) are tunable values chosen during implementation. They are not part of this spec's contract beyond the requirement that they exist.
- **Sub-second latency is for the target corpus scale**: "Corpus of a few hundred items" is the scale being designed for. Larger corpora may need separate attention but are not promised here.
- **Scope override is per-search, not a sticky preference**: The writer's manual broaden to "entire document" applies to the current search interaction only. The next time the chapter context changes, the default scope rebinds. Persisting a cross-session preference is not required.
- **Search is synchronous from the writer's perspective**: Results appear together after the query completes (no progressive streaming). Implementation may stream internally but the UX contract is a single results render.
- **Snippet embeddings do not exist today**: Confirmed by inspection of the current codebase — only source chunks are embedded (see spec 005). This spec therefore adds snippet embedding as part of its scope. If this assumption turns out to be wrong during planning, FR-019–FR-022 simplify accordingly.
- **Snippet text is not editable today**: Snippets can be created and deleted, but their `text` field is not mutable through any UI or API path. Keeping the embedding in sync with edited text is therefore not required by this spec. If snippet text editing is added later, that spec must add a re-embed hook (simple: call `index_snippet` again at the deterministic id).
- **Navigation target for clicks**: A source result's click target reveals the source in the sources pane; a snippet result's click target reveals the snippet in the snippets pane. Any deeper interaction (opening a source's detail view, jumping to a specific chunk within a source) is out of scope.

## Out of Scope

Deferred to later phases of the chapter-scoped research initiative ([.exploration/chapter-scoped-research.md](../../.exploration/chapter-scoped-research.md)) or to separate specs:

- **Discover-new-sources**: web search, paperstore search, deep research routing, and Holding Pen integration for newly discovered items (Phase 3).
- **LLM-over-RAG actions**: "summarise this source", "get me quotes for this topic", or any other prompt-level feature layered on search results.
- **Cached source summaries** (including abstract extraction for papers).
- **Automatic chapter tagging** of sources or snippets — tagging remains manual per Phase 1.
- **Query history, personalised ranking, or saved searches**.
- **Cross-document search** — search stays scoped to the current document.
- **Merged sources+snippets result list** — the two groups are always separate (explicit product decision).
- **A dedicated detail view for search results** — click-through reuses the existing sidebar panes.
- **Re-chunking or re-embedding existing sources** as part of this spec; source indexing behaviour from spec 005 is unchanged.
- **Re-embedding snippets when their text changes** — snippet text is not editable today; a re-embed hook would only be needed once snippet text editing is introduced.
