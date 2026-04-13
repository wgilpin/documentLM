# Build context: ~/projects/  (one level above the workspace root)
# Run with: docker compose up --build  (from document-projects/)

# Stage 1: Build JS bundle
FROM node:22-slim AS js-builder
WORKDIR /build
COPY document-projects/documentLM/package.json document-projects/documentLM/package-lock.json ./
RUN npm ci --silent
COPY document-projects/documentLM/static/ static/
RUN npx esbuild static/editor.js --bundle --outfile=static/editor.bundle.js --format=iife --minify

# Stage 2: Python runtime
FROM python:3.13-slim

# Mirror the local workspace layout so uv path sources resolve identically
WORKDIR /projects/document-projects

RUN pip install uv

# Workspace root
COPY document-projects/pyproject.toml document-projects/uv.lock ./

# documentLM-core (workspace member)
COPY document-projects/documentLM-core/pyproject.toml document-projects/documentLM-core/README.md documentLM-core/
COPY document-projects/documentLM-core/src/ documentLM-core/src/

# nlp_utils (path dep: ../nlp_utils relative to workspace root)
COPY nlp_utils/pyproject.toml nlp_utils/README.md /projects/nlp_utils/
COPY nlp_utils/src/ /projects/nlp_utils/src/

# documentLM app
COPY document-projects/documentLM/pyproject.toml document-projects/documentLM/README.md documentLM/
COPY document-projects/documentLM/src/ documentLM/src/
COPY document-projects/documentLM/static/ documentLM/static/
COPY --from=js-builder /build/static/editor.bundle.js documentLM/static/editor.bundle.js
COPY document-projects/documentLM/alembic.ini documentLM/alembic.ini
COPY document-projects/documentLM/migrations/ documentLM/migrations/

RUN uv sync --no-dev

# Run migrations and start the app from the documentLM subdirectory
WORKDIR /projects/document-projects/documentLM
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn writer.main:app --host 0.0.0.0 --port 8000"]
