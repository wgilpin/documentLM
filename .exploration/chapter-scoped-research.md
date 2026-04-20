# Chapter-scoped research: ongoing source + snippet organisation

## Problem

Research in documentLM is currently front-loaded: users pick sources at project init, and there's no built-in way to continue researching as the document grows. Three concrete pain points (reported from dogfooding):

1. **No post-init source discovery.** Once the project starts, there is no UI path to go find more sources. Research is implicitly "done" after ingestion.
2. **Source list grows unwieldy.** As sources accumulate, the flat sidebar list becomes hard to browse.
3. **Snippet list is worse.** The newly-shipped snippets feature produces finer-grained items that pile up faster and have even less structure than sources.

Chapters (from spec 016) already partition the document structurally. The working hypothesis is that chapters are the right axis for partitioning research too.

## Proposed change

Introduce chapter-scoped research in three staged phases, each independently shippable:

1. **Manual chapter tagging** (MVP floor). Sources and snippets can be tagged to one or more chapters. Untagged items are document-level. Tagging is manual at this stage — user chooses the chapter(s) when adding a source or saving a snippet. This is the minimum slice that ships the organising primitive.
2. **Semantic search** over sources and snippets. Chapter of the current editing context is the default filter, overridable. When results exist outside the default scope, surface a count ("12 in this chapter, 4 in others") with one-click broaden. Also enables "summarise this source" and "get me quotes for this topic" as downstream prompt-level features.
3. **Unified surface + discover.** A single search UI that returns both existing-corpus hits and a "discover more" action. Discover runs against multiple backends (deep research via 014, generic web search, paperstore search) and routes results through the existing Holding Pen before they enter the corpus. Discovered items can auto-tag to the chapter they were discovered from.

Ergonomic refinements layered on top: auto-tag-to-current-chapter when a snippet is created or a source is added inside a chapter context; cached source summaries that prefer a paper's abstract when one is extractable.

## Key decisions made during exploration

- **Many-to-many, not one-to-many**: a source or snippet can belong to ≥0 chapters. Zero tags = document-level.
- **Chapters-only, no free-form tags**: "topic" is user-facing language for a semantic search query, not a tagging dimension. A separate tag system is explicitly not in scope.
- **Chapter drift rules**: on chapter delete, tagged items move to document-level (losing research is worse than miscategorisation). Split/merge rules deferred — no such feature exists today.
- **Snippets → document is manual drag-as-quote**, not AI-assisted draft insertion. This preserves documentLM's anti-chat philosophy; snippets are research artifacts, not draft ingredients.
- **Discover routes to Holding Pen, not directly to corpus**. Trust boundary stays explicit (reuses existing PRD concept).
- **Search-first ordering**: if only one thing ships, manual tagging is the floor. But search is the higher-leverage follow-up because it makes a long list *findable*, not just filterable.
- **Cached source summaries** live at the source, not regenerated per view. For papers, prefer the abstract.

## Open questions

- **Snippet schema delta**: does snippets need a `chapter_id` column, or is the `snippet_chapters` join table sufficient? (Join table is likely enough — auto-tag can insert a row at creation time.)
- **Spillover UX copy and interaction**: exact wording and click target for "N matches in other chapters."
- **Discover-route selection UX**: is the route (deep research / web / paperstore) picked explicitly by the user per search, or is there a default? Does the user see results from all three merged, or one at a time?
- **Discover cost/latency management**: web search + LLM per chapter is expensive. Rate limits? Cached results? Not blocking for MVP phases but needed before phase 3 ships.
- **Auto-tag-on-create for sources**: when a user adds a source while inside a chapter, does it auto-tag to that chapter, or default to document-level with the chapter as a pre-filled option?

## Red-team findings

Three objections were raised and resolved:

- **"You're pricing three features as one."** Survived with mitigation: accepted a staged delivery. User's stated minimum is phase 1 alone (manual tagging), which is genuinely small. Risk of never finishing the later phases is acknowledged; each phase independently reduces pain.
- **"Test the cheapest hypothesis first — just a search box might solve it."** User rejected this experiment. The organisational primitive is wanted regardless. Accepted that this means building on a hypothesis rather than validated data.
- **"Chapter-scoping before search adds a filter to a list that's already too long to browse."** Accepted. Ordering revised: manual tagging ships as the organising primitive, but semantic search is the second phase, not third, because it converts the pain from "unbrowsable" to "findable." The earlier "LLM-over-RAG wins first" ordering was wrong.

The idea survived red-team. Strongest surviving concern: scope discipline. The user should treat phase 1 as potentially final and only commit to phases 2/3 based on actual usage of phase 1.

## Feasibility flags

- **Join tables** (`source_chapters`, `snippet_chapters`) are straightforward SQLAlchemy additions with migrations. Chapter-delete cascade requires explicit handling (move to document-level, i.e. delete the join rows, don't delete the source/snippet).
- **Semantic search over snippets** needs snippet embeddings. Spec 005 established embeddings for sources but not necessarily snippets — needs verification. If absent, embedding generation on snippet create is a small addition.
- **Discover** is the largest feasibility unknown. Spec 014 gives one route; the other two (generic web search, paperstore search) need API selection. Cost controls required.

## Out of scope

- **Free-form tags / topics as a separate taxonomy.** Chapters are the only structural axis.
- **Chapter split/merge handling.** No such feature exists; decide when built.
- **AI-assisted snippet-to-draft insertion.** Snippets go into the draft via manual drag-as-quote only.
- **Cross-document source sharing.** Orthogonal to this work.
- **Promoting snippets to citations.** Possibly a natural follow-on but not part of this initiative.

## Ready for /specify?

**Phase 1 (manual chapter tagging) — yes.** Data model, chapter-drift rules, and UX shape are all decided. Open questions for this phase are all copy- or interaction-level, answerable during spec writing.

**Phase 2 (semantic search) — conditional.** Ready once phase 1 ships and the snippet-embedding question is answered. Spillover UX needs to be decided at spec time.

**Phase 3 (unified surface + discover) — no.** Needs concrete route-selection UX, cost controls, and verification of what spec 014 already provides before this is spec-ready. Recommend re-exploring or sketching separately before `/specify`.
