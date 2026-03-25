# Stage 1: Build JS bundle
FROM node:22-slim AS js-builder
WORKDIR /build
COPY documentLM/package.json documentLM/package-lock.json ./
RUN npm ci --silent
COPY documentLM/static/ static/
RUN npx esbuild static/editor.js --bundle --outfile=static/editor.bundle.js --format=iife --minify

# Stage 2: Python runtime
FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY documentLM/pyproject.toml documentLM/uv.lock documentLM/README.md ./
COPY documentLM/src/ src/
COPY documentLM/static/ static/
COPY --from=js-builder /build/static/editor.bundle.js static/editor.bundle.js
COPY documentLM/alembic.ini ./
COPY documentLM/migrations/ migrations/
COPY nlp_utils/ /nlp_utils/

RUN uv sync --no-dev

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn writer.main:app --host 0.0.0.0 --port 8000"]
