# Quickstart: Vector RAG for Document Sources

**Branch**: `005-vector-rag-sources`

---

## Prerequisites

- Docker Desktop running
- `uv` installed
- `.env` file present (copy `.env.example` if needed)

---

## Setup

### 1. Add dependency

```bash
uv add chromadb
```

### 2. Configure ChromaDB path (optional)

Add to `.env` (defaults to `./data/chroma` if omitted):

```env
CHROMA_PATH=./data/chroma
```

### 3. Run the database migration

```bash
docker-compose up -d postgres
uv run alembic upgrade head
```

This adds `indexing_status` and `error_message` columns to the `sources` table.

### 4. Start the full stack

```bash
docker-compose up --build
```

---

## Verify the feature

### Upload a PDF and watch indexing

```bash
curl -X POST http://localhost:8000/api/sources/pdf \
  -F "document_id=<your-doc-id>" \
  -F "file=@/path/to/document.pdf"
# Returns: { "indexing_status": "pending", ... }
```

Wait a moment, then list sources to see the completed status:

```bash
curl "http://localhost:8000/api/sources/?document_id=<your-doc-id>"
# Returns: [{ "indexing_status": "completed", ... }]
```

### Ask the chat agent

Open the document in the browser and ask the chat agent a question that references content from the uploaded PDF. Confirm it answers correctly using source content.

---

## Running tests

```bash
uv run pytest tests/unit/test_vector_store.py
uv run pytest tests/integration/test_rag_pipeline.py
```

---

## ChromaDB data location

The vector store persists to `./data/chroma/` (relative to the project root). This directory is gitignored. To reset the vector store, delete this directory and re-upload sources.
