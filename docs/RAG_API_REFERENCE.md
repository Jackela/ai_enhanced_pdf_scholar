# RAG API Reference

**Last Updated**: 2025-11-18
**Purpose**: Verified API signatures for RAG modules to prevent test signature mismatches

---

## Overview

This document contains the **actual** method signatures extracted from RAG module source code. Always refer to this document before writing tests to ensure correct API usage.

**Key Testing Notes**:
- Most RAG components support `test_mode=True` to avoid external API dependencies
- Use mocked repositories (DocumentRepository, VectorIndexRepository) in tests
- Mock the RAGFileManager for filesystem operations
- Never call real Gemini API or LlamaIndex in unit tests

---

## 1. RAGQueryEngine (`src/services/rag/query_engine.py`)

### Purpose
Handles vector index loading and query execution.

### Constructor

```python
def __init__(
    self,
    document_repo: DocumentRepository,
    vector_repo: VectorIndexRepository,
    file_manager: RAGFileManager,
    test_mode: bool = False,
)
```

**Parameters**:
- `document_repo`: Document repository instance
- `vector_repo`: Vector index repository instance
- `file_manager`: RAG file manager instance
- `test_mode`: If True, use mock indexes for testing (avoids LlamaIndex initialization)

**Test Mode Behavior**:
- When `test_mode=True`, creates mock indexes that return test responses
- Mock query response format: `f"Test mode response for query: {query_text}"`

### Public Methods

#### load_index_for_document
```python
def load_index_for_document(self, document_id: int) -> bool
```
Load vector index for a specific document.

**Returns**: `True` if index loaded successfully
**Raises**: `IndexLoadError` if loading fails or index not found

**Error Conditions**:
- Document not found in database
- No vector index exists for document
- Index files missing or corrupted
- Index loading failed

#### query_document
```python
def query_document(self, query: str, document_id: int) -> str
```
Query a specific document using its vector index.

**Returns**: RAG response string
**Raises**: `QueryExecutionError` if query execution fails

**Behavior**:
- Auto-loads index if not currently loaded or different document
- Updates document access time on successful load

#### query_current_document
```python
def query_current_document(self, query: str) -> str
```
Query the currently loaded document.

**Returns**: RAG response string
**Raises**: `QueryExecutionError` if no document is loaded or query fails

#### get_current_document_info
```python
def get_current_document_info(self) -> dict[str, Any]
```
Get information about the currently loaded document and index.

**Returns**: Dictionary with keys:
- `current_document_id`: int | None
- `has_loaded_index`: bool
- `current_pdf_path`: str | None
- `vector_index_info`: dict | None (with `index_id`, `index_path`, `chunk_count`, `created_at`)
- `test_mode`: bool

#### get_document_query_status
```python
def get_document_query_status(self, document_id: int) -> dict[str, Any]
```
Get query readiness status for a document.

**Returns**: Dictionary with keys:
- `document_id`: int
- `can_query`: bool
- `has_index`: bool
- `index_valid`: bool
- `index_path`: str | None
- `chunk_count`: int
- `created_at`: str | None (ISO format)
- `is_currently_loaded`: bool
- `error`: str | None

#### clear_current_index
```python
def clear_current_index(self) -> None
```
Clear the currently loaded index and reset state.

#### preload_index
```python
def preload_index(self, document_id: int) -> bool
```
Preload index for a document to improve query performance.

