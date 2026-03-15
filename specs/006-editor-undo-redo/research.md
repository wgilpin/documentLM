# Research: Editor Undo/Redo

**Branch**: `006-editor-undo-redo` | **Date**: 2026-03-15

## Decision 1: Use TipTap's Native History Extension

**Decision**: Use TipTap's built-in `history` extension (included in `StarterKit`) rather than a custom undo stack.

**Rationale**: The history extension is a thin wrapper over ProseMirror's mature, battle-tested history plugin. It already handles the transaction model, step inversion, and grouping. Custom re-implementation would violate YAGNI and duplicate existing functionality.

**Alternatives considered**:
- Custom JS undo stack tracking document snapshots: rejected — delta storage requires knowing ProseMirror's internal step format anyway; duplicates the history plugin.
- External undo library (e.g., `undox`): rejected — not compatible with ProseMirror's transaction model.

**TipTap v2 API** (version currently in use):
```js
// StarterKit configuration
StarterKit.configure({
  history: {
    depth: 1000,       // buffer size (default: 100)
    newGroupDelay: 0,  // ms — 0 = every keystroke is a discrete entry
  },
})
```

Note: TipTap v3 renames this option to `undoRedo`. If the project upgrades, update accordingly.

---

## Decision 2: Per-Keystroke Granularity via `newGroupDelay: 0`

**Decision**: Set `newGroupDelay: 0` to disable transaction grouping by time.

**Rationale**: The spec requires each individual keystroke to be a discrete undo entry (FR-002). ProseMirror's default `newGroupDelay: 500ms` merges consecutive keystrokes typed within 500ms into one history step. Setting it to 0 ensures every character insertion/deletion is its own step.

**Trade-off**: A 1000-entry buffer now holds 1000 individual characters worth of history, not 1000 "typing sessions". The spec acknowledges this ("buffer may therefore hold thousands of entries") — the configurable size via `.env` compensates.

---

## Decision 3: AI Changes as a Single Undoable Transaction

**Decision**: When the MutationObserver detects an OOB textarea swap (AI change), use a ProseMirror transaction to replace document content rather than calling `editor.commands.setContent()`.

**Rationale**: `setContent()` bypasses the history system and resets it. A direct transaction dispatch creates a single history entry that can be undone in one step (FR-003, FR-004).

**Implementation pattern**:
```js
// Instead of: editor.commands.setContent(newContent)
// Use:
const tr = editor.state.tr
const newDoc = editor.schema.nodeFromJSON(parsedContent)
tr.replaceWith(0, editor.state.doc.content.size, newDoc.content)
tr.setMeta('ai-change', true)   // marks this entry for tooltip labelling
editor.view.dispatch(tr)
```

The `setMeta('ai-change', true)` flag allows the `onTransaction` listener to record the type of the last history entry for tooltip purposes.

---

## Decision 4: Button State via `editor.can().undo()` / `editor.can().redo()`

**Decision**: Update toolbar button enabled/disabled state by calling `editor.can().undo()` and `editor.can().redo()` inside an `onTransaction` handler.

**Rationale**: These methods query the ProseMirror state directly and are the canonical TipTap API for this purpose. Checking on every transaction (including selection changes) ensures the buttons always reflect current state (SC-003).

```js
editor.on('transaction', () => {
  undoBtn.disabled = !editor.can().undo()
  redoBtn.disabled = !editor.can().redo()
  updateTooltips()
})
```

---

## Decision 5: Tooltip Labels Track Last Change Type

**Decision**: Maintain a module-level variable `lastChangeType: 'keystroke' | 'ai-change' | null` updated on each `transaction` event. Use it to set the Undo button's `title` attribute.

**Rationale**: ProseMirror's history does not expose the type of the top-of-stack entry. Tracking externally is the simplest approach. The AI change marker (`setMeta('ai-change', true)`) distinguishes AI transactions; all other `docChanged` transactions are classified as keystrokes.

---

## Decision 6: Config — Python `Settings` Validator with Fallback

**Decision**: Add `undo_buffer_size: int` to `core/config.py` with a `field_validator` that falls back to 1000 and logs a warning for invalid values, rather than raising a validation error.

**Rationale**: FR-011 requires a graceful fallback, not a startup crash. A validator that returns the default on invalid input satisfies this. The warning satisfies Principle IX.

```python
@field_validator('undo_buffer_size', mode='before')
@classmethod
def validate_buffer_size(cls, v: object) -> int:
    try:
        n = int(v)
        if n > 0:
            return n
    except (TypeError, ValueError):
        pass
    logger.warning("Invalid UNDO_BUFFER_SIZE value %r, falling back to 1000", v)
    return 1000
```

---

## No New Dependencies

All capabilities are already present:
- TipTap `history` extension: included in `StarterKit` (already a dependency)
- Keyboard shortcuts Ctrl+Z / Ctrl+Y: provided automatically by TipTap's history extension
- Python config: Pydantic v2 validators (already in use)

No new packages required.
