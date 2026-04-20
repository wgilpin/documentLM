# Feature Specification: Chapter-Scoped Sources and Snippets (Phase 1: Manual Tagging)

**Feature Branch**: `017-chapter-scoped-research`
**Created**: 2026-04-19
**Status**: Draft
**Input**: User description: "Add chapter-scoped organisation for sources and snippets. Phase 1 of the larger initiative captured in [.exploration/chapter-scoped-research.md](../../.exploration/chapter-scoped-research.md). Scope here is manual tagging only; semantic search, auto-tagging, discovery, and cached summaries are explicitly out of scope for this spec."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Organise sources by chapter (Priority: P1)

A writer has accumulated dozens of sources across a long-running document. As the document grows into chapters, the flat sources sidebar becomes hard to browse. The writer wants to tag each source to one or more chapters it belongs to (or leave it document-level), and filter the sources pane to show only sources relevant to the chapter they are currently working on.

**Why this priority**: Sources are the primary research artifact and the most numerous item in the sidebar. Without an organising axis they become unbrowsable as the project matures. Tagging plus filtering together turn a long flat list into a navigable structure — neither half is useful alone, so they ship together as the P1 slice.

**Independent Test**: Create a document with at least three chapters and at least six sources. Verify the writer can (a) tag sources to chapters when adding them, (b) edit a source's tags afterwards, (c) filter the sources pane to "all", "document-level only", or a specific chapter, and (d) see correct results for each filter setting. Delivers the full sources organisation slice end-to-end.

**Acceptance Scenarios**:

1. **Given** a document with three chapters and the add-source dialog open, **When** the writer selects two of the three chapters and submits, **Then** the new source appears in the sources pane and is associated with exactly those two chapters.
2. **Given** a document with three chapters and the add-source dialog open, **When** the writer submits without selecting any chapters, **Then** the new source is created as document-level (no chapter associations).
3. **Given** an existing source already in the sources pane, **When** the writer opens the source's chapter-tag editor and changes its chapter associations, **Then** the source's tags are updated and the sources pane filter view reflects the change immediately.
4. **Given** the sources pane filter is set to a specific chapter, **When** that chapter has two tagged sources and the document has five other sources, **Then** only those two sources are visible in the pane.
5. **Given** the sources pane filter is set to "document-level only", **When** the document has both tagged and untagged sources, **Then** only the untagged sources are visible.
6. **Given** the sources pane filter is set to "all", **When** the document has any sources, **Then** every source is visible regardless of its tags.

---

### User Story 2 - Organise snippets by chapter (Priority: P2)

The same writer is also collecting snippets (highlighted excerpts from sources). Snippets accumulate even faster than sources and the snippets pane becomes unwieldy first. The writer wants the same chapter-tag organising primitive applied to snippets: tag on save, edit later, filter the pane.

**Why this priority**: Snippets share the organising problem with sources but can be delivered as a second independent slice. The data model and UX patterns are parallel to P1, so this is genuinely a separate user-visible feature with the same shape, scoped to a different artifact type. Sources go first because they are the more established primitive and the bigger pain point per dogfooding feedback; snippets follow.

**Independent Test**: Create a document with chapters and at least six snippets. Verify the writer can tag snippets on save, edit a snippet's tags afterwards, and filter the snippets pane to "all", "document-level only", or a specific chapter, with correct results for each setting.

**Acceptance Scenarios**:

1. **Given** the snippet-save flow is open after highlighting text, **When** the writer selects one or more chapters and saves, **Then** the snippet is created and associated with exactly those chapters.
2. **Given** the snippet-save flow is open, **When** the writer saves without selecting any chapters, **Then** the snippet is created as document-level.
3. **Given** an existing snippet in the snippets pane, **When** the writer edits the snippet's chapter tags, **Then** the snippet's tags are updated and the snippets pane filter view reflects the change immediately.
4. **Given** the snippets pane filter is set to a specific chapter, **When** snippets are tagged across several chapters, **Then** only snippets tagged to the selected chapter are visible.

---

### User Story 3 - Filter defaults to the chapter being edited (Priority: P3)

When the writer is actively editing inside a specific chapter, the sources and snippets panes should default their filter to that chapter so the most-relevant material is immediately visible. The default must be overridable — switching the filter to "all" or to another chapter should hold until the writer changes it again or moves to a different chapter context.

**Why this priority**: This is a quality-of-life refinement on top of P1 and P2. Without it the feature still works, but the writer pays a small cost (changing the filter every time they switch chapters). With it, the right material is in front of the writer by default. Importantly, this default must NOT auto-tag any new sources or snippets to the current chapter — it only affects the filter view.

