# AI Enhanced PDF Scholar - Testing Guide

## 🎯 Testing Philosophy

This project maintains high code quality through comprehensive testing at multiple levels. Our testing strategy ensures reliability, performance, and maintainability while supporting rapid development.

## 📊 Testing Overview

### Test Coverage Metrics
- **Overall Coverage**: 75%+ across all critical components
- **Unit Tests**: 63 citation system tests + 64 core functionality tests
- **Integration Tests**: Database and service layer validation
- **E2E Tests**: Complete workflow automation
- **Performance Tests**: Automated benchmarking and optimization

### Testing Pyramid
```
                    E2E Tests (5%)
                 ─────────────────
                Integration Tests (15%)
            ─────────────────────────────
           Unit Tests (80%)
    ─────────────────────────────────────────
```

## 🧪 Test Structure and Organization

### Directory Structure
```
tests/
├── unit/                          # Fast, isolated unit tests
│   ├── test_core_functionality.py # Core system components
│   ├── test_database_layer.py     # Database models and connections
│   ├── test_repository_layer.py   # Repository pattern tests
│   ├── test_service_layer.py      # Business logic tests
│   └── test_smoke.py              # Basic smoke tests
├── integration/                   # Service integration tests
│   ├── test_document_workflow.py  # End-to-end document processing
│   ├── test_citation_integration.py # Citation system integration
│   └── test_api_integration.py    # API endpoint testing
├── e2e/                          # Browser-based end-to-end tests
│   ├── test_user_workflows.py    # Complete user scenarios
│   └── test_performance.py       # Real-world performance tests
├── performance/                  # Performance and benchmark tests
│   ├── test_database_performance.py
│   ├── test_api_performance.py
│   └── test_citation_performance.py
├── conftest.py                   # Shared test fixtures
└── fixtures/                     # Test data and sample files
    ├── sample_pdfs/
    ├── test_citations.json
    └── mock_responses.json
```

### Test Categories and Markers

#### pytest Markers
```python
# Core test categories
@pytest.mark.unit          # Fast, isolated unit tests
@pytest.mark.integration   # Component interaction tests
@pytest.mark.e2e          # End-to-end workflow tests
@pytest.mark.slow         # Tests taking >1 second

# Feature-specific markers
@pytest.mark.database     # Database-related tests
@pytest.mark.services     # Service layer tests
@pytest.mark.repositories # Repository pattern tests
@pytest.mark.performance  # Performance benchmark tests

# Special execution markers
@pytest.mark.skip_ci      # Skip in CI environment
@pytest.mark.local_only   # Requires local setup
```

## 🚀 Running Tests

### Quick Test Commands

#### Full Test Suite
```bash
# Run all tests with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Parallel execution for speed
pytest tests/ -n auto --dist=loadfile

# Verbose output with live logs
pytest tests/ -v -s --log-cli-level=INFO
```

#### Targeted Test Execution
```bash
# Unit tests only (fastest)
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# Performance tests
pytest tests/performance -v --benchmark-only

# Specific test file
pytest tests/unit/test_core_functionality.py -v

# Specific test method
pytest tests/unit/test_core_functionality.py::TestCoreModels::test_document_model_creation -v
```

#### CI/CD Test Commands
```bash
# Lightweight CI test (used in GitHub Actions)
pytest tests/unit -v --cov=src --cov-report=xml --cov-fail-under=8 --override-ini="addopts="

# Full CI test suite
pytest tests/ --cov=src --cov-report=xml --cov-fail-under=75 -n auto
```

### Test Configuration

#### pytest.ini Configuration
```ini
[pytest]
testpaths = tests
python_paths = . src
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=src
    --cov-report=html:coverage_html
    --cov-report=term-missing
    --cov-report=xml:coverage.xml
    --cov-fail-under=20
    --cov-branch
    --cov-config=.coveragerc
    -n auto
    --dist=loadfile
    --maxfail=10

markers =
    unit: Unit tests - isolated component testing
    integration: Integration tests - component interaction
    e2e: End-to-end tests - full workflow testing
    slow: Slow running tests
    database: Tests requiring database setup
    services: Service layer tests
    repositories: Repository layer tests
    performance: Performance benchmark tests

# Minimum Python version
minversion = 3.10

# Test discovery patterns
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Logging configuration
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s [%(levelname)8s] %(name)s: %(message)s
log_cli_date_format = %Y-%m-%d %H:%M:%S

# Performance settings - optimized for faster execution
timeout = 60
timeout_method = thread
```

