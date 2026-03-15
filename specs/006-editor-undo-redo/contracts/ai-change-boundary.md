# Contract: AI Change Boundary Protocol

**Feature**: `006-editor-undo-redo`

## Overview

When the AI agent writes new document content, the frontend must record that change as a single atomic undo entry. This contract defines how the JavaScript undo manager identifies an AI change vs. a user keystroke.

## Detection Mechanism

The AI agent signals its change via the existing HTMX **OOB swap** of the `#document-content` textarea. The MutationObserver in `document.html` already detects this swap.

**The contract**: when the MutationObserver fires and new document content is loaded, the JavaScript MUST use a ProseMirror transaction dispatch (not `setContent()`) and MUST attach the metadata marker `ai-change: true` to that transaction.

## Transaction Marker

```js
// Required on every AI-triggered content replacement
tr.setMeta('ai-change', true)
```

This marker is checked by the `onTransaction` listener to:
1. Update `lastChangeType` to `'ai-change'`
2. Set the Undo button tooltip to `"Undo AI change"`

## Invariants

| Invariant | Description |
|-----------|-------------|
| One transaction per AI change | The entire AI replacement MUST be dispatched as a single `tr.replaceWith(...)` call |
| No `setContent()` for AI changes | `editor.commands.setContent()` resets history and is forbidden for AI-triggered updates |
| Keystroke transactions carry no marker | Normal typing transactions do NOT set `ai-change` meta — their absence identifies them as keystrokes |
