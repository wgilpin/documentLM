# API Contracts: Sources (affected endpoints)

**Branch**: `005-vector-rag-sources` | **Date**: 2026-03-15

---

## Changed: `POST /api/sources/` — Upload a source

**Change**: Response now includes `indexing_status` and `error_message`. The endpoint returns immediately; indexing runs in the background.

### Response (200 OK)

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "source_type": "pdf | url | note",
  "title": "string",
  "content": "string",
  "url": "string | null",
  "created_at": "2026-03-15T12:00:00Z",
  "indexing_status": "pending",
  "error_message": null
}
```

**Guarantee**: `indexing_status` is always `"pending"` on the initial response. The status transitions to `"processing"` → `"completed"` or `"failed"` asynchronously.

---

## Changed: `POST /api/sources/pdf` — Upload a PDF source

Same change as above. Returns `indexing_status: "pending"` immediately.

---

## Changed: `GET /api/sources/?document_id={uuid}` — List sources

**Change**: Each source in the list now includes `indexing_status` and `error_message`.

### Response (200 OK)

```json
[
  {
    "id": "uuid",
    "document_id": "uuid",
    "source_type": "pdf",
    "title": "My Document.pdf",
    "content": "...",
    "url": null,
    "created_at": "2026-03-15T12:00:00Z",
    "indexing_status": "completed",
    "error_message": null
  }
]
```

---

## Changed: `DELETE /api/sources/{source_id}` — Delete a source

**Change**: Deletion now also removes all ChromaDB chunks associated with `source_id`. The response is unchanged.

### Response (204 No Content)

No body. The deletion is synchronous — both the relational record and the vector store entries are removed before returning.

---

## No Change: Chat / Drafter / Planner endpoints

The RAG retrieval is transparent to callers. Existing request/response shapes for `/api/chat/`, suggestions, and documents are unchanged.
