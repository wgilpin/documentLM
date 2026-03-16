# API Contracts: Universal App Settings

**Feature**: 007-universal-settings
**Date**: 2026-03-16

## GET /api/settings

Returns the current user settings. If no settings have been saved yet, returns defaults.

### Response 200 OK

```json
{
  "display_name": null,
  "language_code": "en",
  "ai_instructions": null,
  "updated_at": "2026-03-16T12:00:00Z"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `display_name` | `string \| null` | User's name; null if not set |
| `language_code` | `string` | BCP 47 tag; default `"en"` |
| `ai_instructions` | `string \| null` | Up to 2,000 chars; null if not set |
| `updated_at` | `ISO 8601 datetime` | Last save time |

---

## POST /api/settings

Upsert user settings. Responds with an HTMX-friendly fragment on success (empty body + `HX-Trigger: settingsSaved` header to trigger modal close).

### Request Body (form-encoded or JSON)

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `display_name` | `string \| null` | No | Max 255 chars |
| `language_code` | `string` | No | Must be one of the supported codes; defaults to `"en"` |
| `ai_instructions` | `string \| null` | No | Max 2,000 chars |

### Response 200 OK

Returns the updated `UserSettingsResponse` JSON (same shape as GET response).

HTMX response header: `HX-Trigger: settingsSaved` — consumed by the frontend to close the dialog.

### Response 422 Unprocessable Entity

Returned when `ai_instructions` exceeds 2,000 characters or `language_code` is invalid.

```json
{
  "detail": [
    {
      "loc": ["body", "ai_instructions"],
      "msg": "String should have at most 2000 characters",
      "type": "string_too_long"
    }
  ]
}
```

---

## UI Contract: Settings Modal

The settings icon (`⚙`) appears in the document toolbar immediately left of the Delete button (`.toolbar-btn--danger`).

Clicking it calls `document.getElementById('settings-dialog').showModal()`.

The modal contains a `<form>` that posts to `POST /api/settings` via HTMX:

```html
hx-post="/api/settings"
hx-trigger="submit"
hx-target="#settings-response"
hx-swap="outerHTML"
```

On `HX-Trigger: settingsSaved`, a small inline JS listener calls `dialog.close()`.

The AI instructions `<textarea>` has `maxlength="2000"` and a live character counter driven by an `input` event listener (minimal inline JS — ~3 lines).