#### Coverage Configuration
```ini
[coverage:run]
source = src
omit = 
    src/web/static/*
    */tests/*
    */test_*
    */__pycache__/*
    */migrations/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    if self.debug:
    if settings.DEBUG
    raise AssertionError
    raise NotImplementedError
    if 0:
    if __name__ == .__main__.:
    class .*\bProtocol\):
    @(abc\.)?abstractmethod

[coverage:html]
directory = coverage_html
```

## 🔧 Test Development

### Writing Unit Tests

#### Basic Test Structure
```python
"""
Test module following project conventions.
Each test should be fast, isolated, and deterministic.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.database.models import DocumentModel
from src.services.content_hash_service import ContentHashService


class TestDocumentModel:
    """Test DocumentModel creation and validation."""

    def test_document_model_creation(self):
        """Test basic DocumentModel instantiation."""
        doc = DocumentModel(
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash_123",
            file_size=1024
        )
        
        assert doc.title == "Test Document"
        assert doc.file_path == "/test/path.pdf"
        assert doc.file_hash == "test_hash_123"
        assert doc.file_size == 1024
        assert doc.metadata == {}
        assert doc.created_at is not None
        assert doc.updated_at is not None

    def test_document_model_validation(self):
        """Test DocumentModel validation rules."""
        # Test empty hash validation
        with pytest.raises(ValueError, match="File hash cannot be empty"):
            DocumentModel(
                title="Test",
                file_path="/test/path.pdf",
                file_hash="",
                file_size=1024
            )
        
        # Test negative file size validation
        with pytest.raises(ValueError, match="File size cannot be negative"):
            DocumentModel(
                title="Test",
                file_path="/test/path.pdf",
                file_hash="test_hash",
                file_size=-1
            )

    @pytest.mark.parametrize("file_size,expected", [
        (0, True),
        (1024, True),
        (1024*1024, True),
        (-1, False),
    ])
    def test_file_size_validation(self, file_size, expected):
        """Test file size validation with parametrized inputs."""
        if expected:
            doc = DocumentModel(
                title="Test",
                file_path="/test/path.pdf",
                file_hash="test_hash",
                file_size=file_size
            )
            assert doc.file_size == file_size
        else:
            with pytest.raises(ValueError):
                DocumentModel(
                    title="Test",
                    file_path="/test/path.pdf",
                    file_hash="test_hash",
                    file_size=file_size
                )
```

#### Service Layer Testing
```python
class TestContentHashService:
    """Test ContentHashService functionality."""

    def test_file_hash_calculation(self):
        """Test file hash calculation with temporary files."""
        service = ContentHashService()
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content")
            temp_file_path = temp_file.name
        
        try:
            # Calculate hash
            hash_result = service.calculate_file_hash(temp_file_path)
            assert hash_result is not None
            assert len(hash_result) == 16  # 16-character hex length
            
            # Verify hash is consistent
            hash_result2 = service.calculate_file_hash(temp_file_path)
            assert hash_result == hash_result2
            
        finally:
            Path(temp_file_path).unlink(missing_ok=True)

    @patch('src.services.content_hash_service.fitz')
    def test_pdf_processing_with_mock(self, mock_fitz):
        """Test PDF processing with mocked dependencies."""
        # Setup mock
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Sample PDF content"
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        service = ContentHashService()
        result = service._extract_pdf_text("test.pdf")
        
        assert result == "Sample PDF content"
        mock_fitz.open.assert_called_once_with("test.pdf")

    @pytest.mark.performance
    def test_hash_calculation_performance(self):
        """Test hash calculation performance benchmarks."""
        import time
        
        service = ContentHashService()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content" * 100)
            temp_file_path = temp_file.name
        
        try:
            start_time = time.time()
            hash_result = service.calculate_file_hash(temp_file_path)
            duration = time.time() - start_time
            
            assert hash_result is not None
            assert duration < 0.1  # Should be fast for small content
            
        finally:
            Path(temp_file_path).unlink(missing_ok=True)
```

