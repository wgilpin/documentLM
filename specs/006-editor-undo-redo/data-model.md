# Data Model: Editor Undo/Redo

**Branch**: `006-editor-undo-redo` | **Date**: 2026-03-15

## Overview

All undo/redo state is **client-side only** — maintained in TipTap/ProseMirror's in-memory history plugin. There are no new database tables, no new server-side data structures, and no persistence across sessions.

The only backend change is a new configuration value read from the environment.

---

## New Backend Configuration Field

**Model**: `writer.core.config.Settings`

| Field | Type | Default | Source |
|-------|------|---------|--------|
| `undo_buffer_size` | `int` | `1000` | `UNDO_BUFFER_SIZE` env var |

**Validation**: Must be a positive integer. Any non-positive or non-numeric value is silently replaced with `1000` and logged as a warning.

---

## Client-Side Conceptual Entities

These are not Python types — they describe the in-memory structure managed by ProseMirror's history plugin.

### UndoEntry (ProseMirror history step)

Stored internally by ProseMirror as an inverted transaction step. The application does not access this structure directly.

| Attribute | Description |
|-----------|-------------|
| `type` | `'keystroke'` or `'ai-change'` — tracked externally via `lastChangeType` variable |
| `delta` | For keystrokes: one character insertion or deletion at a given cursor position. For AI changes: full document content replacement encoded as a ProseMirror step. |

### UndoBuffer

ProseMirror's history plugin manages this as two stacks: `done` and `undone`.

| Attribute | Description |
|-----------|-------------|
| `depth` | Maximum number of entries; value read from `Settings.undo_buffer_size` |
| `newGroupDelay` | `0` ms — each keystroke is a separate entry |

### RedoStack

The `undone` half of ProseMirror's history. Cleared automatically when a new edit is made after undoing.

---

## Template Context Change

The document template receives one additional variable:

| Variable | Type | Description |
|----------|------|-------------|
| `undo_buffer_size` | `int` | Passed from `Settings.undo_buffer_size`; rendered into `<script>` as `const UNDO_BUFFER_SIZE = {{ undo_buffer_size }}` |

---

## What Does NOT Change

- No new database tables or columns
- No Alembic migrations
- No new Pydantic request/response schemas
- No new agent types
- No changes to document storage format (TipTap JSON)
