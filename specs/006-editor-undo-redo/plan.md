# Implementation Plan: Editor Undo/Redo

**Branch**: `006-editor-undo-redo` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-editor-undo-redo/spec.md`

## Summary

Add undo/redo to the TipTap document editor with per-keystroke granularity and atomic AI-change entries. A toolbar above the editor exposes Undo/Redo buttons (plus Ctrl+Z / Ctrl+Y keyboard shortcuts). The buffer depth is controlled by `UNDO_BUFFER_SIZE` in `.env`. All state is client-side only; the only backend change is reading and forwarding the config value to the template.

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg, TipTap v2 (CDN)
**Storage**: PostgreSQL (Docker container) — no changes
**Testing**: pytest (unit test for `undo_buffer_size` config validator only)
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: Web service (FastAPI + HTMX)
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save; custom JS only where HTMX has no equivalent
**Scale/Scope**: Demo/prototype — YAGNI

## Constitution Check

- [x] **I. Python + uv**: Config change is Python; no new packages added
- [x] **II. TDD scope**: One new service-layer concern (config validation) covered by unit test; no tests for frontend
- [x] **III. No remote APIs in tests**: Config unit test has no external calls
- [x] **IV. Simplicity**: TipTap's native history extension reused; no custom undo stack
- [x] **V. Strong typing**: `undo_buffer_size: int` added with validator; `main.py` template context typed
- [x] **VI. Functional style**: No new classes; validator is a classmethod on existing Settings
- [x] **VII. Ruff**: All new Python will pass ruff before commit
- [x] **VIII. Containers**: No infra changes
- [x] **IX. Logging**: Invalid `UNDO_BUFFER_SIZE` logs a WARNING at startup (FR-011)
- [x] **ADK architecture**: No new agent types

## Complexity Tracking

| Violation                                         | Why Needed                                                                                 | Simpler Alternative Rejected Because                                     |
|---------------------------------------------------|--------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Custom JavaScript (3 additions to document.html) | HTMX has no undo/redo primitive; TipTap must be configured and its AI change path patched | Cannot replace client-side history management with server round-trips |

## Project Structure

### Documentation (this feature)

```text
specs/006-editor-undo-redo/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── env-config.md
│   └── ai-change-boundary.md
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code Changes

```text
src/writer/
├── core/
│   └── config.py          ← add undo_buffer_size field + validator
├── main.py                ← pass undo_buffer_size to document.html template context
└── templates/
    └── document.html      ← toolbar HTML, TipTap history config, AI change fix, button state

static/
└── style.css              ← toolbar + button styles

.env.example               ← add UNDO_BUFFER_SIZE=1000

tests/
└── unit/
    └── test_config.py     ← new: test undo_buffer_size validation fallback
```

**Structure Decision**: Single-project layout. No new directories. All changes extend existing files.

---

## Phase 0: Research

See [research.md](research.md). All unknowns resolved. No NEEDS CLARIFICATION markers remain.

**Key decisions**:

1. Use TipTap's native `history` extension (in StarterKit) — no custom undo stack
2. `newGroupDelay: 0` — per-keystroke granularity
3. AI changes: `tr.replaceWith()` dispatch instead of `setContent()` — single undoable entry
4. Button state: `editor.can().undo()` / `editor.can().redo()` on every transaction
5. Config validation: Pydantic `field_validator` with warning fallback to 1000

---

## Phase 1: Design

### 1. Backend: Config (`src/writer/core/config.py`)

Add `undo_buffer_size` to `Settings`:

```python
from pydantic import field_validator

class Settings(BaseSettings):
    ...
    undo_buffer_size: int = 1000

    @field_validator("undo_buffer_size", mode="before")
    @classmethod
    def validate_buffer_size(cls, v: object) -> int:
        try:
            n = int(v)  # type: ignore[arg-type]
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass
        import logging
        logging.getLogger(__name__).warning(
            "Invalid UNDO_BUFFER_SIZE value %r; falling back to 1000", v
        )
        return 1000
```

### 2. Backend: Template context (`src/writer/main.py`)

Pass `undo_buffer_size` to `document.html` in both routes that render it:

```python
# GET /documents/new
return templates.TemplateResponse(
    "document.html",
    {"request": request, "doc": None, "undo_buffer_size": settings.undo_buffer_size},
)

# GET /documents/{doc_id}
return templates.TemplateResponse(
    "document.html",
    {"request": request, "doc": doc, "undo_buffer_size": settings.undo_buffer_size},
)
```

### 3. Frontend: Toolbar HTML (`src/writer/templates/document.html`)

Insert a toolbar `<div>` **above** the TipTap mount point (`#tiptap-mount`), before the hidden textarea:

