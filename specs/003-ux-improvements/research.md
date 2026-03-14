# Research: UX Improvements

**Branch**: `003-ux-improvements` | **Date**: 2026-03-13

## Decisions

### 1. Inline Suggestions: Editor-pane Overlay

**Decision**: Keep the `<textarea>` editor; render suggestion cards in a dedicated `#inline-suggestions` overlay container positioned absolutely within `.editor-pane`. The overlay floats over the right portion of the textarea.

**Rationale**: Replacing the textarea with a `contenteditable` div would require rewriting all auto-save HTMX bindings, cursor tracking, and key-event handling. The spec requirement — "inject AI-generated text directly into the document editor" — is satisfied by positioning suggestion cards visually within the editor pane (not the separate sidebar). The HTMX accept/reject wiring remains unchanged.

**Alternatives considered**:
- `contenteditable` div: Enables true in-document text annotation but requires significant refactor of the textarea-based auto-save.
- Sidebar suggestion panel (status quo): Rejected — fails the "inline" spec requirement and increases context-switching.
- Character-offset pixel positioning (map `selectionStart` to pixel rect): Accurate but requires ~30 lines of custom JS for scroll + line-height math. Not justified given the YAGNI principle.

---

### 2. Source Entry Collapse: `<details>/<summary>`

**Decision**: Use the native HTML `<details>/<summary>` elements to wrap the source input form. The `<summary>` acts as the "Add Source" button.

**Rationale**: Zero JavaScript required. The browser handles expand/collapse, accessibility (keyboard, screen reader), and open/close state natively. Satisfies FR-012 through FR-014 without any custom code.

**Alternatives considered**:
- CSS `max-height` toggle via class: Requires at least one JS event listener.
- HTMX `hx-get` to load form on demand: Adds a round-trip network request for a purely local interaction.

---

### 3. Delete De-emphasis: Pure CSS Hover Visibility

**Decision**: Change `.btn-danger` to a new `.btn-ghost-danger` class (gray by default). Add CSS rule `.source-item:hover .btn-ghost-danger { visibility: visible; }` and `.btn-ghost-danger { visibility: hidden; }` to the base rule.

**Rationale**: The entire change is three CSS rules plus a class rename on the `<button>` element in `sources.html`. No JavaScript, no HTMX change. `visibility: hidden` preserves layout so the source-item height doesn't change on hover.

**Alternatives considered**:
- `display: none` / `display: block`: Causes layout shift on hover.
- Opacity transition: Extra CSS; hidden elements still intercept pointer events unless `pointer-events: none` is also added.

---

### 4. Global Command Modal: Native `<dialog>` Element

**Decision**: Use the HTML `<dialog>` element. Show with `dialog.showModal()` triggered by a keyboard shortcut (`Ctrl+K`/`Cmd+K`) and a floating action button. The modal submits to the existing `POST /api/documents/{doc_id}/comments` endpoint via HTMX.

**Rationale**: `<dialog>` provides native focus-trap, Escape-to-close, and backdrop overlay — all for free. The only custom JS needed (~4 lines) is the `showModal()` call and keyboard event listener. HTMX handles the form submission unchanged.

**Alternatives considered**:
- Custom div modal with JS: More code, no accessibility benefits.
- HTMX-only (`hx-trigger="keyup[...]"`): HTMX `keyup` trigger cannot detect global keyboard shortcuts that fire outside a specific element.

---

### 5. Contextual Floating Menu: `getBoundingClientRect()` + `position:fixed`

**Decision**: On `mouseup` event of the textarea, check if `selectionStart !== selectionEnd`. If text is selected, call `textarea.getBoundingClientRect()` to get the textarea's viewport position, then show a `position:fixed` `<div id="floating-menu">` near the selection. The "Add AI Instruction" button in the menu opens the command modal pre-populated with the selection data (already captured by the existing selection listener).

**Rationale**: The existing selection-detection JS in `document.html` already captures start/end/text. The new code adds ~8 lines: position calculation and show/hide of the floating div. No new libraries needed.

**Alternatives considered**:
- `window.getSelection().getRangeAt(0).getBoundingClientRect()`: Works for `contenteditable` but not reliably for `<textarea>` selections in all browsers.
- HTMX trigger: No HTMX attribute can respond to textarea `mouseup` selection state.

---

### 6. Meta-chat Panel: `<details>/<summary>` + New `ChatAgent`

**Decision**: The panel is a `<details>/<summary>` section at the bottom of the sidebar (zero-JS collapse). Inside, a chat history list and input form submit via HTMX to a new `POST /api/documents/{doc_id}/chat` endpoint. A new `ChatAgent` (google-adk) handles conversational responses.

**Rationale**: `<details>` handles collapse with zero JS. The new `ChatAgent` uses a different system prompt from `DrafterAgent` (open-ended brainstorming vs. targeted document edits), justifying a separate agent type per the ADK architecture pattern. New `ChatMessage` ORM model stores turn history (document-scoped, session-visible, not cross-session persistent per spec).

**Alternatives considered**:
- Reuse `DrafterAgent` with different prompt: Conflates document-editing concerns with brainstorming; Drafter outputs formatted suggestions, not conversational text.
- In-memory chat history (no DB): Loses history on server restart, inconsistent with project's PostgreSQL persistence pattern.

---

## Summary: Custom JS Required (HTMX Cannot Replace)

| Interaction                      | JS Lines Needed | Why HTMX Cannot Replace                              |
| -------------------------------- | --------------- | ---------------------------------------------------- |
| Command modal show/hide          | ~4              | `dialog.showModal()` + global `keydown` shortcut     |
| Floating menu show/hide/position | ~8              | `mouseup` selection detection + viewport positioning |

All other interactions (form submission, source CRUD, suggestion accept/reject, meta-chat) use existing or new HTMX attributes exclusively.
