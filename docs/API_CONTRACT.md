# API Contract

Authoritative envelope and route shapes used by the SPA and backend tests. All API URLs are rooted at `/api`; there are no parallel versions in the tree, so any breaking change to these routes must be coordinated between backend, frontend, and this document.

## Response Envelope

All endpoints return the same envelope:

```jsonc
{
  "success": true,
  "data": { /* resource-specific payload */ },
  "meta": {
    "timestamp": "2025-01-12T10:00:00Z",
    "version": "v2",
    "...": "resource metadata"
  },
  "errors": null
}
```

For paginated resources `meta` extends with `page`, `per_page`, `total`, `total_pages`, `has_next`, and `has_prev`.

## Document Routes (`/api/documents`)

### `GET /api/documents`
- Query params: `query`, `page`, `per_page`, `sort_by`, `sort_order`
- Response: `PaginatedResponse[DocumentData]`
- `DocumentData.file_path` is optional; clients **must** guard before using it.
- `meta.total` is driven by `COUNT(*)`, and pagination metadata reflects LIMIT/OFFSET.

Example:

```jsonc
{
  "success": true,
  "data": [
    {
      "id": 7,
      "title": "Doc.pdf",
      "file_path": "/Users/me/.ai_pdf_scholar/documents/abcd1234.pdf",
      "is_file_available": true,
      "_links": {
        "self": "/api/documents/7",
        "related": {
          "download": "/api/documents/7/download",
          "queries": "/api/documents/7/queries",
          "indexes": "/api/documents/7/indexes",
          "citations": "/api/documents/7/citations"
        }
      }
    }
  ],
  "meta": {
    "timestamp": "2025-01-12T10:00:00Z",
    "version": "v2",
    "page": 1,
    "per_page": 20,
    "total": 42,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  },
  "errors": null
}
```

### `GET /api/documents/{id}`
- Returns `DocumentResponse`.
- `data.file_path` may be `null` if the file was pruned; clients must guard before showing download buttons.

### `POST /api/documents`
- Multipart upload.
- Filenames are sanitized with `sanitize_upload_filename`, written to `_tmp_uploads/`, then imported.
- Unsupported media types → `415`.
- Oversized files (>50 MB) → `413`.

### `GET /api/documents/{id}/download`
- Streams the managed PDF.
- Download is allowed when the document's stored root (metadata `storage_root`) or the default documents directory contains the file.
- Traversal or missing files → `403/404`.

## Query Routes (`/api/queries`)

Until the real RAG implementation lands, queries are feature-gated.

- Env flag `ENABLE_RAG_SERVICES=1` must be set to enable placeholder behavior.
- Without the flag every `/api/queries` endpoint returns `501 Not Implemented`.
- With the flag the endpoints respond with the standard envelope (currently placeholder text + cache metadata).

Covered endpoints:
- `POST /queries/document/{id}`
- `POST /queries/multi-document`
- `DELETE /queries/cache/document/{id}`
- `GET /queries/cache/stats`

## Index Routes (`/api/indexes`)

Same feature flag (`ENABLE_RAG_SERVICES`) controls access.

- When disabled, all `/api/indexes` routes return `503 Service Unavailable`.
- When enabled they return the documented envelope, though build/rebuild results are placeholder success objects until the builder is wired in.

Covered endpoints:
- `GET /indexes/document/{id}`
- `POST /indexes/document/{id}/build`
- `POST /indexes/document/{id}/rebuild`
- `GET /indexes/{index_id}/verify`
- `POST /indexes/cleanup/orphaned`
- `GET /indexes/stats/storage`

## Contract Tests

Automated tests under `tests/backend` enforce this contract:
- `test_documents_api_contract.py` exercises the list/get envelopes and pagination metadata.
- `test_rag_feature_flags.py` verifies `/queries` responds with 501 and `/indexes` with 503 until `ENABLE_RAG_SERVICES` is set, and that placeholder responses resume once the flag is enabled.

Any change to these routes or envelopes **must** update this document and its tests.