### Database Testing

#### Repository Testing with Fixtures
```python
@pytest.fixture
def test_database():
    """Create a test database for isolated testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        db_path = temp_db.name
    
    try:
        db = DatabaseConnection(db_path)
        # Initialize schema
        db.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        yield db
    finally:
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)


class TestDocumentRepository:
    """Test DocumentRepository CRUD operations."""

    def test_create_document(self, test_database):
        """Test document creation."""
        repo = DocumentRepository(test_database)
        
        doc = DocumentModel(
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="test_hash",
            file_size=1024
        )
        
        created_doc = repo.create(doc)
        assert created_doc.id is not None
        assert created_doc.title == "Test Document"

    def test_find_by_hash(self, test_database):
        """Test finding documents by hash."""
        repo = DocumentRepository(test_database)
        
        # Create test document
        doc = DocumentModel(
            title="Test Document",
            file_path="/test/path.pdf",
            file_hash="unique_hash_123",
            file_size=1024
        )
        created_doc = repo.create(doc)
        
        # Find by hash
        found_doc = repo.find_by_hash("unique_hash_123")
        assert found_doc is not None
        assert found_doc.id == created_doc.id
        assert found_doc.file_hash == "unique_hash_123"
        
        # Test non-existent hash
        not_found = repo.find_by_hash("non_existent_hash")
        assert not_found is None

    @pytest.mark.database
    def test_repository_transaction_support(self, test_database):
        """Test repository transaction handling."""
        repo = DocumentRepository(test_database)
        
        try:
            with test_database.transaction():
                doc1 = DocumentModel(
                    title="Doc 1", file_path="/test/1.pdf", 
                    file_hash="hash1", file_size=100
                )
                doc2 = DocumentModel(
                    title="Doc 2", file_path="/test/2.pdf", 
                    file_hash="hash2", file_size=200
                )
                
                repo.create(doc1)
                repo.create(doc2)
                
                # Simulate error
                raise Exception("Simulated error")
                
        except Exception:
            pass  # Expected exception
        
        # Verify rollback
        docs = repo.find_all()
        assert len(docs) == 0  # Transaction should have rolled back
```

### Integration Testing

#### API Integration Tests
```python
import asyncio
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


class TestDocumentAPI:
    """Test document API endpoints."""

    def test_health_endpoint(self):
        """Test system health endpoint."""
        response = client.get("/api/system/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_document_upload(self):
        """Test document upload endpoint."""
        # Create test PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(b"%PDF-1.4\n%Test PDF content")
            temp_pdf_path = temp_pdf.name
        
        try:
            with open(temp_pdf_path, "rb") as f:
                files = {"file": ("test.pdf", f, "application/pdf")}
                response = client.post("/api/documents/upload", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "document_id" in data
            
        finally:
            Path(temp_pdf_path).unlink(missing_ok=True)

    def test_document_list(self):
        """Test document listing endpoint."""
        response = client.get("/api/documents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["documents"], list)
        assert "total" in data

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection for real-time updates."""
        from fastapi.testclient import TestClient
        
        with client.websocket_connect("/ws/documents") as websocket:
            # Test connection
            data = websocket.receive_json()
            assert data["type"] == "connection_established"
            
            # Test message sending
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()
            assert response["type"] == "pong"
```

