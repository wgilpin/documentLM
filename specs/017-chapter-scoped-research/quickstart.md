# Quickstart: Chapter-Scoped Sources and Snippets (Phase 1)

End-to-end manual verification path. Use after implementation to confirm the feature works in a running stack. The Constitution mandates manual UI/endpoint validation in lieu of automated tests for those layers.

## Prereqs

```bash
# Ask before running these — per CLAUDE.md
docker compose up -d postgres
cd /Users/will/projects/document-projects/documentLM && uv run alembic upgrade head
cd /Users/will/projects/document-projects/documentLM && npm run build:dev   # only if static/editor.js changed
cd /Users/will/projects/document-projects/documentLM && uv run uvicorn writer.main:app --reload
```

Open <http://localhost:8000>, log in.

## Verify migration

```bash
docker exec -it <postgres-container> psql -U documentlm -d documentlm -c "\d chapter_sources"
```

Expect: composite PK `(chapter_id, source_id)`, two CASCADE FKs, secondary index `chapter_sources_source_idx`.

## Walkthrough

### 1. Set up a fixture document

1. Create a new document titled "Chapter Tag Demo".
2. Add three chapters: "Background", "Method", "Findings".
3. Add five sources (mix of note + URL): two will be tagged to chapters in step 3, three left document-level.
4. Highlight some text in one of the URL sources and save four snippets — two will be tagged, two left document-level.

### 2. Verify add-source picker (FR-006, FR-008)

- Open the **Add Source** disclosure on the sources panel. Each of the three tabs (Note / URL / PDF) shows a "Chapters" `<details>` containing one checkbox per chapter, all unchecked by default.
- Add a new note **without** ticking any chapter. Confirm the new row appears with no chapter chips → it is document-level.
- Add a new note **with** "Background" and "Method" both ticked. Confirm the new row's chapter chips show both names.

### 3. Verify retroactive editing (FR-011, FR-013)

- On an existing source row, click the chapter-tag affordance. Popover opens with the chapter checkbox list reflecting current state.
- Toggle: add "Findings", remove "Background". Apply.
- Confirm the row's chips update in place without a full page reload, and the database row in `chapter_sources` reflects the change.

### 4. Verify filter modes (FR-014–FR-018)

- In the source filter `<select>` at the top of the sources pane:
  - **All** — every source is visible.
  - **Document-level only** — only the three untagged sources are visible.
  - **Background** — only sources tagged with "Background" are visible.
  - **Method** — only sources tagged with "Method" are visible (an item tagged to both Background+Method should appear in both views).

### 5. Verify auto-default filter on chapter context (FR-019, FR-020)

- Click into the "Background" chapter editor. Both source-list and snippet-bank panes should auto-filter to "Background".
- Manually change the source filter to "All". Stays on "All" while you remain in Background.
- Click into the "Method" chapter. Filter resets to default ("Method") in both panes — manual override cleared by context change.

### 6. Verify snippet flow (FR-002, FR-007, FR-012, FR-015–FR-018)

- Highlight text in the source viewer, save as a snippet, with "Findings" ticked. Confirm the snippet card carries the chip.
- Edit a previously document-level snippet to add "Method". Card updates in place.
- Filter the snippet bank by each scope as in step 4.

### 7. Verify chapter-deletion drift (FR-005, FR-021, edge cases)

- Note: the "Method"-only-tagged source IDs and snippet IDs.
- Delete the "Method" chapter.
- Confirm:
  - Method-only sources/snippets become document-level (visible under "Document-level only").
  - Sources/snippets that were tagged to both Method and another chapter retain their other tag.
  - The filter `<select>` no longer lists "Method".
  - If a pane was actively filtered on "Method" at delete time, it falls back to "All".
  - The underlying `sources` and `snippets` rows still exist (run `SELECT count(*) FROM sources;` before/after to confirm).

### 8. Zero-chapter document case (FR-009, FR-023)

- Create a second document with **no** chapters.
- Open Add Source — the chapter picker is hidden.
- Open the source pane filter — control is hidden or disabled, all items shown.
- Delete the last remaining chapter on the first document — same behaviour applies.

### 9. Migration safety (FR-024, FR-025)

Run `uv run pytest tests/integration/` to confirm no pre-existing data was touched. Specifically check that pre-feature sources still appear, all default to document-level (no rows in `chapter_sources`).

## Service-layer test gate

```bash
cd /Users/will/projects/document-projects/documentLM && uv run pytest tests/unit/test_source_service.py tests/unit/test_snippet_service.py -v
```

All new service tests must pass. Then full suite:

```bash
cd /Users/will/projects/document-projects/documentLM && uv run pytest
```

Must pass with zero regressions.

## Lint + type gate

```bash
cd /Users/will/projects/document-projects/documentLM && uv run ruff check --fix src/ tests/
cd /Users/will/projects/document-projects/documentLM && uv run ruff format src/ tests/
cd /Users/will/projects/document-projects/documentLM && uv run mypy src/
```

All zero errors required before commit.

## Acceptance mapping

| Spec Acceptance Scenario              | Quickstart Step    |
|---------------------------------------|--------------------|
| US1 / 1–2 (add source, with/without)  | Step 2             |
| US1 / 3 (retroactive edit)            | Step 3             |
| US1 / 4–6 (filter modes)              | Step 4             |
| US2 / 1–2 (snippet save, with/without)| Step 6             |
| US2 / 3 (snippet edit)                | Step 6             |
| US2 / 4 (snippet filter)              | Step 6             |
| US3 / 1–2 (auto-default + override)   | Step 5             |
| US3 / 3 (empty state on auto-filter)  | Step 4 / 5         |
| US3 / 4 (no auto-tag on add)          | Step 2 last bullet |
| Edge: zero chapters                   | Step 8             |
| Edge: chapter delete drift            | Step 7             |
| FR-024 / FR-025 (migration safety)    | Step 9             |
