"""
Enhanced RAG Service Module
This module provides an enhanced RAG service that integrates with the document library
database system. It extends the original RAG service with persistent vector index
management and database integration.
"""

import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union


# Define base RAG exceptions
class RAGServiceError(Exception):
    """Base exception for RAG service errors."""

    pass


class RAGIndexError(RAGServiceError):
    """Exception for RAG index related errors."""

    pass


class RAGQueryError(RAGServiceError):
    """Exception for RAG query related errors."""

    pass


from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel, VectorIndexModel
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from src.services.content_hash_service import ContentHashError, ContentHashService

logger = logging.getLogger(__name__)


class EnhancedRAGServiceError(RAGServiceError):
    """Base exception for enhanced RAG service errors."""

    pass


class VectorIndexNotFoundError(EnhancedRAGServiceError):
    """Raised when vector index is not found for a document."""

    pass


class EnhancedRAGService:
    """
    {
        "name": "EnhancedRAGService",
        "version": "2.0.0",
        "description": "Complete standalone RAG service with database integration and vector index management.",
        "dependencies": ["DatabaseConnection", "DocumentRepository", "VectorIndexRepository", "LlamaIndex", "Google Gemini API"],
        "interface": {
            "inputs": [
                {"name": "api_key", "type": "string"},
                {"name": "db_connection", "type": "DatabaseConnection"}
            ],
            "outputs": "Complete RAG functionality with database persistence and Gemini integration"
        }
    }
    Complete standalone RAG service that provides comprehensive document indexing and querying.
    This class is a self-contained RAG implementation that combines:
    - LlamaIndex integration with Google Gemini LLM and embeddings
    - Database persistence for documents and vector indexes
    - Intelligent vector index management and caching
    - Thread-safe operations with connection pooling
    - Comprehensive error handling and logging
    The service manages the complete RAG workflow:
    1. PDF document ingestion and chunking
    2. Vector embedding generation using Gemini
    3. Persistent storage of vector indexes
    4. Query processing with context retrieval
    5. Response generation using Gemini LLM
    """

    def __init__(
        self,
        api_key: str,
        db_connection: DatabaseConnection,
        vector_storage_dir: str = "vector_indexes",
        test_mode: bool = False,
    ) -> None:
        """
        Initialize enhanced RAG service with database integration.
        Args:
            api_key: Google Gemini API key
            db_connection: Database connection instance
            vector_storage_dir: Directory for storing vector indexes
            test_mode: If True, skip actual API initialization for testing
        """
        # Store API key and configuration
        self.api_key = api_key
        self.test_mode = test_mode
        # RAG service attributes (previously from base class)
        self.current_index = None
        self.current_pdf_path: Optional[str] = None
        self.cache_dir = Path(".rag_cache")
        self.cache_dir.mkdir(exist_ok=True)
        # Database integration
        self.db = db_connection
        self.document_repo = DocumentRepository(db_connection)
        self.vector_repo = VectorIndexRepository(db_connection)
        # Vector storage configuration
        self.vector_storage_dir = Path(vector_storage_dir)
        self.vector_storage_dir.mkdir(exist_ok=True)
        # Current state
        self.current_document_id: Optional[int] = None
        self.current_vector_index: Optional[VectorIndexModel] = None
        # Initialize LlamaIndex components if not in test mode
        if not test_mode:
            self._initialize_llama_index()
        logger.info(
            f"Enhanced RAG service initialized with vector storage: {vector_storage_dir}"
        )

    def _initialize_llama_index(self) -> None:
        """Initialize LlamaIndex components with Gemini integration."""
        try:
            import os

            os.environ["GOOGLE_API_KEY"] = self.api_key
            from llama_index.core import Settings
            from llama_index.embeddings.gemini import GeminiEmbedding
            from llama_index.llms.gemini import Gemini

            # Configure LLM
            Settings.llm = Gemini(model="models/gemini-1.5-pro", api_key=self.api_key)
            # Configure embeddings
            Settings.embed_model = GeminiEmbedding(
                model_name="models/embedding-001", api_key=self.api_key
            )
            logger.info("LlamaIndex initialized with Gemini integration")
        except ImportError as e:
            logger.error(f"Failed to import LlamaIndex components: {e}")
            raise RAGServiceError(f"LlamaIndex dependencies not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize LlamaIndex: {e}")
            raise RAGServiceError(f"LlamaIndex initialization failed: {e}")

    def build_index_from_pdf(
        self, pdf_path: str, cache_dir: Optional[str] = None
    ) -> bool:
        """
        Build vector index from PDF file using LlamaIndex.
        Args:
            pdf_path: Path to PDF file
            cache_dir: Directory to store the index (defaults to self.cache_dir)
        Returns:
            True if index was built successfully, False otherwise
        """
        try:
            if self.test_mode:
                logger.info(f"Test mode: Simulating index build for {pdf_path}")
                return True
            from llama_index.core import (
                SimpleDirectoryReader,
                StorageContext,
                VectorStoreIndex,
            )
            from llama_index.readers.file import PDFReader

            # Use provided cache_dir or default
            storage_dir = Path(cache_dir) if cache_dir else self.cache_dir
            storage_dir.mkdir(exist_ok=True)
            # Load PDF document
            reader = PDFReader()
            documents = reader.load_data(file=Path(pdf_path))
            if not documents:
                logger.error(f"No content extracted from PDF: {pdf_path}")
                return False
            # Create vector index
            index = VectorStoreIndex.from_documents(documents)
            # Persist to storage
            storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
            index.storage_context = storage_context
            index.storage_context.persist(persist_dir=str(storage_dir))
            # Store current index
            self.current_index = index
            self.current_pdf_path = pdf_path
            logger.info(f"Vector index built successfully for {pdf_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to build index from PDF {pdf_path}: {e}")
            return False

    def query(self, query_text: str) -> str:
        """
        Query the current vector index.
        Args:
            query_text: User query string
        Returns:
            RAG response string
        Raises:
            RAGQueryError: If no index is loaded or query fails
        """
        if not self.current_index:
            raise RAGQueryError("No vector index loaded. Build or load an index first.")
        try:
            if self.test_mode:
                return f"Test mode response for query: {query_text}"
            # Create query engine
            query_engine = self.current_index.as_query_engine()
            # Execute query
            response = query_engine.query(query_text)
            return str(response)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise RAGQueryError(f"Failed to execute query: {e}")

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache and index status.
        Returns:
            Dictionary with cache information
        """
        try:
            cache_info = {
                "cache_dir": str(self.cache_dir),
                "has_current_index": self.current_index is not None,
                "current_pdf_path": self.current_pdf_path,
                "current_document_id": self.current_document_id,
                "test_mode": self.test_mode,
            }
            # Add cache directory statistics
            if self.cache_dir.exists():
                cache_files = list(self.cache_dir.glob("*"))
                cache_info["cache_files_count"] = len(cache_files)
                cache_info["cache_size_bytes"] = sum(
                    f.stat().st_size for f in cache_files if f.is_file()
                )
            else:
                cache_info["cache_files_count"] = 0
                cache_info["cache_size_bytes"] = 0
            # Add vector storage info
            if self.vector_storage_dir.exists():
                vector_dirs = [
                    d for d in self.vector_storage_dir.iterdir() if d.is_dir()
                ]
                cache_info["vector_indexes_count"] = len(vector_dirs)
            else:
                cache_info["vector_indexes_count"] = 0
            return cache_info
        except Exception as e:
            logger.error(f"Failed to get cache info: {e}")
            return {"error": str(e)}

    def build_index_from_document(
        self, document: DocumentModel, overwrite: bool = False
    ) -> VectorIndexModel:
        """
        Build vector index from a document model and persist to database.
        Args:
            document: Document model from database
            overwrite: If True, overwrite existing index
        Returns:
            Created vector index model
        Raises:
            RAGIndexError: If index building fails or index already exists
        """
        logger.info(f"Building index for document {document.id}: {document.title}")
        # Check if vector index already exists
        existing_index = self.vector_repo.find_by_document_id(document.id)
        if existing_index and not overwrite:
            raise RAGIndexError(
                f"Vector index already exists for document {document.id}"
            )
        # Validate document file exists
        if not document.file_path or not Path(document.file_path).exists():
            raise RAGIndexError(f"Document file not found: {document.file_path}")
        # Create a temporary directory to build the index
        with tempfile.TemporaryDirectory() as temp_dir:
            # Build index in temporary directory
            success = self.build_index_from_pdf(document.file_path, cache_dir=temp_dir)
            if not success:
                raise RAGIndexError(
                    f"Failed to build RAG index for document {document.id}"
                )
            # Calculate index hash for integrity verification
            try:
                index_hash = ContentHashService.calculate_file_hash(document.file_path)
            except ContentHashError as e:
                logger.warning(f"Could not calculate index hash: {e}")
                index_hash = f"fallback_{document.id}_{datetime.now().timestamp()}"
            # Create persistent vector index directory
            vector_index_path = (
                self.vector_storage_dir / f"doc_{document.id}_{index_hash[:8]}"
            )
            if vector_index_path.exists():
                shutil.rmtree(vector_index_path)
            vector_index_path.mkdir(exist_ok=True)
            # Copy index files from temp to permanent storage
            self._copy_index_files(Path(temp_dir), vector_index_path)
            # Get document count for metadata
            chunk_count = self._get_chunk_count(str(vector_index_path))
            # Create or update vector index record in database
            if existing_index:
                vector_index = existing_index
                vector_index.index_path = str(vector_index_path)
                vector_index.index_hash = index_hash
                vector_index.chunk_count = chunk_count
                vector_index.created_at = datetime.now()
                saved_index = self.vector_repo.update(vector_index)
            else:
                vector_index = VectorIndexModel(
                    document_id=document.id,
                    index_path=str(vector_index_path),
                    index_hash=index_hash,
                    chunk_count=chunk_count,
                )
                saved_index = self.vector_repo.create(vector_index)
            # Update current state
            self.current_document_id = document.id
            self.current_vector_index = saved_index
            logger.info(
                f"Vector index for document {document.id} built successfully: {saved_index.id}"
            )
            return saved_index

    def load_index_for_document(self, document_id: int) -> bool:
        """
        Load vector index for a specific document.
        Args:
            document_id: Document ID to load index for
        Returns:
            True if index loaded successfully
        Raises:
            VectorIndexNotFoundError: If no index found for document
            RAGIndexError: If loading fails
        """
        logger.info(f"Loading vector index for document {document_id}")
        # Get document
        document = self.document_repo.find_by_id(document_id)
        if not document:
            raise VectorIndexNotFoundError(f"Document not found: {document_id}")
        # Get vector index
        vector_index = self.vector_repo.find_by_document_id(document_id)
        if not vector_index:
            raise VectorIndexNotFoundError(
                f"No vector index found for document {document_id}"
            )
        # Verify index files exist
        if not self._verify_index_files(vector_index.index_path):
            raise RAGIndexError(
                f"Vector index files missing: {vector_index.index_path}"
            )
        # Load index using base RAG service
        if not self.test_mode:
            from llama_index.core import StorageContext, load_index_from_storage

            storage_context = StorageContext.from_defaults(
                persist_dir=vector_index.index_path
            )
            self.current_index = load_index_from_storage(storage_context)
        else:
            # Test mode: create mock index
            self.current_index = self._create_mock_index(document_id)
        # Update current state
        self.current_pdf_path = document.file_path
        self.current_document_id = document_id
        self.current_vector_index = vector_index
        # Update document access time
        self.document_repo.update_access_time(document_id)
        logger.info(f"Vector index loaded successfully for document {document_id}")
        return True

    def query_document(self, query: str, document_id: int) -> str:
        """
        Query a specific document using its vector index.
        Args:
            query: User query
            document_id: Document ID to query
        Returns:
            RAG response string
        Raises:
            RAGQueryError: If query fails
        """
        logger.info(f"Querying document {document_id} with query: {query[:100]}...")
        # Load index if not current or different document
        if self.current_document_id != document_id or not self.current_index:
            try:
                self.load_index_for_document(document_id)
            except (VectorIndexNotFoundError, RAGIndexError) as e:
                raise RAGQueryError(f"Failed to load index for query: {e}")
        # Execute query using base RAG service
        response = self.query(query)
        logger.info(f"Query completed for document {document_id}")
        return response

    def get_document_index_status(self, document_id: int) -> Dict[str, Any]:
        """
        Get the indexing status for a document.
        Args:
            document_id: Document ID to check
        Returns:
            Dictionary with index status information
        """
        try:
            status = {
                "document_id": document_id,
                "has_index": False,
                "index_valid": False,
                "index_path": None,
                "chunk_count": 0,
                "created_at": None,
                "can_query": False,
            }
            # Check if vector index exists
            vector_index = self.vector_repo.find_by_document_id(document_id)
            if vector_index:
                status["has_index"] = True
                status["index_path"] = vector_index.index_path
                status["chunk_count"] = vector_index.chunk_count or 0
                status["created_at"] = vector_index.created_at
                # Verify index files
                status["index_valid"] = self._verify_index_files(
                    vector_index.index_path
                )
                status["can_query"] = status["index_valid"]
            return status
        except Exception as e:
            logger.error(f"Failed to get index status for document {document_id}: {e}")
            return {"document_id": document_id, "error": str(e)}

    def rebuild_index(self, document_id: int) -> VectorIndexModel:
        """
        Rebuild vector index for a document.
        Args:
            document_id: Document ID to rebuild index for
        Returns:
            New vector index model
        """
        logger.info(f"Rebuilding index for document {document_id}")
        # Get document
        document = self.document_repo.find_by_id(document_id)
        if not document:
            raise VectorIndexNotFoundError(f"Document not found: {document_id}")
        # Remove existing index if present
        existing_index = self.vector_repo.find_by_document_id(document_id)
        if existing_index:
            self._cleanup_index_files(existing_index.index_path)
            self.vector_repo.delete(existing_index.id)
        # Build new index
        return self.build_index_from_document(document, overwrite=True)

    def cleanup_orphaned_indexes(self) -> int:
        """
        Clean up orphaned vector indexes that have no corresponding documents.
        Returns:
            Number of orphaned indexes cleaned up
        """
        try:
            logger.info("Cleaning up orphaned vector indexes")
            return self.vector_repo.cleanup_orphaned_indexes()
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned indexes: {e}")
            raise EnhancedRAGServiceError(f"Cleanup failed: {e}") from e

    def get_enhanced_cache_info(self) -> Dict[str, Any]:
        """
        Get enhanced cache information including database statistics.
        Returns:
            Dictionary with comprehensive cache information
        """
        try:
            # Get base cache info
            cache_info = self.get_cache_info()
            # Add database statistics
            vector_stats = self.vector_repo.get_index_statistics()
            cache_info.update(
                {
                    "vector_storage_dir": str(self.vector_storage_dir),
                    "current_document_id": self.current_document_id,
                    "database_stats": vector_stats,
                    "persistent_indexes": vector_stats.get("total_indexes", 0),
                }
            )
            return cache_info
        except Exception as e:
            logger.error(f"Failed to get enhanced cache info: {e}")
            return {"error": str(e)}

    # Private helper methods
    def _load_existing_index(
        self, document: DocumentModel, vector_index: VectorIndexModel
    ) -> VectorIndexModel:
        """Load an existing vector index."""
        try:
            if not self.test_mode:
                from llama_index.core import StorageContext, load_index_from_storage

                storage_context = StorageContext.from_defaults(
                    persist_dir=vector_index.index_path
                )
                self.current_index = load_index_from_storage(storage_context)
            else:
                # Test mode: create mock index
                self.current_index = type(
                    "MockIndex",
                    (),
                    {
                        "as_query_engine": lambda **kwargs: type(
                            "MockQueryEngine",
                            (),
                            {
                                "query": lambda prompt: type(
                                    "MockResponse",
                                    (),
                                    {
                                        "__str__": lambda: f"Mock response for existing document {document.id}: {prompt}"
                                    },
                                )()
                            },
                        )()
                    },
                )()
            # Update current state
            self.current_pdf_path = document.file_path
            self.current_document_id = document.id
            self.current_vector_index = vector_index
            logger.info(f"Loaded existing vector index for document {document.id}")
            return vector_index
        except Exception as e:
            logger.error(f"Failed to load existing index: {e}")
            raise

    def _create_mock_index(self, document_id: int) -> Any:
        """
        Helper to create a mock index for testing purposes.
        """
        return type(
            "MockIndex",
            (),
            {
                "as_query_engine": lambda **kwargs: type(
                    "MockQueryEngine",
                    (),
                    {
                        "query": lambda prompt: type(
                            "MockResponse",
                            (),
                            {
                                "__str__": lambda: f"Mock response for document {document_id}: {prompt}"
                            },
                        )()
                    },
                )()
            },
        )()

    def _verify_index_files(self, index_path: str) -> bool:
        """Verify that all required index files exist."""
        try:
            path = Path(index_path)
            if not path.exists():
                return False
            required_files = [
                "default__vector_store.json",
                "graph_store.json",
                "index_store.json",
            ]
            return all((path / file_name).exists() for file_name in required_files)
        except Exception:
            return False

    def _copy_index_files(self, source_path: Path, dest_path: Path) -> None:
        """Copy index files from source to destination."""
        try:
            for item in source_path.iterdir():
                if item.is_file():
                    shutil.copy2(item, dest_path / item.name)
                elif item.is_dir():
                    shutil.copytree(item, dest_path / item.name, dirs_exist_ok=True)
            logger.debug(f"Copied index files from {source_path} to {dest_path}")
        except Exception as e:
            logger.error(f"Failed to copy index files: {e}")
            raise

    def _get_chunk_count(self, index_path: str) -> int:
        """Get the number of chunks in the index."""
        try:
            # Try to read metadata.json if it exists
            metadata_path = Path(index_path) / "metadata.json"
            if metadata_path.exists():
                import json

                with open(metadata_path, "r") as f:
                    metadata = json.load(f)
                    return int(metadata.get("document_count", 0))
            # Fallback: estimate from vector store file
            vector_store_path = Path(index_path) / "default__vector_store.json"
            if vector_store_path.exists():
                import json

                with open(vector_store_path, "r") as f:
                    data = json.load(f)
                    # Estimate chunk count from vector store data
                    return len(data.get("embedding_dict", {}))
            return 0
        except Exception as e:
            logger.warning(f"Could not determine chunk count: {e}")
            return 0

    def _cleanup_index_files(self, index_path: str) -> None:
        """Clean up index files at the given path."""
        try:
            path = Path(index_path)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                logger.debug(f"Cleaned up index files at {index_path}")
        except Exception as e:
            logger.warning(f"Could not cleanup index files at {index_path}: {e}")