#### Citation System Integration
```python
class TestCitationIntegration:
    """Test citation system integration."""

    def test_citation_extraction_workflow(self, test_database):
        """Test complete citation extraction workflow."""
        # Setup services
        doc_service = DocumentLibraryService(test_database)
        citation_service = CitationService(test_database)
        
        # Create test document with citations
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            # Create PDF with citation content
            temp_pdf.write(b"""%PDF-1.4
References:
Smith, J. (2023). Machine Learning Applications. Journal of AI, 15(3), 45-67.
Johnson, A., & Davis, B. (2022). Data Analysis Methods. Proceedings of Data Science Conference, 123-145.
""")
            temp_pdf_path = temp_pdf.name
        
        try:
            # Upload and process document
            doc_id = doc_service.add_document(temp_pdf_path, "Test Paper")
            
            # Wait for citation processing
            import time
            time.sleep(1)  # Allow async processing
            
            # Verify citations were extracted
            citations = citation_service.get_citations_by_document(doc_id)
            assert len(citations) >= 2
            
            # Verify citation data
            smith_citation = next(
                (c for c in citations if "Smith" in c.authors), None
            )
            assert smith_citation is not None
            assert smith_citation.publication_year == 2023
            assert smith_citation.confidence_score > 0.8
            
        finally:
            Path(temp_pdf_path).unlink(missing_ok=True)

    def test_citation_network_analysis(self, test_database):
        """Test citation network relationship analysis."""
        citation_service = CitationService(test_database)
        
        # Create test documents and citations
        # (Implementation would create multiple docs with cross-references)
        
        # Test network analysis
        network = citation_service.analyze_citation_network()
        assert "nodes" in network
        assert "edges" in network
        assert len(network["nodes"]) > 0
```

### Performance Testing

#### Database Performance Tests
```python
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestDatabasePerformance:
    """Test database performance and concurrency."""

    @pytest.mark.performance
    def test_bulk_insert_performance(self, test_database):
        """Test bulk insertion performance."""
        repo = DocumentRepository(test_database)
        
        # Generate test data
        documents = [
            DocumentModel(
                title=f"Document {i}",
                file_path=f"/test/doc_{i}.pdf",
                file_hash=f"hash_{i}",
                file_size=1024 + i
            )
            for i in range(1000)
        ]
        
        # Measure insertion time
        start_time = time.time()
        
        with test_database.transaction():
            for doc in documents:
                repo.create(doc)
        
        duration = time.time() - start_time
        
        # Performance assertions
        assert duration < 5.0  # Should complete within 5 seconds
        assert len(repo.find_all()) == 1000
        
        # Calculate operations per second
        ops_per_second = 1000 / duration
        assert ops_per_second > 200  # Minimum 200 ops/second

    @pytest.mark.performance
    def test_concurrent_database_access(self, test_database):
        """Test concurrent database operations."""
        repo = DocumentRepository(test_database)
        
        def create_document(index):
            """Create a document in a separate thread."""
            doc = DocumentModel(
                title=f"Concurrent Document {index}",
                file_path=f"/test/concurrent_{index}.pdf",
                file_hash=f"concurrent_hash_{index}",
                file_size=1024
            )
            return repo.create(doc)
        
        # Test concurrent operations
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(create_document, i) 
                for i in range(100)
            ]
            
            results = [future.result() for future in as_completed(futures)]
        
        duration = time.time() - start_time
        
        # Verify all operations completed
        assert len(results) == 100
        assert all(result.id is not None for result in results)
        assert duration < 10.0  # Should complete within 10 seconds

    @pytest.mark.performance  
    def test_query_performance(self, test_database):
        """Test query performance with indexes."""
        repo = DocumentRepository(test_database)
        
        # Create test data
        for i in range(1000):
            doc = DocumentModel(
                title=f"Performance Test {i}",
                file_path=f"/test/perf_{i}.pdf",
                file_hash=f"perf_hash_{i}",
                file_size=1024
            )
            repo.create(doc)
        
        # Test query performance
        start_time = time.time()
        
        # Perform multiple queries
        for _ in range(100):
            results = repo.search("Performance Test")
            assert len(results) > 0
        
        duration = time.time() - start_time
        queries_per_second = 100 / duration
        
        assert queries_per_second > 50  # Minimum 50 queries/second
```