**Independent Test**: With chapter tags already in place from P1/P2, navigate the editor caret into a specific chapter and verify the sources and snippets panes auto-filter to that chapter. Switch chapters and verify the filter follows. Manually change the filter to "all" and verify it sticks until the chapter context changes again.

**Acceptance Scenarios**:

1. **Given** the writer's caret moves into a chapter that has tagged sources and snippets, **When** no manual filter override is active, **Then** both the sources pane and snippets pane filter to that chapter automatically.
2. **Given** the filter has auto-defaulted to a chapter, **When** the writer manually changes it to "all", **Then** the filter stays on "all" while the writer remains in that chapter.
3. **Given** the writer is in a chapter with no tagged sources or snippets, **When** the panes auto-filter to that chapter, **Then** each pane shows an empty state with a clear way to broaden the filter to "all" or "document-level only".
4. **Given** a new source or snippet is added while the writer is editing inside a chapter, **When** the writer does not explicitly select that chapter in the picker, **Then** the new item is created as document-level (no auto-tagging).

---

### Edge Cases

- **Document has no chapters**: The chapter picker is hidden (or rendered as a no-op) in the add-source and snippet-save flows. The sources/snippets pane filter control is hidden or disabled. All sources and snippets remain document-level.
- **Document had chapters, then all chapters are deleted**: All previously tagged items become document-level (their associations are removed). The pane filter control reverts to its no-chapters behaviour.
- **Item tagged to multiple chapters**: The item appears in the filtered view for each of those chapters and also in the "all" view. It does NOT appear in the "document-level only" view.
- **Chapter is deleted while items are tagged to it only**: Those items become document-level. They are not deleted.
- **Chapter is deleted while items are tagged to it and to other chapters**: Items lose only the deleted chapter's association; other associations are preserved.
- **Filter is set to a chapter, then that chapter is deleted**: The filter falls back to "all" and the writer is shown the broader list.
- **Pre-existing data after migration**: All sources and snippets that existed before this feature shipped have zero chapter associations and are therefore document-level. Visible in "all" and "document-level only" views by default.
- **Empty filter result**: When a filter setting yields no items, the pane shows an empty state with the active filter clearly indicated and a one-click way to broaden to "all".

## Requirements *(mandatory)*

### Functional Requirements

#### Data and tagging

- **FR-001**: The system MUST allow each source to be associated with zero or more chapters of its containing document.
- **FR-002**: The system MUST allow each snippet to be associated with zero or more chapters of its containing document.
- **FR-003**: The system MUST treat a source or snippet with zero chapter associations as "document-level".
- **FR-004**: A source or snippet MUST only be associatable with chapters that belong to its own document (cross-document chapter associations are not allowed).
- **FR-005**: When a chapter is deleted, the system MUST remove all chapter-tag associations referencing that chapter, leaving the underlying sources and snippets intact (becoming document-level if no other chapter associations remain).

#### Add/save flows

- **FR-006**: When the writer adds a new source to a document that has at least one chapter, the add-source flow MUST present an optional chapter picker that allows selecting zero or more chapters.
- **FR-007**: When the writer saves a new snippet in a document that has at least one chapter, the snippet-save flow MUST present an optional chapter picker that allows selecting zero or more chapters.
- **FR-008**: The chapter picker in both flows MUST default to no chapters selected (document-level).
- **FR-009**: When the writer adds a source or saves a snippet in a document that has zero chapters, the chapter picker MUST be hidden or otherwise non-presented.
- **FR-010**: When the writer is editing inside a specific chapter and adds a new source or saves a new snippet without explicitly selecting any chapter, the new item MUST be created as document-level (no auto-tagging).

#### Retroactive editing

- **FR-011**: From the sources pane, the writer MUST be able to view and edit the chapter associations of any existing source.
- **FR-012**: From the snippets pane, the writer MUST be able to view and edit the chapter associations of any existing snippet.
- **FR-013**: Edits to chapter associations MUST persist immediately and be reflected in the pane's filtered view without requiring a page reload.

#### Filtering

