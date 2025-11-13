## ADDED Requirements

### Requirement: Documents API MUST expose preview and thumbnail endpoints
Clients SHALL retrieve lightweight previews of managed documents through dedicated endpoints that enforce auth, limits, and caching.

#### Scenario: Stream specific page preview
- **GIVEN** a document exists and the caller is authorized
- **WHEN** they call `GET /api/documents/{id}/preview?page=2&width=600`
- **THEN** the API returns a `200 OK` response with `image/png` body representing page 2, constrained to the configured max width
- **AND** the response includes `Cache-Control: private` plus metadata headers (page, width, document id)
- **AND** requests for unsupported page numbers return `404` or `400` with a descriptive message

#### Scenario: Return cached thumbnail quickly
- **GIVEN** previews are enabled and the document is a supported type
- **WHEN** the client calls `GET /api/documents/{id}/thumbnail`
- **THEN** the API serves a cached first-page image (generating it on first request) within the configured TTL, respecting rate limits
- **AND** if previews are disabled globally, the endpoint responds with `503` or `404` and logs the reason
- **AND** access control errors surface as `401/403` without leaking file paths