#### API Performance Tests
```python
class TestAPIPerformance:
    """Test API endpoint performance."""

    @pytest.mark.performance
    def test_concurrent_api_requests(self):
        """Test API performance under concurrent load."""
        import concurrent.futures
        import requests
        
        def make_request():
            """Make a single API request."""
            response = requests.get("http://localhost:8000/api/documents")
            return response.status_code, response.elapsed.total_seconds()
        
        # Test concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [future.result() for future in futures]
        
        # Analyze results
        status_codes = [result[0] for result in results]
        response_times = [result[1] for result in results]
        
        # Performance assertions
        assert all(code == 200 for code in status_codes)
        assert max(response_times) < 1.0  # Max 1 second response time
        assert sum(response_times) / len(response_times) < 0.5  # Average < 500ms

    @pytest.mark.performance
    def test_large_file_upload_performance(self):
        """Test large file upload performance."""
        # Create large test file (10MB)
        large_content = b"test content " * (1024 * 1024)  # ~10MB
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(b"%PDF-1.4\n")
            temp_file.write(large_content)
            temp_file_path = temp_file.name
        
        try:
            start_time = time.time()
            
            with open(temp_file_path, "rb") as f:
                files = {"file": ("large_test.pdf", f, "application/pdf")}
                response = client.post("/api/documents/upload", files=files)
            
            duration = time.time() - start_time
            
            assert response.status_code == 200
            assert duration < 30.0  # Should complete within 30 seconds
            
        finally:
            Path(temp_file_path).unlink(missing_ok=True)
```

## 🔍 Test Debugging and Troubleshooting

### Common Test Issues

#### Test Environment Issues
```python
# Issue: Tests failing due to environment differences
# Solution: Use proper fixtures and isolation

@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment for each test."""
    # Clear caches
    import os
    if os.path.exists("./test_cache"):
        shutil.rmtree("./test_cache")
    
    # Reset global state
    from src.core.state_manager import StateManager
    StateManager.reset()
    
    yield
    
    # Cleanup after test
    # ... cleanup code ...
```

#### Database Test Issues
```python
# Issue: Database lock errors in tests
# Solution: Proper connection management

@pytest.fixture
def isolated_database():
    """Create isolated database for testing."""
    db_path = f"test_{uuid.uuid4().hex}.db"
    
    try:
        db = DatabaseConnection(db_path)
        yield db
    finally:
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)
```

#### Mock and Fixture Issues
```python
# Issue: Mocks not working as expected
# Solution: Proper mock setup and verification

@pytest.fixture
def mock_api_client():
    """Mock external API client."""
    with patch('src.services.external_api.APIClient') as mock:
        mock_instance = mock.return_value
        mock_instance.query.return_value = {"status": "success"}
        yield mock_instance

def test_with_proper_mock(mock_api_client):
    """Test using properly configured mock."""
    service = ExternalService()
    result = service.call_api()
    
    # Verify mock was called
    mock_api_client.query.assert_called_once()
    assert result["status"] == "success"
```

### Test Debugging Tools

#### Debug Test Output
```bash
# Run tests with detailed output
pytest tests/unit/test_core_functionality.py -v -s --tb=long

# Run specific test with debugging
pytest tests/unit/test_core_functionality.py::TestDocumentModel::test_document_model_creation -v -s --pdb

# Run with live logging
pytest tests/unit -v --log-cli-level=DEBUG

# Run with profiling
pytest tests/unit --profile
```

#### Test Coverage Analysis
```bash
# Generate detailed coverage report
pytest tests/unit --cov=src --cov-report=html --cov-report=term-missing

# View coverage report
open coverage_html/index.html

# Identify missing coverage
pytest tests/unit --cov=src --cov-report=term-missing | grep "TOTAL"
```

## 📈 Performance Optimization

### Test Performance Optimization

#### Parallel Test Execution
```bash
# Optimal parallel execution
pytest tests/unit -n auto --dist=loadfile

# Custom worker count
pytest tests/unit -n 4 --dist=loadfile

# Load balancing by test duration
pytest tests/unit -n auto --dist=loadscope
```