- **FR-014**: The sources pane MUST provide a filter control with the modes: "all", "document-level only", and one mode per chapter in the document.
- **FR-015**: The snippets pane MUST provide a filter control with the same modes as the sources pane.
- **FR-016**: When the filter is set to "all", the pane MUST show every source/snippet in the document regardless of chapter associations.
- **FR-017**: When the filter is set to "document-level only", the pane MUST show only sources/snippets with zero chapter associations.
- **FR-018**: When the filter is set to a specific chapter, the pane MUST show only sources/snippets that are associated with that chapter (an item with multiple associations appears in each of its chapters' filtered views).
- **FR-019**: When the writer's editing context moves into a specific chapter and no explicit filter override is active, the sources and snippets pane filters MUST default to that chapter.
- **FR-020**: A manual filter override MUST persist until the writer either changes the filter again or the editing context moves to a different chapter.
- **FR-021**: When the active filter is on a chapter that is then deleted, the filter MUST fall back to "all".
- **FR-022**: When the filter yields zero items, the pane MUST show an empty state that names the active filter and offers a one-click broaden-to-all action.
- **FR-023**: When the document has zero chapters, the filter control MUST be hidden or disabled and all items MUST be shown.

#### Migration and back-compatibility

- **FR-024**: Pre-existing sources and snippets MUST default to document-level (no chapter associations) after the feature is deployed; no data migration that infers tags is required.
- **FR-025**: The migration MUST be safe to apply on a populated production database without data loss.

### Key Entities *(include if feature involves data)*

- **Source–Chapter Association**: A many-to-many link between a source and a chapter. Each association references exactly one source and one chapter, and both must belong to the same document. Removing a chapter removes all its associations; removing a source removes all its associations. Associations have no payload of their own (no order, label, or metadata) — their presence simply records that the source belongs to the chapter for organising purposes.
- **Snippet–Chapter Association**: A many-to-many link between a snippet and a chapter, with the same semantics as Source–Chapter Association.
- **Sources Pane Filter State**: The current filter setting for the sources pane (one of "all", "document-level only", or a specific chapter). Includes a flag for whether the current setting is the auto-default from editing context or an explicit user override.
- **Snippets Pane Filter State**: Equivalent filter state for the snippets pane, with the same shape as Sources Pane Filter State.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A writer with a document containing at least 30 sources spread across 5+ chapters can locate any tagged source in under 10 seconds using the filter (vs. scanning a flat list).
- **SC-002**: 100% of newly added sources and saved snippets honour the chapter selection (or absence thereof) made by the writer at creation time — verified by inspection of associations after each operation.
- **SC-003**: 100% of pre-existing sources and snippets are visible in the "all" and "document-level only" filter views immediately after the feature ships, with no manual cleanup required.
- **SC-004**: Deleting a chapter never destroys an associated source or snippet — verified by data audit before and after a chapter deletion in a populated document.
- **SC-005**: Auto-default filter on chapter context change is correct on first focus into a chapter at least 95% of the time in usage testing (the remaining margin accounts for ambiguous caret positions, e.g. between chapters).
- **SC-006**: Documents with zero chapters behave identically to today (no new UI surfaces, no behavioural regression in the add-source or snippet-save flows).

## Assumptions

- **Chapter feature already exists**: This spec builds on spec 016 (document chapters). Chapters are assumed to be a stable structural primitive on documents with a stable identifier.
- **Sources and snippets are scoped to a single document**: Cross-document sharing is out of scope; an association links a source/snippet to a chapter within the same document only.
- **Editing context is detectable**: The system can determine which chapter (if any) the writer's caret is currently in, since that capability is required by spec 016. The auto-default filter (FR-019) relies on this signal.
- **Filter state lives on the client**: Per-pane filter state is session-scoped and need not persist across page reloads. The only persistent state is the chapter associations themselves.
- **No free-form tags are introduced**: Chapters are the only organisational axis for sources and snippets in this feature. Adding a separate tag taxonomy is explicitly out of scope.
- **Picker UI is multi-select**: The chapter picker in add/save and edit flows allows zero, one, or multiple chapter selections. UI affordance details (checklist, chips, dropdown) are implementation choices.
- **No bulk re-tagging UI required for Phase 1**: Editing chapter tags retroactively works one item at a time. A bulk operation across many sources/snippets at once is not required.

## Out of Scope

The following are intentionally deferred to later phases of the broader chapter-scoped research initiative ([.exploration/chapter-scoped-research.md](../../.exploration/chapter-scoped-research.md)):

- Automatic tagging of newly created sources or snippets based on the current editing context.
- Semantic search over sources or snippets, scoped or otherwise.
- "Summarise this source" or any cached source summary feature.
- Discover-new-sources flows (web search, paperstore search, deep research routing, Holding Pen integration).
- Any change to the snippet schema beyond the new join table.
- Chapter split/merge handling (no such feature exists today).
- Promoting snippets to citations.
- Cross-document source sharing.
