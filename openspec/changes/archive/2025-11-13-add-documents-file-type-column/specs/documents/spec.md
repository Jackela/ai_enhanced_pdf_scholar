## ADDED Requirements

### Requirement: Documents MUST persist canonical file type metadata
All document records SHALL store a normalized `file_type` column (e.g., `.pdf`) that is populated on ingest and exposed via the API.

#### Scenario: Persist file type on ingest
- **GIVEN** a document import completes
- **WHEN** the record is stored in the `documents` table
- **THEN** the `file_type` column is set based on the uploaded file's extension or MIME type
- **AND** existing rows are backfilled during migration so no document has a NULL `file_type`

#### Scenario: Expose file type in API responses
- **GIVEN** a client calls any `/api/documents` endpoint
- **WHEN** the response envelope describes a document
- **THEN** the payload includes `file_type` so UI and analytics consumers can filter by type
- **AND** metrics collection assumes the column exists when aggregating document-type counts
