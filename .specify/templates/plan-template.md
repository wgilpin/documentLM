# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.12+
**Package Manager**: uv
**Primary Dependencies**: google-adk (local), FastAPI, HTMX, Pydantic v2, SQLAlchemy 2.x / asyncpg
**Storage**: PostgreSQL (Docker container)
**Testing**: pytest (backend services only — TDD; no tests for frontend components or API endpoints)
**Type Checking**: mypy (strict), ruff (linting + formatting)
**Target Platform**: Docker containers (app server + PostgreSQL)
**Project Type**: [e.g., web-service/cli/library or NEEDS CLARIFICATION]
**Performance Goals**: N/A — prototype/demo
**Constraints**: No remote API calls in tests; no plain dicts; no Any type; ruff must pass before save
**Scale/Scope**: Demo/prototype — YAGNI; no new features without explicit user confirmation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify each principle before proceeding:

- [ ] **I. Python + uv**: All new code is Python; uv used for deps
- [ ] **II. TDD scope**: Tests planned for service layer only (not endpoints, not frontend)
- [ ] **III. No remote APIs in tests**: All external calls mocked
- [ ] **IV. Simplicity**: Feature scope confirmed with user; no unrequested extras
- [ ] **V. Strong typing**: All function signatures use Pydantic/TypedDict; no plain dicts; no Any
- [ ] **VI. Functional style**: No unnecessary classes or inheritance
- [ ] **VII. Ruff**: ruff check + ruff format will be run before every save
- [ ] **VIII. Containers**: PostgreSQL + server run in Docker; docker-compose provided
- [ ] **IX. Logging**: Every except block logs; all significant operations emit log entries
- [ ] **ADK architecture**: Any new agent types confirmed against `docs/agents.md`; no undocumented agents introduced

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
