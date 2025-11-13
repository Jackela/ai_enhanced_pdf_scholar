## Tasks
- [x] Design migration strategy (column definition, default value, backfill plan, rollback)
- [x] Implement migration script under `src/database/migrations/versions/009_add_document_file_type.py`
- [x] Update ORM/data models, repositories, ingestion services, and API serializers to read/write `file_type`
- [x] Adjust metrics collector/test data to assume the column exists
- [x] Document schema change in relevant markdown/docs and specs
- [x] Run `openspec validate add-documents-file-type-column --strict`
