# Contract: Environment Configuration

**Feature**: `006-editor-undo-redo`

## `UNDO_BUFFER_SIZE`

| Property | Value |
|----------|-------|
| **Variable name** | `UNDO_BUFFER_SIZE` |
| **Type** | Positive integer |
| **Default** | `1000` |
| **Used by** | `Settings.undo_buffer_size` → passed to `document.html` template → TipTap history `depth` |

**Valid values**: Any integer `>= 1`. Recommended range: `100` – `10000`.

**Invalid values**: Zero, negative numbers, non-numeric strings. On invalid input the system falls back to `1000` and logs a warning at startup.

**Example `.env` entry**:
```
UNDO_BUFFER_SIZE=1000
```
