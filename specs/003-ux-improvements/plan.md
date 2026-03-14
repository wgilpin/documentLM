# Implementation Plan: UX Improvements

**Branch**: `003-ux-improvements` | **Date**: 2026-03-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-ux-improvements/spec.md`

## Summary

Implement all 6 UX improvements identified in the post-002 review: replace the permanent "ASK AI" sidebar with an on-demand command modal, add a contextual floating menu for text selections, move AI suggestion cards inline within the editor pane, collapse the source entry form behind a single button, hide delete controls behind hover state, and add a collapsible meta-chat panel for conversational brainstorming. All changes are frontend-heavy (HTML templates + CSS) with one new backend resource (meta-chat messages) and one new ADK agent (ChatAgent for conversational mode).

## Technical Context

**Language/Version**: Python 3.13+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX 2.0, Pydantic v2, SQLAlchemy 2.x / asyncpg
**Storage**: PostgreSQL (Docker container) — one new table: `chat_messages`
**Testing**: pytest — TDD for `chat_service.py` only; no tests for templates, CSS, or API endpoints
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers
**Project Type**: Web service (FastAPI + HTMX)
**Performance Goals**: N/A — prototype/demo
**Constraints**: HTMX-first; custom JS only where HTMX attributes cannot achieve the result; zero new `Any` types; ruff passes before save
**Scale/Scope**: Demo/prototype — YAGNI

### Key Technical Decisions (from research.md)

| Decision                     | Choice                                       | Rationale                                                |
| ---------------------------- | -------------------------------------------- | -------------------------------------------------------- |
| Inline suggestions placement | Editor-pane overlay (absolute position)      | No textarea migration; HTMX accept/reject unchanged      |
| Source entry collapse        | HTML `<details>/<summary>`                   | Zero JS; browser-native expand/collapse                  |
| Delete de-emphasis           | Pure CSS `:hover` visibility                 | No JS needed; single CSS rule                            |
| Command modal                | Native `<dialog>` + 2 JS lines               | Browser handles focus trap and Escape key                |
| Contextual menu positioning  | `getBoundingClientRect()` + `position:fixed` | ~8 lines JS; accurate for textarea selection             |
| Meta-chat agent              | New `ChatAgent` (google-adk)                 | Different prompt pattern from Drafter; confirmed by spec |

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. Python + uv**: All new code is Python; uv manages deps
- [x] **II. TDD scope**: Tests written only for `chat_service.py`; no tests for templates/endpoints/CSS
- [x] **III. No remote APIs in tests**: Agent calls in `chat_service.py` tests are mocked
- [x] **IV. Simplicity**: Feature scope confirmed — `<details>` over JS toggle, overlay over contenteditable; no extras
- [x] **V. Strong typing**: `ChatMessage` uses Pydantic; `ChatRole` uses `Enum`; no plain dicts
- [x] **VI. Functional style**: `chat_service.py` uses module-level functions; no utility classes
- [x] **VII. Ruff**: ruff check + ruff format run before every save
- [x] **VIII. Containers**: No new container needed; migration adds `chat_messages` table to existing Postgres
- [x] **IX. Logging**: `chat_service.py` logs all except blocks; agent errors logged at ERROR level
- [x] **ADK architecture**: `ChatAgent` added per `docs/agents.md` pattern; explicitly confirmed by feature spec

## Project Structure

### Documentation (this feature)

```text
specs/003-ux-improvements/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output
│   └── htmx-endpoints.md
└── tasks.md             ← Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/writer/
├── agents/
│   └── chat_agent.py           ← NEW: Google ADK ChatAgent for meta-chat
├── api/
│   └── chat.py                 ← NEW: /api/documents/{doc_id}/chat endpoints
├── models/
│   ├── db.py                   ← UPDATE: add ChatMessage ORM model
│   ├── enums.py                ← UPDATE: add ChatRole enum
│   └── schemas.py              ← UPDATE: add ChatMessageCreate, ChatMessageResponse
├── services/
│   └── chat_service.py         ← NEW: business logic (TDD)
└── templates/
    ├── document.html            ← UPDATE: restructure sidebar + add modal + floating menu
    └── partials/
        ├── sources.html         ← UPDATE: hover-only delete, details/summary wrapper
        ├── suggestion.html      ← UPDATE: styled for inline editor-pane overlay
        └── chat_message.html   ← NEW: single chat turn partial

static/style.css                 ← UPDATE: ~80 new lines for all new UI elements
migrations/
└── XXXX_add_chat_messages.py   ← NEW: Alembic migration
```

## Complexity Tracking

No constitution violations. All complexity justified:

| Element                               | Why Needed                                              | Simpler Alternative Rejected Because                       |
| ------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------- |
| New `ChatAgent` (ADK)                 | Needs distinct system prompt from Drafter               | Drafter reuse conflates edit and brainstorm concerns       |
| Minimal JS for dialog + floating menu | HTMX has no attribute for keyboard shortcuts or mouseup | No HTMX attr covers keyboard shortcuts or selection events |
