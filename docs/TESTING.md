# Testing Guide for AI Enhanced PDF Scholar

**Last Updated**: 2025-11-18
**Purpose**: Comprehensive guide for writing tests in the project

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Organization](#test-organization)
3. [Stub Patterns](#stub-patterns)
4. [Fixture Usage](#fixture-usage)
5. [RAG Module Testing](#rag-module-testing)
6. [Auth Module Testing](#auth-module-testing)
7. [API Route Testing](#api-route-testing)
8. [Common Patterns](#common-patterns)
9. [Running Tests](#running-tests)
10. [Coverage Guidelines](#coverage-guidelines)

---

## Testing Philosophy

### Core Principles

1. **Test Isolation**: Each test should be independent and not rely on external dependencies
2. **Stub Over Mock**: Prefer lightweight stubs for repositories and services
3. **Fast Execution**: Tests should run quickly to support rapid development
4. **Clear Intent**: Test names should clearly describe what is being tested

### Test Levels

```
┌─────────────────────────────────────────────┐
│ Unit Tests (Fastest)                        │
│ - Test individual functions/classes         │
│ - Use stubs for all dependencies           │
│ - Location: tests/services/, tests/backend/│
├─────────────────────────────────────────────┤
│ Integration Tests (Medium)                  │
│ - Test component interactions              │
│ - Use real database (temporary)            │
│ - Location: tests/integration/             │
├─────────────────────────────────────────────┤
│ End-to-End Tests (Slowest)                  │
│ - Test complete workflows                  │
│ - Use real application instance            │
│ - Location: tests/e2e/ (planned)           │
└─────────────────────────────────────────────┘
```

---

## Test Organization

### Directory Structure

```
tests/
├── conftest.py              # Global fixtures and stubs (PyMuPDF, LlamaIndex)
├── backend/                 # Backend API tests
│   ├── test_auth_*.py      # Auth module tests
│   ├── test_documents_*.py # Document route tests
│   ├── test_middleware_*.py# Middleware tests
│   └── test_main_*.py      # Application lifecycle tests
├── services/                # Service layer tests
│   ├── test_rag_*.py       # RAG module tests
│   ├── test_document_*.py  # Document service tests
│   └── test_cache_*.py     # Cache service tests
├── repositories/            # Repository layer tests
│   └── test_*_repository.py
├── database/                # Database model tests
│   └── test_models.py
├── integration/             # Integration tests
│   └── test_real_*.py
└── README.md                # Testing overview
```

### File Naming Convention

- **Unit tests**: `test_{module_name}.py`
- **Integration tests**: `test_real_{feature}.py`
- **Comprehensive tests**: `test_{module}_comprehensive.py`
- **Stub tests**: `test_{module}_stubs.py`

---

## Stub Patterns

### Philosophy: Stubs vs. Mocks

**Stub (Preferred)**:
- Lightweight class with minimal implementation
- Returns predictable values
- Easier to understand and maintain
- Example: `_StubDocRepo`

**Mock (When Necessary)**:
- Use `unittest.mock.Mock` for complex interfaces
- Verify call counts and arguments
- Example: Mocking external APIs

### Repository Stub Pattern

```python
class _StubDocRepository:
    """Stub for DocumentRepository with in-memory storage."""

    def __init__(self, documents: list[DocumentModel] | None = None):
        self._documents = documents or []
        self._next_id = max((doc.id for doc in self._documents), default=0) + 1

    def find_by_id(self, document_id: int) -> DocumentModel | None:
        for doc in self._documents:
            if doc.id == document_id:
                return doc
        return None

    def find_all(self, limit: int = 100, offset: int = 0) -> list[DocumentModel]:
        return self._documents[offset : offset + limit]

    def create(self, document: DocumentModel) -> DocumentModel:
        document.id = self._next_id
        self._next_id += 1
        self._documents.append(document)
        return document

    def update(self, document: DocumentModel) -> DocumentModel:
        for idx, doc in enumerate(self._documents):
            if doc.id == document.id:
                self._documents[idx] = document
                return document
        raise ValueError(f"Document {document.id} not found")

    def delete(self, document_id: int) -> None:
        self._documents = [doc for doc in self._documents if doc.id != document_id]

    def count(self) -> int:
        return len(self._documents)
```

### Error-Injecting Stub Pattern

```python
class _FailingDocRepository(_StubDocRepository):
    """Stub that raises exceptions for testing error handling."""

    def __init__(self, exception: Exception):
        super().__init__([])
        self._exception = exception

    def find_by_id(self, document_id: int) -> DocumentModel | None:
        raise self._exception

    def find_all(self, limit: int = 100, offset: int = 0) -> list[DocumentModel]:
        raise self._exception
```

### Service Stub Pattern

```python
class _StubRAGCoordinator:
    """Stub for RAGCoordinator with mock responses."""

    def __init__(self, test_mode: bool = True):
        self.test_mode = test_mode
        self.queries_executed = []
        self.indexes_built = []

    def build_index_from_document(
        self, document: DocumentModel, overwrite: bool = False
    ) -> VectorIndexModel:
        self.indexes_built.append(document.id)
        return VectorIndexModel(
            id=1,
            document_id=document.id,
            index_path=f"/test/index/{document.id}",
            index_hash="test_hash",
            chunk_count=10
        )

    def query_document(self, query: str, document_id: int) -> str:
        self.queries_executed.append((query, document_id))
        return f"Mock response for: {query}"

    def get_document_index_status(self, document_id: int) -> dict:
        return {
            "document_id": document_id,
            "can_query": True,
            "has_index": True,
            "index_valid": True
        }
```

---

## Fixture Usage

### Global Fixtures (conftest.py)

The `tests/conftest.py` file provides:

#### 1. PDF Library Stub
```python
# Automatically installed, no action needed
# sys.modules["fitz"] = stub for PyMuPDF
# sys.modules["pymupdf"] = stub for PyMuPDF
```

#### 2. LlamaIndex Stub
```python
# Automatically installed, no action needed
# sys.modules["llama_index.core"] = stub
# Provides: StorageContext, VectorStoreIndex, load_index_from_storage
```

### Creating Test Fixtures

```python
import pytest
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_document(temp_dir):
    """Create a sample document model with temporary file."""
    pdf_path = temp_dir / "test.pdf"
    pdf_path.write_text("Mock PDF content")

    return DocumentModel(
        id=1,
        title="Test Document",
        file_path=str(pdf_path),
        file_hash="abc123",
        file_size=1024,
        file_type=".pdf"
    )

@pytest.fixture
def stub_doc_repository(sample_document):
    """Provide a stub document repository."""
    return _StubDocRepository([sample_document])
```

---

## RAG Module Testing

### General Strategy

**CRITICAL**: Always use `test_mode=True` for RAG components to avoid:
- LlamaIndex API initialization
- Google Gemini API calls
- Actual file system operations (use stubs)

### Testing RAGQueryEngine

```python
from unittest.mock import Mock
import pytest

from src.services.rag.query_engine import RAGQueryEngine, IndexLoadError
from src.database.models import DocumentModel, VectorIndexModel

def test_query_engine_initialization():
    """Test query engine initializes in test mode."""
    mock_doc_repo = Mock()
    mock_vector_repo = Mock()
    mock_file_manager = Mock()

    engine = RAGQueryEngine(
        document_repo=mock_doc_repo,
        vector_repo=mock_vector_repo,
        file_manager=mock_file_manager,
        test_mode=True  # CRITICAL: Avoids LlamaIndex
    )

    assert engine.test_mode is True
    assert engine.current_index is None
    assert engine.current_document_id is None

def test_load_index_document_not_found():
    """Test loading index for non-existent document."""
    mock_doc_repo = Mock()
    mock_doc_repo.find_by_id.return_value = None

    mock_vector_repo = Mock()
    mock_file_manager = Mock()

    engine = RAGQueryEngine(
        document_repo=mock_doc_repo,
        vector_repo=mock_vector_repo,
        file_manager=mock_file_manager,
        test_mode=True
    )

    with pytest.raises(IndexLoadError, match="Document not found"):
        engine.load_index_for_document(999)

def test_query_document_in_test_mode():
    """Test querying document in test mode returns mock response."""
    # Setup mocks
    mock_document = DocumentModel(
        id=1, title="Test", file_path="/test.pdf",
        file_hash="hash1", file_size=100, file_type=".pdf"
    )
    mock_vector_index = VectorIndexModel(
        id=1, document_id=1, index_path="/test/index",
        index_hash="idx_hash", chunk_count=5
    )

    mock_doc_repo = Mock()
    mock_doc_repo.find_by_id.return_value = mock_document

    mock_vector_repo = Mock()
    mock_vector_repo.find_by_document_id.return_value = mock_vector_index

    mock_file_manager = Mock()
    mock_file_manager.verify_index_files.return_value = True

    engine = RAGQueryEngine(
        document_repo=mock_doc_repo,
        vector_repo=mock_vector_repo,
        file_manager=mock_file_manager,
        test_mode=True
    )

    # Execute query
    response = engine.query_document("What is this about?", 1)

    # Verify test mode response
    assert "Test mode response for query: What is this about?" == response
    assert engine.current_document_id == 1
```

### Testing RAGCoordinator

```python
from unittest.mock import Mock
from src.services.rag.coordinator import RAGCoordinator
from src.database.connection import DatabaseConnection

def test_coordinator_initialization_correct_signature():
    """Test coordinator with CORRECT constructor signature."""
    db_mock = Mock(spec=DatabaseConnection)

    # CORRECT: api_key, db_connection, vector_storage_dir, test_mode
    coordinator = RAGCoordinator(
        api_key="test-key",
        db_connection=db_mock,
        vector_storage_dir="test_indexes",
        test_mode=True
    )

    assert coordinator.test_mode is True
    assert coordinator.api_key == "test-key"
    assert str(coordinator.file_manager.vector_storage_dir) == "test_indexes"

def test_coordinator_delegates_to_query_engine():
    """Test that coordinator delegates query to query_engine."""
    db_mock = Mock(spec=DatabaseConnection)

    coordinator = RAGCoordinator(
        api_key="test-key",
        db_connection=db_mock,
        test_mode=True
    )

    # Setup query_engine mock response
    coordinator.query_engine.query_document = Mock(return_value="Mock response")

    result = coordinator.query_document("test query", 1)

    assert result == "Mock response"
    coordinator.query_engine.query_document.assert_called_once_with("test query", 1)
```

### Testing ChunkingStrategies

```python
from src.services.rag.chunking_strategies import (
    ChunkConfig, SentenceChunker, AdaptiveChunking, CitationAwareChunking
)

def test_sentence_chunker_basic():
    """Test sentence chunker splits text correctly."""
    config = ChunkConfig(chunk_size=100, chunk_overlap=20)
    chunker = SentenceChunker(config)

    text = "First sentence. Second sentence. Third sentence."
    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    assert all("text" in chunk for chunk in chunks)
    assert all(chunk["metadata"]["type"] == "sentence" for chunk in chunks)

def test_adaptive_chunking_complexity_calculation():
    """Test adaptive chunker calculates complexity correctly."""
    config = ChunkConfig(chunk_size=1000)
    chunker = AdaptiveChunking(config)

    # Simple text (low complexity)
    simple = "This is a simple text. No technical terms."
    simple_complexity = chunker._calculate_complexity(simple)

    # Technical text (high complexity)
    technical = "The API uses HTTPS and JWT for authentication. RSA encryption."
    technical_complexity = chunker._calculate_complexity(technical)

    assert technical_complexity > simple_complexity

def test_citation_aware_chunking_extracts_citations():
    """Test citation-aware chunker identifies citations."""
    chunker = CitationAwareChunking()

    text = "This is a claim [1]. Another claim (Smith, 2020). See Figure 1."
    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    chunk = chunks[0]
    assert "citations" in chunk
    assert chunk["citation_count"] > 0
    assert chunk["has_figures"] is True
```

---

## Auth Module Testing

### Testing Auth Service

```python
import pytest
from unittest.mock import Mock
from backend.api.auth.service import AuthService
from backend.api.auth.models import UserCreate

def test_register_user_success():
    """Test successful user registration."""
    mock_user_repo = Mock()
    mock_user_repo.get_by_username.return_value = None
    mock_user_repo.get_by_email.return_value = None
    mock_user_repo.create.return_value = Mock(id=1, username="testuser")

    service = AuthService(user_repo=mock_user_repo)

    user_data = UserCreate(username="testuser", email="test@example.com", password="Test123!")
    result = service.register_user(user_data)

    assert result.id == 1
    assert result.username == "testuser"

def test_register_duplicate_username():
    """Test registration fails with duplicate username."""
    mock_user_repo = Mock()
    mock_user_repo.get_by_username.return_value = Mock(id=1, username="existing")

    service = AuthService(user_repo=mock_user_repo)

    user_data = UserCreate(username="existing", email="new@example.com", password="Test123!")

    with pytest.raises(ValueError, match="Username already exists"):
        service.register_user(user_data)
```

### Testing Auth Routes

```python
import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)

def test_register_endpoint_success():
    """Test /api/auth/register endpoint."""
    response = client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123!"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]

def test_login_invalid_credentials():
    """Test login with invalid credentials."""
    response = client.post(
        "/api/auth/login",
        json={"username": "nonexistent", "password": "wrongpass"}
    )

    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
```

---

## API Route Testing

### Testing Document Routes

```python
from fastapi.testclient import TestClient
from unittest.mock import Mock
import pytest

@pytest.mark.asyncio
async def test_list_documents_pagination():
    """Test document listing with pagination."""
    # Create stub repository
    stub_repo = _StubDocRepository([
        DocumentModel(id=i, title=f"Doc {i}", file_path=f"/doc{i}.pdf",
                     file_hash=f"hash{i}", file_size=100, file_type=".pdf")
        for i in range(1, 11)
    ])

    from backend.api.routes import documents

    response = await documents.list_documents(
        query=None,
        page=1,
        per_page=5,
        sort_by="created_at",
        sort_order="desc",
        doc_repo=stub_repo
    )

    assert response.success is True
    assert len(response.data) == 5
    assert response.meta.total == 10
    assert response.meta.has_next is True

@pytest.mark.asyncio
async def test_get_document_not_found():
    """Test getting non-existent document returns 404."""
    stub_repo = _StubDocRepository([])

    from backend.api.routes import documents
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await documents.get_document(document_id=999, doc_repo=stub_repo)

    assert exc_info.value.status_code == 404
```

---

## Common Patterns

### Pattern 1: Testing Error Paths

```python
def test_service_handles_database_error():
    """Test service gracefully handles database errors."""
    failing_repo = _FailingDocRepository(Exception("Database connection lost"))
    service = DocumentService(doc_repo=failing_repo)

    with pytest.raises(Exception, match="Database connection lost"):
        service.get_document(1)
```

### Pattern 2: Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function execution."""
    result = await some_async_function()
    assert result is not None
```

### Pattern 3: Testing with Temporary Files

```python
import tempfile
from pathlib import Path

def test_function_with_file(tmp_path):
    """Test function that requires file system access."""
    # tmp_path is a pytest built-in fixture
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = process_file(str(test_file))
    assert result == "expected output"
```

### Pattern 4: Parametrized Tests

```python
@pytest.mark.parametrize("input_text,expected_count", [
    ("Simple text.", 1),
    ("First. Second. Third.", 3),
    ("", 0),
])
def test_sentence_count(input_text, expected_count):
    """Test sentence counting with various inputs."""
    count = count_sentences(input_text)
    assert count == expected_count
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run tests in specific directory
pytest tests/services/

# Run specific test file
pytest tests/services/test_rag_query_engine.py

# Run specific test function
pytest tests/services/test_rag_query_engine.py::test_load_index_success

# Run tests with verbose output
pytest -v

# Run tests with coverage
pytest --cov=src --cov=backend --cov-report=term

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run tests and stop on first failure
pytest -x
```

### Coverage Reports

```bash
# Terminal coverage report
pytest --cov=src --cov=backend --cov-report=term-missing

# HTML coverage report
pytest --cov=src --cov=backend --cov-report=html
# View: open htmlcov/index.html

# Generate coverage for specific module
pytest tests/services/test_rag_query_engine.py \
    --cov=src/services/rag/query_engine \
    --cov-report=term-missing
```

### Continuous Integration

```bash
# CI-friendly test run (from Makefile)
make test

# Run tests with coverage threshold
pytest --cov=src --cov=backend --cov-report=term --cov-fail-under=75
```

---

## Coverage Guidelines

### Target Coverage Levels

| Module Type | Target Coverage | Priority |
|-------------|----------------|----------|
| Core Business Logic | 80-90% | High |
| API Routes | 70-80% | High |
| Services | 75-85% | High |
| Repositories | 60-70% | Medium |
| Models | 90-100% | Low (mostly auto-covered) |
| Utilities | 80-90% | Medium |

### What to Test

**✅ DO Test**:
- Business logic and algorithms
- Error handling paths
- Edge cases and boundary conditions
- State transitions
- Integration points between components
- Public API interfaces

**❌ DON'T Test**:
- Third-party library internals
- Simple getters/setters (unless they have logic)
- Trivial pass-through functions
- Auto-generated code

### Coverage Measurement

```python
# Example: Check if critical paths are covered
def test_critical_error_recovery():
    """Ensure critical error recovery path is exercised."""
    service = RAGRecoveryService(...)

    # Test critical corruption path
    result = service.recover_corrupted_index(
        corrupted_index, force_rebuild=True
    )

    assert result["recovery_successful"] is True
    assert "full_rebuild" in result["repair_actions"]
```

---

## Best Practices

### 1. Test Naming

```python
# ✅ GOOD: Descriptive test names
def test_query_engine_raises_error_when_document_not_found():
    ...

def test_coordinator_delegates_query_to_engine():
    ...

# ❌ BAD: Vague test names
def test_query():
    ...

def test_1():
    ...
```

### 2. Test Structure (AAA Pattern)

```python
def test_something():
    # Arrange: Setup test data and dependencies
    mock_repo = Mock()
    service = MyService(repo=mock_repo)
    test_data = {"key": "value"}

    # Act: Execute the function being tested
    result = service.process(test_data)

    # Assert: Verify the outcome
    assert result["status"] == "success"
    mock_repo.save.assert_called_once()
```

### 3. One Assertion Per Test (When Possible)

```python
# ✅ GOOD: Focused test
def test_service_returns_success_status():
    result = service.process()
    assert result["status"] == "success"

def test_service_calls_repository():
    service.process()
    mock_repo.save.assert_called_once()

# ⚠️ ACCEPTABLE: Related assertions
def test_service_response_structure():
    result = service.process()
    assert "status" in result
    assert "data" in result
    assert result["status"] == "success"
```

### 4. Avoid Test Interdependence

```python
# ❌ BAD: Tests depend on execution order
class TestSuite:
    state = None

    def test_first(self):
        self.state = "initialized"

    def test_second(self):
        assert self.state == "initialized"  # Fails if run alone!

# ✅ GOOD: Independent tests
def test_first():
    state = "initialized"
    assert state == "initialized"

def test_second():
    state = initialize_state()
    assert state == "initialized"
```

---

## Troubleshooting

### Common Issues

#### Issue: "Module not found" for llama_index
```python
# Solution: Ensure conftest.py is in tests/ root
# The global conftest.py stubs llama_index automatically
```

#### Issue: Tests timeout or hang
```python
# Solution: Check for actual API calls or blocking I/O
# Ensure test_mode=True for RAG components
# Use Mock() for external dependencies
```

#### Issue: Inconsistent test results
```python
# Solution: Check for:
# - Shared mutable state between tests
# - System time dependencies (use freezegun)
# - Random number generation (set seeds)
# - File system state (use tmp_path fixture)
```

#### Issue: Low coverage on exception handlers
```python
# Solution: Test error paths explicitly
def test_handles_database_error():
    failing_repo = _FailingRepository(ValueError("DB error"))

    with pytest.raises(ServiceError, match="Failed to save"):
        service.save_data(failing_repo)
```

---

## Additional Resources

- **Project Docs**: `/docs/PROJECT_DOCS.md` - Architecture overview
- **RAG API Reference**: `/docs/RAG_API_REFERENCE.md` - Verified method signatures
- **Pytest Documentation**: https://docs.pytest.org/
- **Coverage.py**: https://coverage.readthedocs.io/

---

## Version History

- **2025-11-18**: Initial creation with comprehensive testing patterns
- Includes stub examples, RAG testing strategies, auth testing
- Coverage guidelines and best practices added