#### Test Data Optimization
```python
# Use session-scoped fixtures for expensive setup
@pytest.fixture(scope="session")
def sample_database():
    """Create database once per test session."""
    # ... expensive setup ...
    yield db
    # ... cleanup ...

# Use parametrize for multiple test cases
@pytest.mark.parametrize("input,expected", [
    ("test1", "result1"),
    ("test2", "result2"),
    ("test3", "result3"),
])
def test_multiple_cases(input, expected):
    assert process(input) == expected
```

#### Memory and Resource Management
```python
# Explicit resource cleanup in tests
def test_with_proper_cleanup():
    """Test with explicit resource management."""
    resource = create_expensive_resource()
    
    try:
        # Test logic
        result = use_resource(resource)
        assert result is not None
    finally:
        # Ensure cleanup even if test fails
        cleanup_resource(resource)

# Use context managers for automatic cleanup
@contextmanager
def test_database():
    """Context manager for test database."""
    db = create_test_database()
    try:
        yield db
    finally:
        cleanup_database(db)
```

### CI/CD Test Optimization

#### GitHub Actions Test Configuration
```yaml
# Optimized test job
test-job:
  name: 🧪 Test Suite
  runs-on: ubuntu-latest
  timeout-minutes: 15
  
  strategy:
    matrix:
      python-version: [3.11, 3.12]
      test-group: [unit, integration, e2e]
  
  steps:
    - name: 📥 Checkout
      uses: actions/checkout@v4
      
    - name: 🐍 Setup Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'
        
    - name: 📦 Install Dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt -r requirements-test.txt
        
    - name: 🧪 Run Tests
      run: |
        pytest tests/${{ matrix.test-group }} \
          --cov=src \
          --cov-report=xml \
          --cov-fail-under=75 \
          -n auto \
          --dist=loadfile \
          --maxfail=5
        
    - name: 📊 Upload Coverage
      uses: codecov/codecov-action@v3
      if: matrix.test-group == 'unit'
      with:
        file: ./coverage.xml
```

## 📚 Best Practices and Guidelines

### Test Writing Best Practices

#### Test Structure
```python
# Follow AAA pattern: Arrange, Act, Assert
def test_document_creation():
    """Test document creation follows AAA pattern."""
    # Arrange
    title = "Test Document"
    file_path = "/test/path.pdf"
    file_hash = "test_hash"
    file_size = 1024
    
    # Act
    document = DocumentModel(
        title=title,
        file_path=file_path,
        file_hash=file_hash,
        file_size=file_size
    )
    
    # Assert
    assert document.title == title
    assert document.file_path == file_path
    assert document.file_hash == file_hash
    assert document.file_size == file_size
```

#### Test Naming Conventions
```python
# Good test names are descriptive and specific
def test_document_model_creation_with_valid_data():
    """Test that DocumentModel can be created with valid input data."""
    pass

def test_document_model_validation_raises_error_for_empty_hash():
    """Test that DocumentModel raises ValueError when file_hash is empty."""
    pass

def test_citation_service_extracts_multiple_citations_from_pdf():
    """Test that CitationService can extract multiple citations from a PDF."""
    pass
```

#### Test Data Management
```python
# Use factories for test data creation
class DocumentFactory:
    """Factory for creating test documents."""
    
    @staticmethod
    def create_document(**kwargs):
        """Create a document with default test data."""
        defaults = {
            "title": "Test Document",
            "file_path": "/test/default.pdf",
            "file_hash": "default_hash",
            "file_size": 1024,
        }
        defaults.update(kwargs)
        return DocumentModel(**defaults)

# Use in tests
def test_document_creation():
    """Test document creation using factory."""
    doc = DocumentFactory.create_document(title="Custom Title")
    assert doc.title == "Custom Title"
```

### Performance Testing Guidelines

#### Benchmark Testing
```python
import pytest
from pytest_benchmark import benchmark

def test_hash_calculation_benchmark(benchmark):
    """Benchmark hash calculation performance."""
    service = ContentHashService()
    
    def hash_operation():
        return service.calculate_string_hash("test content" * 1000)
    
    result = benchmark(hash_operation)
    assert result is not None
    
    # Benchmark automatically captures timing statistics
```

