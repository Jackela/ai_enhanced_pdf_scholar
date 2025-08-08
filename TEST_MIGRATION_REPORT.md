# Test Infrastructure Migration Report

Found 40 files that could benefit from optimization:

## tests\test_authentication.py
**2 optimization opportunities**

**Line 325** (mock_fixture):
```python
# Current:
session = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 358** (mock_fixture):
```python
# Current:
existing_user = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\test_citation_network_analysis.py
**2 optimization opportunities**

**Line 18** (mock_fixture):
```python
# Current:
self.citation_repo = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 19** (mock_fixture):
```python
# Current:
self.relation_repo = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\test_citation_repositories.py
**2 optimization opportunities**

**Line 22** (mock_fixture):
```python
# Current:
mock_db = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 417** (mock_fixture):
```python
# Current:
mock_db = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\test_content_hash_service.py
**6 optimization opportunities**

**Line 7** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 28** (temp_directory):
```python
# Current:
cls.temp_txt = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 81** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 83** (temp_directory):
```python
# Current:
with tempfile.TemporaryDirectory() as temp_dir:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 261** (temp_directory):
```python
# Current:
corrupted_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 336** (mock_fixture):
```python
# Current:
mock_file = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\test_enhanced_database_connection.py
**8 optimization opportunities**

**Line 13** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 37** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 110** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 121** (database_fixture):
```python
# Current:
conn = DatabaseConnection(temp_db, max_connections=10)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

**Line 274** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 285** (database_fixture):
```python
# Current:
conn = DatabaseConnection(temp_db, max_connections=20)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

**Line 412** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 423** (database_fixture):
```python
# Current:
conn = DatabaseConnection(temp_db, max_connections=20)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

## tests\test_utils.py
**6 optimization opportunities**

**Line 6** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 42** (temp_directory):
```python
# Current:
temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 99** (mock_fixture):
```python
# Current:
mock_index = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 101** (mock_fixture):
```python
# Current:
mock_index.insert = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 102** (mock_fixture):
```python
# Current:
mock_index.delete = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 108** (mock_fixture):
```python
# Current:
mock_service = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\api\test_basic_endpoints.py
**1 optimization opportunities**

**Line 75** (mock_fixture):
```python
# Current:
mock_db.return_value = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\e2e\test_citation_e2e_workflow.py
**3 optimization opportunities**

**Line 8** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 47** (temp_directory):
```python
# Current:
temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 51** (database_fixture):
```python
# Current:
db_connection = DatabaseConnection(temp_db.name)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

## tests\integration\test_citation_integration.py
**3 optimization opportunities**

**Line 8** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 46** (temp_directory):
```python
# Current:
temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 51** (database_fixture):
```python
# Current:
db_connection = DatabaseConnection(temp_db.name)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

## tests\integration\test_citation_simple_integration.py
**3 optimization opportunities**

**Line 7** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 26** (temp_directory):
```python
# Current:
temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 30** (database_fixture):
```python
# Current:
db_connection = DatabaseConnection(temp_db.name)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

## tests\integration\test_mock_replacement_demo.py
**4 optimization opportunities**

**Line 26** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 53** (temp_directory):
```python
# Current:
self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 55** (temp_directory):
```python
# Current:
self.temp_docs_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 56** (temp_directory):
```python
# Current:
self.temp_vector_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

## tests\integration\test_real_document_library.py
**3 optimization opportunities**

**Line 19** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 54** (temp_directory):
```python
# Current:
cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 94** (temp_directory):
```python
# Current:
self.temp_docs_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

## tests\integration\test_real_pdf_processing.py
**4 optimization opportunities**

**Line 9** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 43** (temp_directory):
```python
# Current:
cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 133** (temp_directory):
```python
# Current:
self.temp_docs_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 134** (temp_directory):
```python
# Current:
self.temp_vector_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

## tests\migrations\test_modular_migrations.py
**14 optimization opportunities**

**Line 13** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 37** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 40** (database_fixture):
```python
# Current:
conn = DatabaseConnection(db_path)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

**Line 140** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 143** (database_fixture):
```python
# Current:
conn = DatabaseConnection(db_path)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

**Line 221** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 224** (database_fixture):
```python
# Current:
conn = DatabaseConnection(db_path)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

**Line 237** (temp_directory):
```python
# Current:
with tempfile.TemporaryDirectory() as temp_dir:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 303** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 306** (database_fixture):
```python
# Current:
conn = DatabaseConnection(db_path)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

**Line 348** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 351** (database_fixture):
```python
# Current:
conn = DatabaseConnection(db_path)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

**Line 425** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 428** (database_fixture):
```python
# Current:
conn = DatabaseConnection(db_path)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

## tests\security\test_api_security_integration.py
**1 optimization opportunities**

**Line 36** (mock_fixture):
```python
# Current:
mock_controller = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\security\test_authentication_authorization.py
**1 optimization opportunities**

**Line 39** (mock_fixture):
```python
# Current:
service = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\security\test_cors_api_integration.py
**6 optimization opportunities**

**Line 33** (mock_fixture):
```python
# Current:
mock_db = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 37** (mock_fixture):
```python
# Current:
mock_rag = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 41** (mock_fixture):
```python
# Current:
mock_controller = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 281** (mock_fixture):
```python
# Current:
mock_db = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 284** (mock_fixture):
```python
# Current:
mock_rag = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 287** (mock_fixture):
```python
# Current:
mock_controller = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\security\test_performance_impact.py
**1 optimization opportunities**

