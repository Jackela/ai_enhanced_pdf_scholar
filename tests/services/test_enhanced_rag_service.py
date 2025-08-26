"""
Comprehensive Tests for EnhancedRAGService
Tests all aspects of the enhanced RAG service including:
- Service initialization and configuration
- PDF index building and management
- Document querying and response generation
- Vector index persistence and database integration
- Status checking and cache management
- Error handling and edge cases
- Test mode vs production mode behavior
"""

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel, VectorIndexModel
from src.services.content_hash_service import ContentHashError
from src.services.enhanced_rag_service import (
    EnhancedRAGService,
    EnhancedRAGServiceError,
    RAGIndexError,
    RAGQueryError,
    RAGServiceError,
    VectorIndexNotFoundError,
)


class TestEnhancedRAGService:
    """Comprehensive test suite for EnhancedRAGService."""

    @classmethod
    def setup_class(cls):
        """Set up test database."""
        # Create temporary database
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name
        # Create database connection
        cls.db = DatabaseConnection(cls.db_path)
        # Initialize database schema
        cls._initialize_test_database()

    @classmethod
    def teardown_class(cls):
        """Clean up test database."""
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)

    @classmethod
    def _initialize_test_database(cls):
        """Initialize database schema for testing."""
        # Create documents table
        cls.db.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                content_hash TEXT,
                file_size INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT ''
            )
        """
        )
        # Create vector_indexes table
        cls.db.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                index_path TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                index_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """
        )

    def setup_method(self):
        """Set up for each test method."""
        # Create temporary storage directory
        self.temp_storage_dir = tempfile.mkdtemp()
        # Create service instance
        self.service = EnhancedRAGService(
            api_key="test_api_key",
            db_connection=self.db,
            vector_storage_dir=self.temp_storage_dir,
            test_mode=True,
        )
        # Clear database tables
        self.db.execute("DELETE FROM vector_indexes")
        self.db.execute("DELETE FROM documents")
        # Create test PDF file
        self.test_pdf_path = Path(tempfile.mktemp(suffix=".pdf"))
        self.test_pdf_path.write_text("fake pdf content")

    def teardown_method(self):
        """Clean up after each test method."""
        if Path(self.temp_storage_dir).exists():
            shutil.rmtree(self.temp_storage_dir)
        if self.test_pdf_path.exists():
            self.test_pdf_path.unlink()

    def _create_test_document(self, **kwargs) -> DocumentModel:
        """Create a test document."""
        defaults = {
            "title": "Test Document",
            "file_path": str(self.test_pdf_path),
            "file_hash": "abc123def456",
            "content_hash": "content123hash456",
            "file_size": 1024,
            "page_count": 5,
        }
        defaults.update(kwargs)
        return DocumentModel(**defaults)

    def _create_mock_index_files(self, index_path: Path):
        """Create mock LlamaIndex files for testing."""
        index_path.mkdir(parents=True, exist_ok=True)
        # Create required LlamaIndex files with realistic content
        required_files = {
            "default__vector_store.json": {
                "embedding_dict": {f"chunk_{i}": [0.1] * 384 for i in range(5)},
                "metadata_dict": {},
            },
            "graph_store.json": {"graph_dict": {}},
            "index_store.json": {"index_store": {}},
        }
        for filename, content in required_files.items():
            with open(index_path / filename, "w") as f:
                json.dump(content, f)
        # Create metadata file
        metadata = {"document_count": 5, "created_at": datetime.now().isoformat()}
        with open(index_path / "metadata.json", "w") as f:
            json.dump(metadata, f)

    # ===== Initialization Tests =====
    def test_initialization_test_mode(self):
        """Test service initialization in test mode."""
        assert self.service.api_key == "test_api_key"
        assert self.service.test_mode is True
        assert self.service.db is not None
        assert self.service.document_repo is not None
        assert self.service.vector_repo is not None
        assert self.service.vector_storage_dir.exists()
        assert self.service.cache_dir.exists()
        assert self.service.current_index is None
        assert self.service.current_document_id is None

    def test_initialization_production_mode(self):
        """Test service initialization in production mode (mocked)."""
        with patch(
            "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index"
        ):
            service = EnhancedRAGService(
                api_key="test_key", db_connection=self.db, test_mode=False
            )
            assert service.test_mode is False
            assert service.api_key == "test_key"

    def test_initialization_custom_storage_dir(self):
        """Test initialization with custom storage directory."""
        custom_dir = tempfile.mkdtemp()
        try:
            service = EnhancedRAGService(
                api_key="test_key",
                db_connection=self.db,
                vector_storage_dir=custom_dir,
                test_mode=True,
            )
            assert service.vector_storage_dir == Path(custom_dir)
            assert service.vector_storage_dir.exists()
        finally:
            shutil.rmtree(custom_dir)

    @patch("src.services.enhanced_rag_service.Settings")
    @patch("src.services.enhanced_rag_service.Gemini")
    @patch("src.services.enhanced_rag_service.GeminiEmbedding")
    def test_initialize_llama_index_success(
        self, mock_embedding, mock_gemini, mock_settings
    ):
        """Test successful LlamaIndex initialization."""
        # Create service without test mode to trigger initialization
        service = EnhancedRAGService(
            api_key="test_key", db_connection=self.db, test_mode=False
        )
        # Verify LlamaIndex components were configured
        mock_gemini.assert_called_once()
        mock_embedding.assert_called_once()

    def test_initialize_llama_index_import_error(self):
        """Test LlamaIndex initialization with import error."""
        with patch(
            "src.services.enhanced_rag_service.Settings",
            side_effect=ImportError("No module"),
        ):
            with pytest.raises(
                RAGServiceError, match="LlamaIndex dependencies not available"
            ):
                EnhancedRAGService(
                    api_key="test_key", db_connection=self.db, test_mode=False
                )

    def test_initialize_llama_index_configuration_error(self):
        """Test LlamaIndex initialization with configuration error."""
        with patch(
            "src.services.enhanced_rag_service.Settings",
            side_effect=Exception("Config error"),
        ):
            with pytest.raises(
                RAGServiceError, match="LlamaIndex initialization failed"
            ):
                EnhancedRAGService(
                    api_key="test_key", db_connection=self.db, test_mode=False
                )

    # ===== PDF Index Building Tests =====
    def test_build_index_from_pdf_test_mode(self):
        """Test PDF index building in test mode."""
        result = self.service.build_index_from_pdf(str(self.test_pdf_path))
        assert result is True
        assert self.service.current_pdf_path == str(self.test_pdf_path)

    def test_build_index_from_pdf_custom_cache_dir(self):
        """Test PDF index building with custom cache directory."""
        custom_cache = tempfile.mkdtemp()
        try:
            result = self.service.build_index_from_pdf(
                str(self.test_pdf_path), cache_dir=custom_cache
            )
            assert result is True
            assert Path(custom_cache).exists()
        finally:
            shutil.rmtree(custom_cache)

    @patch("src.services.enhanced_rag_service.VectorStoreIndex")
    @patch("src.services.enhanced_rag_service.PDFReader")
    def test_build_index_from_pdf_production_mode(self, mock_reader, mock_index):
        """Test PDF index building in production mode (mocked)."""
        # Create service in production mode
        with patch(
            "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index"
        ):
            service = EnhancedRAGService(
                api_key="test_key", db_connection=self.db, test_mode=False
            )
        # Mock successful PDF processing
        mock_reader.return_value.load_data.return_value = [
            MagicMock()
        ]  # Mock documents
        mock_index_instance = MagicMock()
        mock_index.from_documents.return_value = mock_index_instance
        result = service.build_index_from_pdf(str(self.test_pdf_path))
        assert result is True
        mock_reader.assert_called_once()
        mock_index.from_documents.assert_called_once()

    @patch("src.services.enhanced_rag_service.PDFReader")
    def test_build_index_from_pdf_no_content(self, mock_reader):
        """Test PDF index building when no content is extracted."""
        with patch(
            "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index"
        ):
            service = EnhancedRAGService(
                api_key="test_key", db_connection=self.db, test_mode=False
            )
        # Mock empty document extraction
        mock_reader.return_value.load_data.return_value = []
        result = service.build_index_from_pdf(str(self.test_pdf_path))
        assert result is False

    @patch("src.services.enhanced_rag_service.PDFReader")
    def test_build_index_from_pdf_exception(self, mock_reader):
        """Test PDF index building with exception."""
        with patch(
            "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index"
        ):
            service = EnhancedRAGService(
                api_key="test_key", db_connection=self.db, test_mode=False
            )
        # Mock exception during processing
        mock_reader.side_effect = Exception("PDF processing failed")
        result = service.build_index_from_pdf(str(self.test_pdf_path))
        assert result is False

    # ===== Document Index Building Tests =====
    def test_build_index_from_document_success(self):
        """Test successful document index building."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        with patch.object(self.service, "_get_chunk_count", return_value=10):
            vector_index = self.service.build_index_from_document(created_doc)
        assert vector_index is not None
        assert vector_index.id is not None
        assert vector_index.document_id == created_doc.id
        assert vector_index.chunk_count == 10
        assert Path(vector_index.index_path).exists()
        assert self.service.current_document_id == created_doc.id
        assert self.service.current_vector_index == vector_index

    def test_build_index_from_document_existing_index_no_overwrite(self):
        """Test building index when one already exists without overwrite."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Create first index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            self.service.build_index_from_document(created_doc)
        # Try to create second index without overwrite
        with pytest.raises(RAGIndexError, match="Vector index already exists"):
            self.service.build_index_from_document(created_doc, overwrite=False)

    def test_build_index_from_document_existing_index_with_overwrite(self):
        """Test building index when one already exists with overwrite."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Create first index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            vector_index1 = self.service.build_index_from_document(created_doc)
        # Create second index with overwrite
        with patch.object(self.service, "_get_chunk_count", return_value=10):
            vector_index2 = self.service.build_index_from_document(
                created_doc, overwrite=True
            )
        assert vector_index2.id == vector_index1.id  # Same record, updated
        assert vector_index2.chunk_count == 10

    def test_build_index_from_document_missing_file(self):
        """Test building index when document file doesn't exist."""
        document = self._create_test_document(file_path="/nonexistent/file.pdf")
        created_doc = self.service.document_repo.create(document)
        with pytest.raises(RAGIndexError, match="Document file not found"):
            self.service.build_index_from_document(created_doc)

    def test_build_index_from_document_build_failure(self):
        """Test building index when PDF processing fails."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        with patch.object(self.service, "build_index_from_pdf", return_value=False):
            with pytest.raises(RAGIndexError, match="Failed to build RAG index"):
                self.service.build_index_from_document(created_doc)

    @patch("src.services.enhanced_rag_service.ContentHashService.calculate_file_hash")
    def test_build_index_from_document_hash_error(self, mock_hash):
        """Test building index when hash calculation fails."""
        mock_hash.side_effect = ContentHashError("Hash failed")
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            vector_index = self.service.build_index_from_document(created_doc)
        # Should succeed with fallback hash
        assert vector_index is not None
        assert vector_index.index_hash.startswith("fallback_")

    # ===== Index Loading Tests =====
    def test_load_index_for_document_success(self):
        """Test successful index loading."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build index first
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            vector_index = self.service.build_index_from_document(created_doc)
        # Create mock index files
        self._create_mock_index_files(Path(vector_index.index_path))
        # Clear current state
        self.service.current_index = None
        self.service.current_document_id = None
        # Load index
        result = self.service.load_index_for_document(created_doc.id)
        assert result is True
        assert self.service.current_index is not None
        assert self.service.current_document_id == created_doc.id
        assert self.service.current_pdf_path == created_doc.file_path

    def test_load_index_for_document_not_found(self):
        """Test loading index for nonexistent document."""
        with pytest.raises(VectorIndexNotFoundError, match="Document not found"):
            self.service.load_index_for_document(99999)

    def test_load_index_for_document_no_index(self):
        """Test loading index when no vector index exists."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        with pytest.raises(VectorIndexNotFoundError, match="No vector index found"):
            self.service.load_index_for_document(created_doc.id)

    def test_load_index_for_document_missing_files(self):
        """Test loading index when index files are missing."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Create vector index record without files
        vector_index = VectorIndexModel(
            document_id=created_doc.id,
            index_path=str(Path(self.temp_storage_dir) / "missing_index"),
            index_hash="test_hash",
            chunk_count=5,
        )
        saved_index = self.service.vector_repo.create(vector_index)
        with pytest.raises(RAGIndexError, match="Vector index files missing"):
            self.service.load_index_for_document(created_doc.id)

    @patch("src.services.enhanced_rag_service.load_index_from_storage")
    @patch("src.services.enhanced_rag_service.StorageContext")
    def test_load_index_for_document_production_mode(self, mock_context, mock_load):
        """Test index loading in production mode."""
        # Create service in production mode
        with patch(
            "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index"
        ):
            service = EnhancedRAGService(
                api_key="test_key",
                db_connection=self.db,
                vector_storage_dir=self.temp_storage_dir,
                test_mode=False,
            )
        document = self._create_test_document()
        created_doc = service.document_repo.create(document)
        # Create vector index with files
        index_path = Path(self.temp_storage_dir) / "test_index"
        self._create_mock_index_files(index_path)
        vector_index = VectorIndexModel(
            document_id=created_doc.id,
            index_path=str(index_path),
            index_hash="test_hash",
            chunk_count=5,
        )
        service.vector_repo.create(vector_index)
        # Mock LlamaIndex components
        mock_index = MagicMock()
        mock_load.return_value = mock_index
        result = service.load_index_for_document(created_doc.id)
        assert result is True
        mock_context.from_defaults.assert_called_once()
        mock_load.assert_called_once()
        assert service.current_index == mock_index

    # ===== Query Tests =====
    def test_query_success(self):
        """Test successful query execution."""
        # Set up mock index
        self.service.current_index = MagicMock()
        response = self.service.query("What is artificial intelligence?")
        assert isinstance(response, str)
        assert "Test mode response" in response

    def test_query_no_index_loaded(self):
        """Test query when no index is loaded."""
        self.service.current_index = None
        with pytest.raises(RAGQueryError, match="No vector index loaded"):
            self.service.query("test query")

    @patch(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index"
    )
    def test_query_production_mode(self):
        """Test query execution in production mode."""
        service = EnhancedRAGService(
            api_key="test_key", db_connection=self.db, test_mode=False
        )
        # Set up mock index and query engine
        mock_index = MagicMock()
        mock_query_engine = MagicMock()
        mock_response = MagicMock()
        mock_response.__str__ = MagicMock(return_value="Production response")
        mock_index.as_query_engine.return_value = mock_query_engine
        mock_query_engine.query.return_value = mock_response
        service.current_index = mock_index
        response = service.query("test query")
        assert response == "Production response"
        mock_index.as_query_engine.assert_called_once()
        mock_query_engine.query.assert_called_once_with("test query")

    def test_query_document_success(self):
        """Test successful document querying."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build and set up index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            vector_index = self.service.build_index_from_document(created_doc)
        self._create_mock_index_files(Path(vector_index.index_path))
        response = self.service.query_document(
            "What is this document about?", created_doc.id
        )
        assert isinstance(response, str)
        assert "Test mode response" in response

    def test_query_document_auto_load_index(self):
        """Test document querying with automatic index loading."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build index but clear current state
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            vector_index = self.service.build_index_from_document(created_doc)
        self._create_mock_index_files(Path(vector_index.index_path))
        # Clear current state to force reload
        self.service.current_index = None
        self.service.current_document_id = None
        response = self.service.query_document("test query", created_doc.id)
        assert isinstance(response, str)
        assert self.service.current_document_id == created_doc.id

    def test_query_document_load_failure(self):
        """Test document querying when index loading fails."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # No vector index exists
        with pytest.raises(RAGQueryError, match="Failed to load index for query"):
            self.service.query_document("test query", created_doc.id)

    # ===== Status and Info Tests =====
    def test_get_cache_info_basic(self):
        """Test basic cache info retrieval."""
        info = self.service.get_cache_info()
        assert "cache_dir" in info
        assert "has_current_index" in info
        assert "current_pdf_path" in info
        assert "current_document_id" in info
        assert "test_mode" in info
        assert "cache_files_count" in info
        assert "cache_size_bytes" in info
        assert "vector_indexes_count" in info
        assert info["test_mode"] is True
        assert info["has_current_index"] is False

    def test_get_cache_info_with_index(self):
        """Test cache info with loaded index."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            self.service.build_index_from_document(created_doc)
        info = self.service.get_cache_info()
        assert info["has_current_index"] is True
        assert info["current_document_id"] == created_doc.id
        assert info["current_pdf_path"] == created_doc.file_path
        assert info["vector_indexes_count"] >= 1

    def test_get_cache_info_exception(self):
        """Test cache info retrieval with exception."""
        with patch.object(
            self.service.cache_dir, "exists", side_effect=Exception("FS error")
        ):
            info = self.service.get_cache_info()
            assert "error" in info

    def test_get_enhanced_cache_info(self):
        """Test enhanced cache info retrieval."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            self.service.build_index_from_document(created_doc)
        info = self.service.get_enhanced_cache_info()
        assert "vector_storage_dir" in info
        assert "current_document_id" in info
        assert "database_stats" in info
        assert "persistent_indexes" in info
        assert info["current_document_id"] == created_doc.id
        assert info["persistent_indexes"] >= 1

    def test_get_enhanced_cache_info_exception(self):
        """Test enhanced cache info with exception."""
        with patch.object(
            self.service.vector_repo,
            "get_index_statistics",
            side_effect=Exception("DB error"),
        ):
            info = self.service.get_enhanced_cache_info()
            assert "error" in info

    def test_get_document_index_status_with_index(self):
        """Test document index status when index exists."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            vector_index = self.service.build_index_from_document(created_doc)
        self._create_mock_index_files(Path(vector_index.index_path))
        status = self.service.get_document_index_status(created_doc.id)
        assert status["document_id"] == created_doc.id
        assert status["has_index"] is True
        assert status["index_valid"] is True
        assert status["can_query"] is True
        assert status["chunk_count"] == 5
        assert status["index_path"] == vector_index.index_path

    def test_get_document_index_status_no_index(self):
        """Test document index status when no index exists."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        status = self.service.get_document_index_status(created_doc.id)
        assert status["document_id"] == created_doc.id
        assert status["has_index"] is False
        assert status["index_valid"] is False
        assert status["can_query"] is False
        assert status["chunk_count"] == 0

    def test_get_document_index_status_invalid_files(self):
        """Test document index status with missing files."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Create vector index record without files
        vector_index = VectorIndexModel(
            document_id=created_doc.id,
            index_path=str(Path(self.temp_storage_dir) / "missing_index"),
            index_hash="test_hash",
            chunk_count=5,
        )
        self.service.vector_repo.create(vector_index)
        status = self.service.get_document_index_status(created_doc.id)
        assert status["has_index"] is True
        assert status["index_valid"] is False
        assert status["can_query"] is False

    def test_get_document_index_status_exception(self):
        """Test document index status with exception."""
        with patch.object(
            self.service.vector_repo,
            "find_by_document_id",
            side_effect=Exception("DB error"),
        ):
            status = self.service.get_document_index_status(1)
            assert "error" in status

    # ===== Index Management Tests =====
    def test_rebuild_index_success(self):
        """Test successful index rebuilding."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build initial index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            original_index = self.service.build_index_from_document(created_doc)
        # Rebuild index
        with patch.object(self.service, "_get_chunk_count", return_value=10):
            rebuilt_index = self.service.rebuild_index(created_doc.id)
        assert rebuilt_index is not None
        assert rebuilt_index.document_id == created_doc.id
        assert rebuilt_index.chunk_count == 10
        # Original index should be removed
        remaining_indexes = self.service.vector_repo.find_all()
        assert len(remaining_indexes) == 1
        assert remaining_indexes[0].id == rebuilt_index.id

    def test_rebuild_index_document_not_found(self):
        """Test rebuilding index for nonexistent document."""
        with pytest.raises(VectorIndexNotFoundError, match="Document not found"):
            self.service.rebuild_index(99999)

    def test_rebuild_index_no_existing_index(self):
        """Test rebuilding index when no existing index."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Rebuild without existing index
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            rebuilt_index = self.service.rebuild_index(created_doc.id)
        assert rebuilt_index is not None
        assert rebuilt_index.document_id == created_doc.id

    def test_cleanup_orphaned_indexes(self):
        """Test cleanup of orphaned indexes."""
        with patch.object(
            self.service.vector_repo, "cleanup_orphaned_indexes", return_value=3
        ):
            removed_count = self.service.cleanup_orphaned_indexes()
            assert removed_count == 3

    def test_cleanup_orphaned_indexes_exception(self):
        """Test cleanup with exception."""
        with patch.object(
            self.service.vector_repo,
            "cleanup_orphaned_indexes",
            side_effect=Exception("Cleanup failed"),
        ):
            with pytest.raises(EnhancedRAGServiceError, match="Cleanup failed"):
                self.service.cleanup_orphaned_indexes()

    # ===== Helper Methods Tests =====
    def test_verify_index_files_valid(self):
        """Test index file verification with valid files."""
        index_path = Path(self.temp_storage_dir) / "test_index"
        self._create_mock_index_files(index_path)
        result = self.service._verify_index_files(str(index_path))
        assert result is True

    def test_verify_index_files_missing_directory(self):
        """Test index file verification with missing directory."""
        result = self.service._verify_index_files("/nonexistent/path")
        assert result is False

    def test_verify_index_files_missing_required_files(self):
        """Test index file verification with missing required files."""
        index_path = Path(self.temp_storage_dir) / "incomplete_index"
        index_path.mkdir()
        # Create only some required files
        (index_path / "default__vector_store.json").touch()
        # Missing graph_store.json and index_store.json
        result = self.service._verify_index_files(str(index_path))
        assert result is False

    def test_verify_index_files_exception(self):
        """Test index file verification with exception."""
        # Pass invalid argument type to trigger exception
        result = self.service._verify_index_files(None)
        assert result is False

    def test_copy_index_files_success(self):
        """Test successful index file copying."""
        source_dir = Path(self.temp_storage_dir) / "source"
        dest_dir = Path(self.temp_storage_dir) / "dest"
        # Create source files
        self._create_mock_index_files(source_dir)
        dest_dir.mkdir()
        self.service._copy_index_files(source_dir, dest_dir)
        # Verify files were copied
        assert (dest_dir / "default__vector_store.json").exists()
        assert (dest_dir / "graph_store.json").exists()
        assert (dest_dir / "index_store.json").exists()
        assert (dest_dir / "metadata.json").exists()

    def test_copy_index_files_with_subdirectory(self):
        """Test index file copying with subdirectories."""
        source_dir = Path(self.temp_storage_dir) / "source"
        dest_dir = Path(self.temp_storage_dir) / "dest"
        # Create source with subdirectory
        source_dir.mkdir()
        subdir = source_dir / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").write_text("test content")
        (source_dir / "main.json").write_text("{}")
        dest_dir.mkdir()
        self.service._copy_index_files(source_dir, dest_dir)
        assert (dest_dir / "main.json").exists()
        assert (dest_dir / "subdir" / "subfile.txt").exists()

    def test_copy_index_files_exception(self):
        """Test index file copying with exception."""
        source_dir = Path("/nonexistent/source")
        dest_dir = Path(self.temp_storage_dir) / "dest"
        dest_dir.mkdir()
        with pytest.raises(Exception):
            self.service._copy_index_files(source_dir, dest_dir)

    def test_get_chunk_count_from_metadata(self):
        """Test chunk count extraction from metadata file."""
        index_path = Path(self.temp_storage_dir) / "test_index"
        self._create_mock_index_files(index_path)
        chunk_count = self.service._get_chunk_count(str(index_path))
        assert chunk_count == 5  # From metadata.json

    def test_get_chunk_count_from_vector_store(self):
        """Test chunk count extraction from vector store file."""
        index_path = Path(self.temp_storage_dir) / "test_index"
        index_path.mkdir()
        # Create vector store without metadata
        vector_store_data = {
            "embedding_dict": {f"chunk_{i}": [0.1] * 384 for i in range(7)}
        }
        with open(index_path / "default__vector_store.json", "w") as f:
            json.dump(vector_store_data, f)
        chunk_count = self.service._get_chunk_count(str(index_path))
        assert chunk_count == 7

    def test_get_chunk_count_no_files(self):
        """Test chunk count extraction when no files exist."""
        index_path = Path(self.temp_storage_dir) / "empty_index"
        index_path.mkdir()
        chunk_count = self.service._get_chunk_count(str(index_path))
        assert chunk_count == 0

    def test_get_chunk_count_invalid_json(self):
        """Test chunk count extraction with invalid JSON."""
        index_path = Path(self.temp_storage_dir) / "invalid_index"
        index_path.mkdir()
        # Create invalid JSON file
        with open(index_path / "metadata.json", "w") as f:
            f.write("invalid json {")
        chunk_count = self.service._get_chunk_count(str(index_path))
        assert chunk_count == 0

    def test_cleanup_index_files(self):
        """Test index file cleanup."""
        index_path = Path(self.temp_storage_dir) / "cleanup_test"
        self._create_mock_index_files(index_path)
        assert index_path.exists()
        self.service._cleanup_index_files(str(index_path))
        assert not index_path.exists()

    def test_cleanup_index_files_nonexistent(self):
        """Test cleanup of nonexistent index files."""
        # Should not raise exception
        self.service._cleanup_index_files("/nonexistent/path")

    def test_create_mock_index(self):
        """Test mock index creation for testing."""
        mock_index = self.service._create_mock_index(123)
        assert mock_index is not None
        # Test that mock index can be queried
        query_engine = mock_index.as_query_engine()
        response = query_engine.query("test query")
        response_str = str(response)
        assert "Mock response for document 123" in response_str
        assert "test query" in response_str

    # ===== Integration Tests =====
    def test_full_rag_workflow(self):
        """Test complete RAG workflow: build, load, query."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Build index
        with patch.object(self.service, "_get_chunk_count", return_value=10):
            vector_index = self.service.build_index_from_document(created_doc)
        self._create_mock_index_files(Path(vector_index.index_path))
        # Verify index status
        status = self.service.get_document_index_status(created_doc.id)
        assert status["can_query"] is True
        # Query document
        response = self.service.query_document(
            "What is this document about?", created_doc.id
        )
        assert isinstance(response, str)
        assert "Test mode response" in response
        # Get cache info
        cache_info = self.service.get_enhanced_cache_info()
        assert cache_info["persistent_indexes"] >= 1
        # Rebuild index
        with patch.object(self.service, "_get_chunk_count", return_value=15):
            rebuilt_index = self.service.rebuild_index(created_doc.id)
        assert rebuilt_index.chunk_count == 15

    def test_multiple_documents_workflow(self):
        """Test workflow with multiple documents."""
        # Create multiple documents
        documents = []
        for i in range(3):
            pdf_path = Path(tempfile.mktemp(suffix=f"_{i}.pdf"))
            pdf_path.write_text(f"content for document {i}")
            doc = self._create_test_document(
                title=f"Document {i}", file_path=str(pdf_path)
            )
            created_doc = self.service.document_repo.create(doc)
            documents.append((created_doc, pdf_path))
        try:
            # Build indexes for all documents
            vector_indexes = []
            for doc, _ in documents:
                with patch.object(self.service, "_get_chunk_count", return_value=5):
                    vector_index = self.service.build_index_from_document(doc)
                self._create_mock_index_files(Path(vector_index.index_path))
                vector_indexes.append(vector_index)
            # Query each document
            responses = []
            for doc, _ in documents:
                response = self.service.query_document(f"Query for {doc.title}", doc.id)
                responses.append(response)
                assert isinstance(response, str)
            # Verify cache info shows multiple indexes
            cache_info = self.service.get_enhanced_cache_info()
            assert cache_info["persistent_indexes"] == 3
            # Test index switching
            first_doc, _ = documents[0]
            last_doc, _ = documents[-1]
            # Query first document
            self.service.query_document("First query", first_doc.id)
            assert self.service.current_document_id == first_doc.id
            # Query last document (should switch indexes)
            self.service.query_document("Last query", last_doc.id)
            assert self.service.current_document_id == last_doc.id
        finally:
            # Clean up test files
            for _, pdf_path in documents:
                if pdf_path.exists():
                    pdf_path.unlink()

    def test_error_recovery_workflow(self):
        """Test error recovery in various scenarios."""
        document = self._create_test_document()
        created_doc = self.service.document_repo.create(document)
        # Test query without index (should fail gracefully)
        with pytest.raises(RAGQueryError):
            self.service.query_document("test query", created_doc.id)
        # Build index but with corrupted files
        with patch.object(self.service, "_get_chunk_count", return_value=5):
            vector_index = self.service.build_index_from_document(created_doc)
        # Create incomplete index files
        index_path = Path(vector_index.index_path)
        index_path.mkdir(exist_ok=True)
        (index_path / "default__vector_store.json").touch()  # Only one file
        # Try to load corrupted index (should fail)
        with pytest.raises(RAGIndexError):
            self.service.load_index_for_document(created_doc.id)
        # Rebuild index (should recover)
        with patch.object(self.service, "_get_chunk_count", return_value=7):
            rebuilt_index = self.service.rebuild_index(created_doc.id)
        self._create_mock_index_files(Path(rebuilt_index.index_path))
        # Now querying should work
        response = self.service.query_document("recovery test", created_doc.id)
        assert isinstance(response, str)