#### Load Testing
```python
def test_concurrent_document_processing():
    """Test system under concurrent load."""
    import concurrent.futures
    import time
    
    def process_document(doc_id):
        # Simulate document processing
        service = DocumentService()
        return service.process_document(doc_id)
    
    # Test with multiple concurrent operations
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(process_document, i) 
            for i in range(50)
        ]
        results = [f.result() for f in futures]
    
    duration = time.time() - start_time
    
    # Performance assertions
    assert len(results) == 50
    assert duration < 30.0  # Should complete within 30 seconds
    assert all(result.success for result in results)
```

### Test Maintenance

#### Test Health Monitoring
```python
# Add test execution time monitoring
@pytest.mark.timeout(10)  # Fail if test takes >10 seconds
def test_with_timeout():
    """Test with execution timeout."""
    # Test implementation
    pass

# Monitor test flakiness
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_potentially_flaky():
    """Test that might be flaky - retry up to 3 times."""
    # Test implementation
    pass
```

#### Test Documentation
```python
def test_citation_extraction_confidence_scoring():
    """
    Test citation extraction confidence scoring algorithm.
    
    This test verifies that the citation parsing service correctly
    assigns confidence scores based on the completeness and format
    of extracted citation data.
    
    Test scenarios:
    1. Complete, well-formatted citation -> high confidence (>0.9)
    2. Missing some fields -> medium confidence (0.5-0.8)
    3. Poorly formatted citation -> low confidence (<0.5)
    
    Expected behavior:
    - Complete citations with all required fields should score >0.9
    - Citations missing 1-2 optional fields should score 0.5-0.8
    - Malformed or incomplete citations should score <0.5
    """
    # Test implementation with detailed scenarios
    pass
```

## 🚀 Advanced Testing Techniques

### Property-Based Testing
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1), st.integers(min_value=0))
def test_document_model_with_random_data(title, file_size):
    """Test DocumentModel with random valid inputs."""
    doc = DocumentModel(
        title=title,
        file_path="/test/path.pdf",
        file_hash="test_hash",
        file_size=file_size
    )
    
    assert doc.title == title
    assert doc.file_size == file_size
    assert len(doc.file_hash) > 0
```

### Mutation Testing
```bash
# Install mutation testing tool
pip install mutmut

# Run mutation tests
mutmut run --paths-to-mutate=src/

# Check results
mutmut results
mutmut show <mutation_id>
```

### Contract Testing
```python
class TestServiceContracts:
    """Test service interface contracts."""
    
    def test_document_service_interface_contract(self):
        """Test that DocumentService implements expected interface."""
        service = DocumentService()
        
        # Verify required methods exist
        assert hasattr(service, 'add_document')
        assert hasattr(service, 'get_document')
        assert hasattr(service, 'delete_document')
        
        # Verify method signatures
        import inspect
        add_doc_sig = inspect.signature(service.add_document)
        assert 'file_path' in add_doc_sig.parameters
        assert 'title' in add_doc_sig.parameters
```

---

## 📞 Testing Support and Resources

### Getting Help with Testing
- **Documentation**: Comprehensive testing guides and examples
- **Code Examples**: Real-world test patterns and implementations
- **Performance Benchmarks**: Expected performance metrics and goals
- **CI/CD Integration**: Automated testing pipeline configuration

### Testing Tools and Resources
- **pytest Documentation**: https://docs.pytest.org/
- **Coverage.py Documentation**: https://coverage.readthedocs.io/
- **Hypothesis Documentation**: https://hypothesis.readthedocs.io/
- **Performance Testing**: pytest-benchmark, locust, apache bench

### Continuous Improvement
- **Test Metrics**: Track test execution time, coverage, and reliability
- **Test Reviews**: Regular review of test quality and effectiveness
- **Performance Monitoring**: Continuous performance regression detection
- **Test Automation**: Automated test generation and maintenance

---

*This testing guide is regularly updated with new techniques and best practices. For the latest version, check the project repository.*

*Last Updated: 2025-01-21*
*Version: 2.1.0*