**Returns**: `True` if preloading successful, `False` otherwise (logs warning, doesn't raise)

#### get_query_statistics
```python
def get_query_statistics(self) -> dict[str, Any]
```
Get statistics about the query engine.

**Returns**: Dictionary with keys:
- `service_name`: "RAGQueryEngine"
- `test_mode`: bool
- `current_state`: dict (from `get_current_document_info()`)
- `storage_stats`: dict (from file_manager)

### Exceptions

- `RAGQueryError`: Base exception for RAG query errors
- `IndexLoadError(RAGQueryError)`: Exception raised when index loading fails
- `QueryExecutionError(RAGQueryError)`: Exception raised when query execution fails

---

## 2. RAGRecoveryService (`src/services/rag/recovery_service.py`)

### Purpose
Handles corruption detection, repair, and system diagnostics.

### Constructor

```python
def __init__(
    self,
    vector_repo: VectorIndexRepository,
    file_manager: RAGFileManager,
    health_checker: HealthChecker | None = None,
)
```

**Parameters**:
- `vector_repo`: Vector index repository instance
- `file_manager`: RAG file manager instance
- `health_checker`: Optional health checker instance (creates default if None)

**Initialization**:
- Sets up 3 default health checks: `vector_storage`, `database_connection`, `system_resources`
- Creates `RecoveryOrchestrator` instance

### Public Methods

#### analyze_index_corruption
```python
def analyze_index_corruption(self, vector_index: VectorIndexModel) -> dict[str, Any]
```
Analyze vector index for corruption and determine severity.

**Returns**: Dictionary with keys:
- `index_id`: int
- `document_id`: int
- `corruption_detected`: bool
- `corruption_types`: list[str] (e.g., `["missing_files", "corrupted_files"]`)
- `corruption_severity`: str (`"none"`, `"light"`, `"moderate"`, `"critical"`)
- `missing_files`: list[str]
- `corrupted_files`: list[str]
- `file_size_issues`: list[str]
- `metadata_issues`: list[str]
- `recommendations`: list[str]

**Raises**: `CorruptionDetectionError` if analysis fails

**Severity Levels**:
- **Critical**: Missing directory, missing core files, corrupted vector_store
- **Moderate**: Corrupted non-core files, empty files
- **Light**: Metadata issues only

#### recover_corrupted_index
```python
def recover_corrupted_index(
    self,
    vector_index: VectorIndexModel,
    force_rebuild: bool = False,
    rebuild_callback: Callable | None = None,
) -> dict[str, Any]
```
Recover a corrupted vector index with comprehensive repair strategies.

**Parameters**:
- `vector_index`: Vector index model to recover
- `force_rebuild`: If True, skip repair attempts and force rebuild
- `rebuild_callback`: Optional callback function for rebuilding index (signature: `Callable[[VectorIndexModel], bool]`)

**Returns**: Dictionary with keys:
- `index_id`: int
- `document_id`: int
- `recovery_successful`: bool
- `corruption_analysis`: dict
- `repair_actions`: list[str] (e.g., `["full_rebuild"]`, `["partial_repair", "fallback_rebuild"]`)
- `recovery_duration_ms`: int
- `error`: str | None

**Raises**: `RecoveryOperationError` if recovery fails

**Recovery Strategies**:
- **Critical/Force**: Full rebuild via callback
- **Moderate**: Partial repair → fallback to rebuild if fails
- **Light**: Verification repair (metadata updates)

#### perform_system_health_check
```python
def perform_system_health_check(self) -> dict[str, Any]
```
Perform comprehensive system health check and diagnosis.

**Returns**: Dictionary with keys:
- `check_start_time`: str (ISO format)
- `check_end_time`: str (ISO format)
- `check_duration_ms`: int
- `health_status`: dict[str, bool] (health check results)
- `corrupted_indexes`: list[dict]
- `orphaned_resources`: dict
- `cleanup_actions`: list[str]
- `recommendations`: list[str]
- `overall_status`: str (`"healthy"`, `"degraded"`, `"critical"`)

#### identify_corrupted_indexes
```python
def identify_corrupted_indexes(self) -> list[dict[str, Any]]
```
Identify all corrupted indexes in the system.

**Returns**: List of dictionaries with keys:
- `index_id`: int
- `document_id`: int
- `corruption_severity`: str
- `corruption_types`: list[str]
- `recommendations`: list[str]

#### cleanup_orphaned_resources
```python
def cleanup_orphaned_resources(self) -> int
```
Clean up orphaned resources including database records and filesystem directories.

**Returns**: Number of orphaned resources cleaned up (DB orphans + FS orphans)

#### get_recovery_metrics
```python
def get_recovery_metrics(self) -> dict[str, Any]
```
Get comprehensive recovery and diagnostic metrics.

**Returns**: Dictionary with keys:
- `service_name`: "RAGRecoveryService"
- `health_status`: dict[str, bool]
- `storage_stats`: dict
- `recovery_orchestrator_metrics`: dict
- `database_stats`: dict | `{"error": str}`

### Exceptions

- `RAGRecoveryError`: Base exception for RAG recovery errors
- `CorruptionDetectionError(RAGRecoveryError)`: Exception raised when corruption detection fails
- `RecoveryOperationError(RAGRecoveryError)`: Exception raised when recovery operations fail

---

## 3. RAGCoordinator (`src/services/rag/coordinator.py`)

### Purpose
Orchestrates interactions between focused RAG services.

### Constructor

```python
def __init__(
    self,
    api_key: str,
    db_connection: DatabaseConnection,
    vector_storage_dir: str = "vector_indexes",
    test_mode: bool = False,
)
```

**Parameters**:
- `api_key`: Google Gemini API key
- `db_connection`: Database connection instance
- `vector_storage_dir`: Directory for storing vector indexes (default: `"vector_indexes"`)
- `test_mode`: If True, use test mode for all services

**CRITICAL NOTES**:
- **NO** `test_db: bool` parameter (previous tests used wrong signature)
- **NO** `document_repo` or `vector_repo` parameters (created internally)
- Parameter order matters: `api_key`, `db_connection`, `vector_storage_dir`, `test_mode`

**Initialization**:
- Creates `DocumentRepository(db_connection)` internally
- Creates `VectorIndexRepository(db_connection)` internally
- Initializes `RAGFileManager`, `RAGIndexBuilder`, `RAGQueryEngine`, `RAGRecoveryService`
- Creates `TransactionManager` and `HealthChecker`

### Public Methods

#### build_index_from_document
```python
def build_index_from_document(
    self, document: DocumentModel, overwrite: bool = False
) -> VectorIndexModel
```
Build vector index from a document model with comprehensive error recovery.

**Returns**: Created vector index model
**Raises**: `RAGCoordinatorError` if index building fails

**Error Conditions**:
- Index already exists and `overwrite=False`
- Build validation fails (missing file, invalid requirements)
- Index building fails

#### load_index_for_document
```python
def load_index_for_document(self, document_id: int) -> bool
```
Load vector index for a specific document (delegates to query_engine).

**Returns**: `True` if index loaded successfully
**Raises**: `RAGCoordinatorError` if loading fails

#### query_document
```python
def query_document(self, query: str, document_id: int) -> str
```
Query a specific document using its vector index (delegates to query_engine).

**Returns**: RAG response string
**Raises**: `RAGCoordinatorError` if query fails

#### get_document_index_status
```python
def get_document_index_status(self, document_id: int) -> dict[str, Any]
```
Get the indexing status for a document (delegates to query_engine).

**Returns**: Dictionary (same as `query_engine.get_document_query_status()`)

#### rebuild_index
```python
def rebuild_index(self, document_id: int) -> VectorIndexModel
```
Rebuild vector index for a document.

**Returns**: New vector index model
**Raises**: `RAGCoordinatorError` if rebuild fails

**Behavior**:
- Deletes existing index (files + DB record)
- Calls `build_index_from_document()` with `overwrite=True`

#### recover_corrupted_index
```python
def recover_corrupted_index(
    self, document_id: int, force_rebuild: bool = False
) -> dict[str, Any]
```
Recover a corrupted vector index with comprehensive diagnostics and repair.

**Returns**: Dictionary with recovery results (same as `recovery_service.recover_corrupted_index()`)
**Raises**: `RAGCoordinatorError` if recovery fails

**Behavior**:
- Provides rebuild callback to recovery service
- Callback calls `self.rebuild_index(document_id)`

#### cleanup_orphaned_indexes
```python
def cleanup_orphaned_indexes(self) -> int
```
Clean up orphaned vector indexes (delegates to recovery_service).

**Returns**: Number of orphaned indexes cleaned up
**Raises**: `RAGCoordinatorError` if cleanup fails

#### perform_system_recovery_check
```python
def perform_system_recovery_check(self) -> dict[str, Any]
```
Perform comprehensive system recovery check and cleanup (delegates to recovery_service).

**Returns**: Dictionary with recovery check results
**Raises**: `RAGCoordinatorError` if system check fails

#### get_enhanced_cache_info
```python
def get_enhanced_cache_info(self) -> dict[str, Any]
```
Get comprehensive cache and service information.

**Returns**: Dictionary with keys:
- `coordinator_info`: dict (`test_mode`, `vector_storage_dir`, `current_document`)
- `service_stats`: dict (`file_manager`, `index_builder`, `query_engine`, `recovery_service`)
- `database_stats`: dict | `{"error": str}`

#### get_service_health_status
```python
def get_service_health_status(self) -> dict[str, Any]
```
Get health status of all coordinated services.

**Returns**: Dictionary with keys:
- `overall_healthy`: bool
- `services`: dict (`file_manager`, `database`, `recovery_service`)
- `recommendations`: list[str]

#### preload_document_index
```python
def preload_document_index(self, document_id: int) -> bool
```
Preload index for improved query performance (delegates to query_engine).

**Returns**: `True` if preloading successful

#### clear_current_index
```python
def clear_current_index(self) -> None
```
Clear the currently loaded index state (delegates to query_engine).

#### get_current_document_info
```python
def get_current_document_info(self) -> dict[str, Any]
```
Get information about the currently loaded document (delegates to query_engine).

### Legacy Compatibility Methods

#### query
```python
def query(self, query_text: str) -> str
```
Legacy method: Query the current vector index.

**NOTE**: This is for backward compatibility. Calls `query_engine.query_current_document()`.

**Returns**: RAG response string
**Raises**: `RAGCoordinatorError` if no index is loaded or query fails

#### get_cache_info
```python
def get_cache_info(self) -> dict[str, Any]
```
Legacy method: Get basic cache information.

**Returns**: Dictionary with keys:
- `has_current_index`: bool
- `current_pdf_path`: str | None
- `current_document_id`: int | None
- `test_mode`: bool
- `vector_indexes_count`: int

### Exceptions

- `RAGCoordinatorError`: Base exception for RAG coordinator errors

---

## 4. RAGIndexBuilder (`src/services/rag/index_builder.py`)

### Purpose
Handles PDF processing and vector index creation.

### Constructor

```python
def __init__(
    self, api_key: str, file_manager: RAGFileManager, test_mode: bool = False
)
```

**Parameters**:
- `api_key`: Google Gemini API key
- `file_manager`: RAG file manager instance
- `test_mode`: If True, skip actual API initialization for testing

**Test Mode Behavior**:
- When `test_mode=True`, skips LlamaIndex initialization
- `build_index_from_pdf()` returns `True` immediately without actual processing

**Initialization**:
- Creates `ResourceCleanupManager` instance
- Configures retry and circuit breaker for API operations
- Initializes LlamaIndex components if not in test mode

### Public Methods

#### build_index_for_document
```python
def build_index_for_document(
    self, document: DocumentModel, overwrite: bool = False
) -> dict[str, Any]
```
Build complete vector index for a document with full error recovery.

**Returns**: Dictionary with keys:
- `document_id`: int
- `success`: bool
- `index_path`: str | None
- `index_hash`: str | None
- `chunk_count`: int
- `build_duration_ms`: int
- `error`: str | None

**Raises**: `RAGIndexBuilderError` if index building fails

**Behavior**:
- Calculates content hash for index uniqueness
- Builds index in temporary directory
- Copies to final location with verification
- Cleans up temporary files
- Emergency cleanup on failure

#### validate_build_requirements
```python
def validate_build_requirements(self, document: DocumentModel) -> dict[str, Any]
```
Validate that all requirements are met for building an index.

**Returns**: Dictionary with keys:
- `valid`: bool
- `issues`: list[str] (blocking issues)
- `warnings`: list[str] (non-blocking warnings)

**Validation Checks**:
- Document file path exists
- File is not empty
- File size < 100MB (warning if larger)
- Vector storage directory is accessible
- API key is configured (if not test mode)

#### get_build_statistics
```python
def get_build_statistics(self) -> dict[str, Any]
```
Get statistics about the index building service.

**Returns**: Dictionary with keys:
- `service_name`: "RAGIndexBuilder"
- `test_mode`: bool
- `storage_stats`: dict
- `config`: dict (`api_retry_attempts`, `circuit_breaker_threshold`, `recovery_timeout`)

### Internal Methods (for reference)

#### build_index_from_pdf (internal)
```python
def build_index_from_pdf(self, pdf_path: str, temp_dir: str) -> bool
```
Build vector index from PDF file using LlamaIndex (used internally by `build_index_for_document`).

**Returns**: `True` if index was built successfully
**Raises**: `IndexCreationError` if index building fails

### Exceptions

- `RAGIndexBuilderError`: Base exception for RAG index builder errors
- `IndexCreationError(RAGIndexBuilderError)`: Exception raised when index creation fails

---

## 5. ChunkingStrategies (`src/services/rag/chunking_strategies.py`)

### Purpose
Provides various chunking strategies for document processing.

### ChunkConfig (Dataclass)

```python
@dataclass
class ChunkConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 200
    separator: str = "\n\n"
    min_chunk_size: int = 100
    max_chunk_size: int = 2000
```

### Base Class

#### ChunkingStrategy
```python
class ChunkingStrategy:
    def __init__(self, config: ChunkConfig | None = None)
    def chunk(self, text: str) -> list[dict[str, Any]]  # Abstract
```

All strategies return list of dictionaries with at minimum:
- `text`: str (chunk text)
- `metadata`: dict (`type`: str, `size`: int)

### Concrete Strategies

#### 1. SentenceChunker
```python
class SentenceChunker(ChunkingStrategy):
    def chunk(self, text: str) -> list[dict[str, Any]]
```
Chunks documents by sentences.

**Returns**: List of dicts with:
- `text`: str
- `metadata`: `{"type": "sentence", "size": int}`

#### 2. ParagraphChunker
```python
class ParagraphChunker(ChunkingStrategy):
    def chunk(self, text: str) -> list[dict[str, Any]]
```
Chunks documents by paragraphs.

**Returns**: List of dicts with:
- `text`: str
- `metadata`: `{"type": "paragraph" | "paragraph_split", "size": int}`

**Behavior**: Splits large paragraphs > `max_chunk_size` into smaller chunks.

#### 3. SemanticChunker
```python
class SemanticChunker(ChunkingStrategy):
    def chunk(self, text: str) -> list[dict[str, Any]]
```
Chunks documents based on semantic similarity (simplified - detects sections by capitalization).

**Returns**: List of dicts with:
- `text`: str
- `metadata`: `{"type": "semantic", "size": int}`

#### 4. HybridChunker
```python
class HybridChunker(ChunkingStrategy):
    def chunk(self, text: str) -> list[dict[str, Any]]
```
Combines multiple chunking strategies (tries semantic → paragraph → sentence).

**Returns**: List of dicts with:
- `text`: str
- `metadata`: `{"type": "semantic" | "paragraph" | "sentence" | "fallback", "size": int}`

**Behavior**: Falls back to next strategy if current fails, final fallback is simple splitting.

#### 5. AdaptiveChunking
```python
class AdaptiveChunking(ChunkingStrategy):
    def chunk(self, text: str) -> list[dict[str, Any]]
```
Adaptive chunking strategy that dynamically adjusts chunk size based on content complexity.

**Returns**: List of dicts with:
- `text`: str
- `start_position`: int
- `end_position`: int
- `chunk_size`: int
- `complexity_score`: float (0-1)
- `adaptive_size`: int
- `metadata`: `{"type": "adaptive", "size": int}`

**Complexity Calculation** (0-1 scale):
- Sentence density × 0.3
- Average word length (normalized) × 0.3
- Technical density (acronyms + numbers) × 0.4

**Adaptive Sizing**:
- High complexity (>0.7): `base_chunk_size * 0.6`
- Medium complexity (0.4-0.7): `base_chunk_size * 0.8`
- Low complexity (<0.4): `base_chunk_size * 1.2`

#### 6. CitationAwareChunking
```python
class CitationAwareChunking(ChunkingStrategy):
    def chunk(self, text: str) -> list[dict[str, Any]]
```
Citation-aware chunking that preserves citation contexts and reference integrity.

**Returns**: List of dicts with:
- `text`: str
- `start_position`: int
- `end_position`: int
- `chunk_size`: int
- `citations`: list[dict] (each with `text`, `type`, `start`, `end`)
- `citation_count`: int
- `has_figures`: bool
- `has_equations`: bool
- `metadata`: `{"type": "citation_aware", "size": int, "citation_density": float}`

**Citation Patterns Detected**:
- Numeric: `[1]`, `[1-3]`, `[1, 2, 3]`
- Author-year: `(Smith, 2020)`, `(Smith et al., 2020)`
- Figures/Tables: `Figure 1`, `Table 2`, `Equation 3`

---

## Testing Guidelines

### Creating Test Instances

#### RAGQueryEngine Test Setup
```python
from unittest.mock import Mock
from src.services.rag.query_engine import RAGQueryEngine

# Create mocks
mock_doc_repo = Mock(spec=DocumentRepository)
mock_vector_repo = Mock(spec=VectorIndexRepository)
mock_file_manager = Mock(spec=RAGFileManager)

# Create engine in test mode
query_engine = RAGQueryEngine(
    document_repo=mock_doc_repo,
    vector_repo=mock_vector_repo,
    file_manager=mock_file_manager,
    test_mode=True  # CRITICAL: Avoids LlamaIndex initialization
)
```

#### RAGCoordinator Test Setup
```python
from unittest.mock import Mock
from src.database.connection import DatabaseConnection
from src.services.rag.coordinator import RAGCoordinator

# Create DB mock
db_mock = Mock(spec=DatabaseConnection)

# Create coordinator with CORRECT signature
coordinator = RAGCoordinator(
    api_key="test-api-key",
    db_connection=db_mock,
    vector_storage_dir="test_indexes",
    test_mode=True
)
```

### Common Test Patterns

#### Testing Error Paths
```python
# Test IndexLoadError when document not found
mock_doc_repo.find_by_id.return_value = None
with pytest.raises(IndexLoadError, match="Document not found"):
    query_engine.load_index_for_document(999)
```

#### Testing Mock Responses in Test Mode
```python
# In test_mode, query returns mock response
response = query_engine._execute_query("test query")
assert response == "Test mode response for query: test query"
```

### Coverage Priority by Complexity

| Module | Lines | Current Coverage | Test Priority | Estimated Tests |
|--------|-------|------------------|---------------|-----------------|
| query_engine.py | 427 | 0% | **High** | 20 |
| recovery_service.py | 648 | 10% | **High** | 18 |
| coordinator.py | 503 | 15% | **High** | 15 |
| index_builder.py | 420 | 0% | **Medium** | 12 |
| chunking_strategies.py | 415 | 25% | **Medium** | 20 |

**Total Estimated**: ~85 tests for RAG modules

---

## Version History

- **2025-11-18**: Initial creation with verified signatures from source code
- All signatures verified against actual implementation
- Test mode behavior documented for all components
- Common pitfalls and correct usage patterns added