**Line 22** (mock_fixture):
```python
# Current:
mock_db = Mock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\services\test_document_library_service.py
**4 optimization opportunities**

**Line 13** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 41** (temp_directory):
```python
# Current:
cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 98** (temp_directory):
```python
# Current:
self.temp_docs_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 127** (temp_directory):
```python
# Current:
custom_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

## tests\services\test_document_library_service_enhancements.py
**3 optimization opportunities**

**Line 11** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 35** (temp_directory):
```python
# Current:
cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 90** (temp_directory):
```python
# Current:
self.temp_docs_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

## tests\services\test_enhanced_rag_service.py
**7 optimization opportunities**

**Line 265** (mock_fixture):
```python
# Current:
MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 267** (mock_fixture):
```python
# Current:
mock_index_instance = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 444** (mock_fixture):
```python
# Current:
mock_index = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 456** (mock_fixture):
```python
# Current:
self.service.current_index = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 476** (mock_fixture):
```python
# Current:
mock_index = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 477** (mock_fixture):
```python
# Current:
mock_query_engine = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 478** (mock_fixture):
```python
# Current:
mock_response = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\services\test_error_recovery.py
**4 optimization opportunities**

**Line 317** (mock_fixture):
```python
# Current:
mock_db = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 318** (mock_fixture):
```python
# Current:
mock_transaction = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 332** (mock_fixture):
```python
# Current:
mock_db = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 333** (mock_fixture):
```python
# Current:
mock_db.transaction.return_value.__enter__ = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\services\test_vector_index_manager.py
**11 optimization opportunities**

**Line 14** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 37** (temp_directory):
```python
# Current:
cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 85** (temp_directory):
```python
# Current:
self.temp_storage_dir = tempfile.mkdtemp()

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 201** (mock_fixture):
```python
# Current:
mock_dt = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 243** (temp_directory):
```python
# Current:
source_dir = Path(tempfile.mkdtemp())

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 277** (temp_directory):
```python
# Current:
source_dir = Path(tempfile.mkdtemp())

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 295** (temp_directory):
```python
# Current:
source_dir = Path(tempfile.mkdtemp())

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 315** (temp_directory):
```python
# Current:
source_dir = Path(tempfile.mkdtemp())

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 582** (temp_directory):
```python
# Current:
temp_dir = Path(tempfile.mkdtemp())

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 594** (temp_directory):
```python
# Current:
temp_dir = Path(tempfile.mkdtemp())

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 612** (temp_directory):
```python
# Current:
temp_dir = Path(tempfile.mkdtemp())

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

## tests\unit\test_repository_layer.py
**2 optimization opportunities**

**Line 288** (mock_fixture):
```python
# Current:
mock_transaction.return_value.__enter__ = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 289** (mock_fixture):
```python
# Current:
mock_transaction.return_value.__exit__ = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\unit\test_service_layer.py
**4 optimization opportunities**

**Line 56** (mock_fixture):
```python
# Current:
mock_doc = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 57** (mock_fixture):
```python
# Current:
mock_page = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 139** (mock_fixture):
```python
# Current:
mock_doc = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 140** (mock_fixture):
```python
# Current:
mock_page = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

## tests\unit_tests\test_content_hash_service.py
**3 optimization opportunities**

**Line 7** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 27** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(delete=False) as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 255** (temp_directory):
```python
# Current:
with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

## tests\conftest.py
**4 optimization opportunities**

**Line 11** (temp_directory):
```python
# Current:
import tempfile

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 36** (temp_directory):
```python
# Current:
with tempfile.TemporaryDirectory(prefix="ai_pdf_test_") as temp_dir:

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 73** (temp_directory):
```python
# Current:
temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)

# Suggested:
def test_func(test_data_directory):
```
*Use test_data_directory fixture*

**Line 77** (database_fixture):
```python
# Current:
db = DatabaseConnection(temp_file.name)

# Suggested:
def test_func(db_connection):  # from conftest.py
```
*Use optimized db_connection fixture from test_utils*

## tests\security\conftest.py
**2 optimization opportunities**

**Line 223** (mock_fixture):
```python
# Current:
mock = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*

**Line 234** (mock_fixture):
```python
# Current:
mock = MagicMock()

# Suggested:
mock_factory.create_mock_...()
```
*Use MockFactory from test_utils*


## Quick Migration Guide

### 1. Update imports in test files:
```python
# Add to test file imports:
from tests.test_utils import db_manager, mock_factory
```

### 2. Replace database fixtures:
```python
# Old:
@pytest.fixture
def db_connection():
    db = DatabaseConnection(':memory:')
    # ... setup ...
    yield db
    db.close_connection()

# New:
def test_my_function(db_connection):  # Use fixture from conftest.py
    # db_connection is already set up and cleaned
    pass
```

### 3. Replace manual mocks:
```python
# Old:
mock_service = Mock()
mock_service.method.return_value = 'result'

# New:
def test_my_function(mock_factory):
    mock_service = mock_factory.create_mock_embedding_service()
    # Pre-configured with sensible defaults
```

### 4. Use performance fixtures:
```python
def test_performance_sensitive(performance_tracker):
    with performance_tracker.measure('operation'):
        # Code being measured
        pass
    # Automatically logged if slow
```