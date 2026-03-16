# Research: Universal App Settings

**Feature**: 007-universal-settings
**Date**: 2026-03-16

## Decision Log

---

### D-001: Settings Storage — Single-row vs. keyed rows

**Decision**: Single-row `user_settings` table (fixed `id = 1` / upsert pattern).

**Rationale**: This is a single-user app. One row per "property group" is the simplest approach — no joins, no key-value parsing, direct ORM column access. SQLAlchemy upsert (`insert … on conflict do update`) or a simple "get-or-create" fetch is trivial.

**Alternatives considered**:
- Key-value store (`key TEXT, value TEXT`): flexible but loses typing, requires serialisation logic, and was rejected (YAGNI).
- Per-user row (multi-tenant): not needed; the constitution explicitly says single-user prototype.

---

### D-002: How AI instructions and user context reach the agent

**Decision**: `invoke_chat_agent` in `chat_service.py` accepts an optional `UserSettings` Pydantic model; the settings are injected into the `_INSTRUCTION` string at agent creation time (via `make_chat_agent`), not into the user-visible prompt.

**Rationale**: The existing `_INSTRUCTION` constant in `chat_agent.py` is the correct place to inject global system context. Appending it to the per-turn user message would pollute conversation history. Passing it to `make_chat_agent` as a parameter keeps the agent factory pure while keeping the service layer responsible for wiring.

**Alternatives considered**:
- Prepending to the user message each turn: leaks system config into visible conversation history, rejected.
- Storing in ADK session state: over-engineered; the runner is per-invocation anyway.

---

### D-003: Language setting format

**Decision**: Store as a BCP 47 language tag string (e.g., `"en"`, `"fr"`, `"zh"`). Default: `"en"`. Inject into the agent instruction as: `"Respond in the following language: {language_name} ({language_code})."`.

**Rationale**: BCP 47 is the standard. Short tags are readable and don't require a separate enum table. The human-readable name is derived at render time from a static dict in the service layer, keeping the DB schema clean.

**Alternatives considered**:
- Full locale codes (e.g., `"en-GB"`): useful but adds complexity with no payoff for a prototype; can be added later.
- DB enum: would require a migration every time a language is added, rejected.

---

### D-004: Character limit enforcement — DB vs. application layer

**Decision**: Enforce 2,000-character limit in the Pydantic schema (`max_length=2000`) and mirror it in the HTML textarea `maxlength` attribute. No DB-level constraint needed for a prototype.

**Rationale**: Pydantic validation at the API boundary is sufficient. Adding a DB check constraint is YAGNI for a single-user prototype.

---

### D-005: Settings API design

**Decision**: Two endpoints — `GET /api/settings` (fetch current, returns defaults if not set) and `POST /api/settings` (upsert). HTMX partial reload closes the modal on success.

**Rationale**: Simple REST. The modal is driven by HTMX: form submits `POST /api/settings`, on success the response swaps an empty element (or closes the dialog via `HX-Trigger` header). No separate `PUT` needed since there is only ever one row.

---

### D-006: Alembic migration

**Decision**: Add a new Alembic migration for the `user_settings` table. The table has a single row seeded by the `get_or_create_settings` service function (no DB-level default row needed).

**Rationale**: Follows the established migration pattern in `migrations/versions/`. No schema changes to existing tables.
