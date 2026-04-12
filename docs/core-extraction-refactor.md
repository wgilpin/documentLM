# Refactoring Plan: Extract `documentlm-core`

## 1. Package Initialization

* Create new directory structure: `documentlm-core/src/documentlm_core/`
* Create `pyproject.toml` for `documentlm-core`.
* Define dependencies: `sqlalchemy`, `google-genai`, `pypdf`, `beautifulsoup4`, `alembic`.
* Set up standard package files: `__init__.py`, `README.md`, `.gitignore`.

## 2. Database & Data Model Extraction

* Move `src/writer/core/database.py` (Base classes, session management) to `documentlm_core/core/database.py`.
* Move domain-agnostic enums from `src/writer/models/enums.py` to `documentlm_core/models/enums.py` (e.g., `SourceType`, `IndexingStatus`, `SessionStatus`).
* Move domain-agnostic ORM models from `src/writer/models/db.py` to `documentlm_core/models/db.py`:
  * `User`
  * `Source`
  * `ChatSession`
  * `ChatMessage`
* Create abstract base class or mixin for `Document` in core to enforce required fields (`id`, `title`, `created_at`), allowing downstream apps to extend it (e.g., adding `content` vs `chapters`).
* Migrate `alembic` base configurations to core, allowing downstream apps to import core models for migrations.

## 3. Service Layer Extraction (RAG & Indexing)

* Move `src/writer/services/vector_store.py` to `documentlm_core/services/vector_store.py`.
* Move `src/writer/services/indexer.py` to `documentlm_core/services/indexer.py`.
* Move `src/writer/services/content_fetcher.py` to `documentlm_core/services/content_fetcher.py`.
* Move `src/writer/services/auth_service.py` to `documentlm_core/services/auth_service.py`.
* Update internal imports within these files to reference `documentlm_core` namespaces.

## 4. Agent Orchestration Extraction

* Move reusable agent invocations from `src/writer/services/agent_service.py` to `documentlm_core/services/agent_service.py`.
* Extract `invoke_research_agent` directly.
* Refactor `invoke_drafter` and `invoke_planner` into base abstract functions that accept customizable instruction templates as arguments, rather than hardcoding the UI-specific output formats.
* Move `src/writer/agents/research_agent.py` to core.
* Leave `planner_agent.py` and `drafter_agent.py` in the downstream apps, inheriting or utilizing the core runner logic.

## 5. UI & Template Componentization

* Move domain-agnostic HTML partials to `documentlm_core/templates/partials/`:
  * `chat_message.html`
  * `chat_session_dropdown.html`
  * `sources.html`
  * `source_note_modal.html`
* Configure downstream Jinja environments to include the core package's template directory in the search path.

## 6. Downstream Integration (`documentlm` & New App)

* Install core package locally in both projects: `pip install -e ../documentlm-core`.
* Execute global find-and-replace in `documentlm` to update imports (e.g., `from writer.services.vector_store` -> `from documentlm_core.services.vector_store`).
* Update `documentlm` SQLAlchemy models to inherit from `documentlm_core.models.db` where applicable.
* Run existing `documentlm` test suite (`pytest`) to verify RAG, auth, and DB logic still function.
* Implement custom `SyllabusItem` and modified `Document` models in the new application, importing base classes from `documentlm-core`.
