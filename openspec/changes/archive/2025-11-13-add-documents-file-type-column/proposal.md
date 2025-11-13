## Why
- The metrics collector expects a `documents.file_type` column for document-type distribution metrics, but many environments do not have that column, causing warnings and skipping metrics.
- Document API responses need a reliable way to communicate the original MIME/type for filtering and analytics; lacking a canonical column leads to divergent metadata handling.
- Aligning the schema ensures uploads, migrations, and metrics remain consistent across SQLite dev and PostgreSQL prod deployments.

## What Changes
- Introduce a schema migration (`009_add_document_file_type.py`) that adds a nullable `file_type` column with sensible defaults (infer from metadata or file extension) and backfills existing rows.
- Update repositories/models (`DocumentModel`, `DocumentRepository`, API serializers) to populate and expose `file_type`.
- Extend ingestion/upload services to capture the detected MIME/extension during import, ensuring the column stays current.
- Refresh metrics collector logic/tests to rely on the column being present instead of treating it as optional.
- Document the new schema requirement in `PROJECT_DOCS.md`, `API_ENDPOINTS.md`, and relevant specs.

## Impact
- Metrics dashboards regain document-type breakdowns without warnings.
- Clients can filter/search by file type reliably, enabling UI enhancements and validation.
- Keeps SQLite/PostgreSQL schemas aligned, reducing drift between environments.
