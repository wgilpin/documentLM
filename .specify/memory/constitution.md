<!--
SYNC IMPACT REPORT
==================
Version change: 1.1.0 → 1.2.0 (MINOR — FastAPI confirmed; HTMX added as
  frontend framework; minimize-JS constraint codified in Technology Stack)

Modified principles: None

Added sections:
- Technology Stack: FastAPI (confirmed), HTMX, minimize-JS rule

Removed sections: None

Templates reviewed:
- .specify/templates/plan-template.md       ✅ updated (Primary Dependencies confirmed + HTMX)
- .specify/templates/spec-template.md       ✅ no changes required
- .specify/templates/tasks-template.md      ✅ no changes required
- .specify/templates/agent-file-template.md ✅ no changes required

Deferred items: None
-->

# AI Document Workbench Constitution

## Core Principles

### I. Python + uv

All application code MUST be written in Python. The `uv` tool MUST be used for
virtual environment management and dependency installation. `pip` MUST NOT be
used to install packages in new work; any legacy `pip install -e` installs are
acceptable but future installs MUST migrate to `uv`.

**Rationale**: Consistent toolchain reduces onboarding friction and ensures
reproducible environments across machines.

### II. Test-Driven Development for Backend Services

TDD MUST be applied to all backend service code (business logic, data access,
transformations). The Red-Green-Refactor cycle MUST be followed: write a failing
test, confirm it fails, implement the minimum code to make it pass, refactor.

TDD MUST NOT be applied to:

- Frontend components (UI layer)
- API endpoint handlers (HTTP routing layer)

**Rationale**: Service-layer logic is the core of correctness guarantees;
endpoints and UI are better validated via integration/e2e testing outside this
project's test suite.

### III. No Remote API Calls in Tests

Tests MUST NOT call remote APIs (LLMs, external HTTP services, third-party
SaaS). All external dependencies MUST be mocked or stubbed. If a test's only
meaningful assertion requires a live LLM response, that test MUST NOT be
written.

**Rationale**: Tests that call remote APIs are slow, flaky, cost money, and
cannot run offline. A test that cannot be meaningfully mocked adds no value.

### IV. Simplicity First (YAGNI)

This project is a demo/prototype. Code MUST be the simplest implementation that
satisfies the current requirement. New features MUST NOT be added without
explicit user confirmation. Abstractions, helpers, and utilities MUST NOT be
created for hypothetical future use.

Complexity violations MUST be justified in the plan's Complexity Tracking table
before implementation begins.

**Rationale**: Prototype complexity compounds fast. Every unrequested abstraction
is a future maintenance burden.

### V. Strong Typing — No Plain Dicts, No `Any`

All function arguments and return values MUST be typed using one of:

- Pydantic models (for data validated at runtime boundaries)
- `TypedDict` (for internal structured data)
- Stdlib dataclasses or named tuples where appropriate

Plain `dict` MUST NOT be used as a function argument or return type.
The `Any` type MUST NOT be used. `mypy` MUST pass with no errors on all
backend code.

**Rationale**: Strong types catch entire classes of bugs at development time
and serve as living documentation.

### VI. Functional Style over OOP

Code MUST prefer pure functions, module-level functions, and data classes
over class hierarchies, inheritance, and stateful objects. Classes MUST only
be introduced when state management genuinely requires encapsulation (e.g.,
a connection pool). One-off utility classes MUST NOT be created.

**Rationale**: Functional code is easier to test, reason about, and compose
without hidden side effects.

### VII. Ruff Linter — Zero Violations

All Python files MUST pass `ruff check` with zero errors before being saved
or committed. Auto-fixable violations SHOULD be fixed with `ruff check --fix`.
`ruff format` MUST also be applied.

**Rationale**: Consistent style and lint cleanliness are enforced by tooling,
not code review, freeing review bandwidth for logic.

### VIII. Containerised Infrastructure

PostgreSQL MUST run in a Docker container. The application server(s) MUST also
run in Docker containers. `docker-compose` or equivalent MUST be provided to
bring up the full stack locally. No service MUST require a local native install
beyond Docker and `uv`.

**Rationale**: Container parity between developer machines eliminates
"works on my machine" failures and makes the demo reproducible.

### IX. Comprehensive Logging — No Silent Exceptions

Every `except` block MUST log the exception at `ERROR` level (or higher) before
taking any recovery action. Silent `except: pass` patterns are FORBIDDEN.
All significant service operations (start, success, failure) MUST emit
structured log entries. The `logging` stdlib module MUST be configured at
application entry points.

**Rationale**: Invisible failures in a prototype are indistinguishable from
correct behaviour; logs are the primary debugging tool.

## Technology Stack

- **Language**: Python 3.12+
- **Package manager**: uv
- **Agent framework**: Google ADK (`google-adk`), running locally
- **Agent architecture**: Root coordinator + specialist sub-agents (Drafter,
  Researcher) + SequentialAgent for ripple-effect pipeline — see `docs/agents.md`
- **Web framework**: FastAPI
- **Frontend**: HTMX — JavaScript MUST be minimised; custom JS MUST NOT be
  written when an HTMX attribute achieves the same result
- **Database**: PostgreSQL (Docker container)
- **ORM / DB access**: SQLAlchemy 2.x or raw `asyncpg` — confirm per feature
- **Validation**: Pydantic v2
- **Type checking**: mypy (strict mode)
- **Linting / formatting**: ruff
- **Testing**: pytest
- **Containerisation**: Docker + docker-compose

## Development Workflow

1. Confirm the feature scope with the user before writing any code.
2. For backend services: write failing tests first (TDD).
3. Run `ruff check --fix && ruff format` before every save.
4. Run `mypy` after implementation; zero errors required.
5. Run `pytest` to confirm all tests pass.
6. Commit using Conventional Commits format.

**Agent work**: All ADK agent definitions MUST follow the architecture in
`docs/agents.md`. New agent types MUST NOT be introduced without explicit user
confirmation (Principle IV).

**Feature gate**: No new feature work begins without an updated spec and explicit
user approval of scope.

**Implementation Strategy**
When executing /speckit.implement, dispatch tasks marked [P] as parallel
sub-agents. Each sub-agent should own distinct files with no overlap.
Sequential tasks must complete before dependent parallel batches begin.

## Governance

This constitution supersedes all other project conventions. Amendments require:

1. A clear statement of the principle being changed and why.
2. A version bump following semantic versioning (MAJOR / MINOR / PATCH).
3. Updated `LAST_AMENDED_DATE`.

All implementation plans MUST include a Constitution Check section that
explicitly gates each principle before Phase 0 research begins.

**Version**: 1.2.0 | **Ratified**: 2026-03-13 | **Last Amended**: 2026-03-13