```html
<div class="editor-toolbar">
  <button id="undo-btn" class="toolbar-btn" disabled title="Undo" aria-label="Undo">
    &#8630; Undo
  </button>
  <button id="redo-btn" class="toolbar-btn" disabled title="Redo" aria-label="Redo">
    Redo &#8631;
  </button>
</div>
```

### 4. Frontend: TipTap History Configuration (`document.html` script)

Expose `undo_buffer_size` from Jinja2 into JS, then configure `StarterKit`:

```js
const UNDO_BUFFER_SIZE = {{ undo_buffer_size }};

const editor = new Editor({
  element: document.querySelector('#tiptap-mount'),
  extensions: [
    StarterKit.configure({
      history: {
        depth: UNDO_BUFFER_SIZE,
        newGroupDelay: 0,   // per-keystroke granularity
      },
    }),
    // ... existing extensions
  ],
  // ...
})
```

### 5. Frontend: AI Change — Undoable Transaction

Replace the existing `editor.commands.setContent(parsed)` call inside the MutationObserver callback with a single ProseMirror transaction:

```js
// BEFORE (resets history):
// editor.commands.setContent(parsed)

// AFTER (single undoable entry):
const tr = editor.state.tr
const newDoc = editor.schema.nodeFromJSON(parsed)
tr.replaceWith(0, editor.state.doc.content.size, newDoc.content)
tr.setMeta('ai-change', true)
editor.view.dispatch(tr)
```

### 6. Frontend: Button State & Tooltips

Add an `onTransaction` listener that runs after TipTap initialises:

```js
let lastChangeType = null  // 'keystroke' | 'ai-change'

editor.on('transaction', ({ transaction }) => {
  if (transaction.docChanged) {
    lastChangeType = transaction.getMeta('ai-change') ? 'ai-change' : 'keystroke'
  }
  const undoBtn = document.getElementById('undo-btn')
  const redoBtn = document.getElementById('redo-btn')
  const canUndo = editor.can().undo()
  const canRedo = editor.can().redo()
  undoBtn.disabled = !canUndo
  redoBtn.disabled = !canRedo
  undoBtn.title = canUndo
    ? (lastChangeType === 'ai-change' ? 'Undo AI change' : 'Undo')
    : 'Nothing to undo'
})

document.getElementById('undo-btn').addEventListener('click', () => editor.chain().focus().undo().run())
document.getElementById('redo-btn').addEventListener('click', () => editor.chain().focus().redo().run())
```

Note: Ctrl+Z and Ctrl+Y/Ctrl+Shift+Z are handled automatically by TipTap's history extension — no additional keyboard listener needed.

### 7. CSS (`static/style.css`)

Add toolbar styles:

```css
.editor-toolbar {
  display: flex;
  gap: 0.25rem;
  padding: 0.375rem 0.5rem;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  background: var(--surface-color, #f9fafb);
}

.toolbar-btn {
  padding: 0.25rem 0.625rem;
  font-size: 0.8125rem;
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 0.25rem;
  background: white;
  cursor: pointer;
  color: var(--text-color, #374151);
}

.toolbar-btn:hover:not(:disabled) {
  background: var(--hover-bg, #f3f4f6);
}

.toolbar-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

### 8. Tests (`tests/unit/test_config.py`)

Unit tests for `undo_buffer_size` validation (TDD — write tests first):

```python
def test_undo_buffer_size_valid():
    s = Settings(undo_buffer_size=500)
    assert s.undo_buffer_size == 500

def test_undo_buffer_size_default():
    s = Settings()
    assert s.undo_buffer_size == 1000

def test_undo_buffer_size_zero_falls_back(caplog):
    s = Settings(undo_buffer_size=0)
    assert s.undo_buffer_size == 1000
    assert "UNDO_BUFFER_SIZE" in caplog.text

def test_undo_buffer_size_negative_falls_back(caplog):
    s = Settings(undo_buffer_size=-5)
    assert s.undo_buffer_size == 1000

def test_undo_buffer_size_non_numeric_falls_back(caplog):
    s = Settings(undo_buffer_size="banana")
    assert s.undo_buffer_size == 1000
```

### 9. `.env.example`

Add:

```ini
UNDO_BUFFER_SIZE=1000
```

---

## Implementation Order

1. `tests/unit/test_config.py` — write failing tests (TDD)
2. `src/writer/core/config.py` — add field + validator (make tests green)
3. `src/writer/main.py` — add `undo_buffer_size` to template context
4. `src/writer/templates/document.html` — toolbar HTML + TipTap config + AI change fix + button state
5. `static/style.css` — toolbar styles
6. `.env.example` — document new variable
7. Run `uv run pytest`, `ruff check --fix`, `ruff format`, `mypy src/`
