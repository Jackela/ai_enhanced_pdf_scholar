# Test Infrastructure Specification

## ADDED Requirements

### Requirement: Backend Test Module Imports
The test infrastructure SHALL support importing backend modules without runtime dependency failures.

Backend test files MUST be able to import from `backend.api` and its submodules without encountering `ModuleNotFoundError` for transitive dependencies that are available in the production environment but stubbed in tests.

#### Scenario: Test imports backend.api.auth modules
- **GIVEN** PyMuPDF is stubbed in test configuration
- **WHEN** a test file imports `from backend.api.auth.dependencies import AuthenticationRequired`
- **THEN** the import succeeds without ModuleNotFoundError
- **AND** the test can proceed to execute

#### Scenario: Lazy import prevents test-time failures
- **GIVEN** `src/services/document_preview_service.py` uses PyMuPDF (fitz module)
- **WHEN** a module imports document_preview_service indirectly
- **THEN** the fitz import is deferred until actual usage
- **AND** tests that don't use PDF preview functionality can import the service

### Requirement: Test Dependency Isolation
Services with optional runtime dependencies SHALL use lazy imports to prevent test import failures.

When a service depends on external libraries that may not be available in all test contexts (e.g., PyMuPDF for PDF processing), the import MUST be deferred to the point of actual usage rather than module load time.

#### Scenario: Service with optional PDF dependency
- **GIVEN** `document_preview_service.py` has methods that use PyMuPDF
- **WHEN** the module is imported
- **THEN** the PyMuPDF import happens inside methods that use it
- **AND** the service class can be instantiated without PyMuPDF being available
- **AND** only methods using PDF functionality will raise ImportError if PyMuPDF is missing

#### Scenario: Test suite discovers all test files
- **GIVEN** all test files are using proper lazy import patterns
- **WHEN** pytest runs test collection
- **THEN** all test files are successfully imported
- **AND** zero ModuleNotFoundError exceptions occur during collection
- **AND** tests can run with appropriate dependency stubs

### Requirement: Frontend TypeScript Type Safety
The frontend build system SHALL enforce TypeScript type safety with zero compilation errors.

All TypeScript interfaces used in WebSocket message handling MUST have complete type definitions for all accessed properties.

#### Scenario: WebSocketMessage interface completeness
- **GIVEN** metricsWebSocket.ts handles various message types
- **WHEN** code accesses properties like `message`, `health_summary`, `alerts`, `subscribed_metrics`, or `error`
- **THEN** the WebSocketMessage interface defines these properties as optional fields
- **AND** TypeScript compilation succeeds without errors

#### Scenario: SystemMetrics type availability
- **GIVEN** code uses `SystemMetrics` type annotation
- **WHEN** TypeScript compiler processes metricsWebSocket.ts
- **THEN** the SystemMetrics type is either defined in the file or imported from a type definition file
- **AND** no "Cannot find name 'SystemMetrics'" error occurs

#### Scenario: Frontend production build
- **GIVEN** all TypeScript errors are resolved
- **WHEN** `npm run build` is executed
- **THEN** the build completes successfully
- **AND** production-ready JavaScript and CSS bundles are generated
- **AND** no type errors block the build process
