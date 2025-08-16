# API Design & Specification

This document provides a simplified specification for the core API endpoints of the AI Enhanced PDF Scholar platform. It is intended to demonstrate API design principles and define the contract for frontend-backend communication.

---

## Core Endpoints

### 1. Document Upload

This endpoint handles the upload of a new PDF document. The request must be `multipart/form-data`.

- **Endpoint:** `POST /api/documents/upload`
- **Description:** Uploads a PDF file, processes it, and creates a corresponding document record in the system.
- **Authentication:** Required (Bearer Token).

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/documents/upload` | Upload a new document. |

**Request:** `multipart/form-data`
- `file`: The PDF file to be uploaded.
- `title` (optional): A title for the document. If not provided, the system will attempt to extract it from the PDF metadata.

**Responses:**

| Status Code | Reason | Response Body |
| :--- | :--- | :--- |
| `201 Created` | Document uploaded and processed successfully. | `{ "id": "doc_123", "title": "The Title of the Paper", "status": "processed" }` |
| `400 Bad Request` | No file provided or file type is not supported. | `{ "detail": "Invalid file format. Only PDF is supported." }` |
| `401 Unauthorized` | Invalid or missing authentication token. | `{ "detail": "Authentication credentials were not provided." }` |
| `413 Payload Too Large` | The uploaded file exceeds the size limit. | `{ "detail": "File size exceeds the 100MB limit." }` |

---

### 2. RAG Query

This endpoint handles a user's question about a specific document.

- **Endpoint:** `POST /api/rag/query`
- **Description:** Takes a user's query and a document ID, retrieves relevant context from the document, and returns an AI-generated answer.
- **Authentication:** Required (Bearer Token).

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/rag/query` | Ask a question about a specified document. |

**Request Body:** `application/json`
```json
{
  "document_id": "doc_123",
  "query": "What were the key findings of this study?"
}
```

**Responses:**

| Status Code | Reason | Response Body |
| :--- | :--- | :--- |
| `200 OK` | Query processed successfully and answer generated. | `{ "answer": "The key findings were...", "sources": [ { "page": 5, "text": "..." }, { "page": 12, "text": "..." } ] }` |
| `400 Bad Request` | The request body is missing required fields. | `{ "detail": "Fields 'document_id' and 'query' are required." }` |
| `401 Unauthorized` | Invalid or missing authentication token. | `{ "detail": "Authentication credentials were not provided." }` |
| `404 Not Found` | The specified `document_id` does not exist. | `{ "detail": "Document with id 'doc_123' not found." }` |
| `503 Service Unavailable` | The backend AI service (e.g., Gemini) is unavailable. | `{ "detail": "The AI service is currently unavailable. Please try again later." }` |
