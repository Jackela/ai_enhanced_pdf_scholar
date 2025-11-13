# frontend Specification

## Purpose
TBD - created by archiving change integrate-preview-into-frontend. Update Purpose after archive.
## Requirements
### Requirement: Frontend MUST render backend-provided previews
The React client SHALL use `preview_url` and `thumbnail_url` when available.

#### Scenario: Thumbnails in library view
- **GIVEN** the document list API returns `thumbnail_url`
- **WHEN** the frontend renders the library grid/list
- **THEN** each row displays the thumbnail `<img>` fetched lazily with loading/error fallbacks, and hides the image when previews are disabled

#### Scenario: Modal preview per page
- **GIVEN** a user opens a document detail panel
- **WHEN** they click “Preview page N”
- **THEN** the client requests `/preview?page=N` with auth, shows the returned image, and surfaces errors (404/415/503) via toast/UI states
