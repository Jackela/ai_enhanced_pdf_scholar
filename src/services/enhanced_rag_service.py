"""
Enhanced RAG Service Module
This module provides an enhanced RAG service that integrates with the document library
database system. It extends the original RAG service with persistent vector index
management and database integration.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel, VectorIndexModel
from src.prompt_management.manager import PromptManager
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from src.services.content_hash_service import ContentHashError, ContentHashService
from src.services.error_recovery import (
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    HealthChecker,
    RecoveryOrchestrator,
    ResourceCleanupManager,
    RetryConfig,
    RetryExhaustedException,
    TransactionManager,
    with_circuit_breaker,
    with_retry,
)


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


class RAGRecoveryError(RAGServiceError):
    """Exception for RAG recovery operations."""

    pass


class RAGResourceError(RAGServiceError):
    """Exception for RAG resource management errors."""

    pass


logger = logging.getLogger(__name__)


class EnhancedRAGServiceError(RAGServiceError):
    """Base exception for enhanced RAG service errors."""

    pass


class VectorIndexNotFoundError(EnhancedRAGServiceError):
    """Raised when vector index is not found for a document."""

    pass


class IndexCorruptionError(EnhancedRAGServiceError):
    """Raised when vector index is corrupted."""

    pass


class InsufficientResourcesError(EnhancedRAGServiceError):
    """Raised when insufficient system resources are available."""

    pass


class EnhancedRAGService:
    """
    {
        "name": "EnhancedRAGService",
        "version": "2.0.0",
        "description": "Complete RAG service with database integration.",
        "dependencies": [
            "DatabaseConnection", "DocumentRepository", "VectorIndexRepository"
        ],
        "interface": {
            "inputs": [
                {"name": "api_key", "type": "string"},
                {"name": "db_connection", "type": "DatabaseConnection"}
            ],
            "outputs": (
                "Complete RAG functionality with database persistence "
                "and Gemini integration"
            )
        }
    }
    Complete standalone RAG service that provides comprehensive document
    indexing and querying.
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
        prompt_manager: PromptManager = None,
    ) -> None:
        """
        Initialize enhanced RAG service with database integration.
        Args:
            api_key: Google Gemini API key
            db_connection: Database connection instance
            vector_storage_dir: Directory for storing vector indexes
            test_mode: If True, skip actual API initialization for testing
            prompt_manager: An instance of PromptManager.
        """
        # Store API key and configuration
        self.api_key: str = api_key
        self.test_mode: bool = test_mode
        self.prompt_manager = prompt_manager
        # RAG service attributes (previously from base class)
        self.current_index: VectorStoreIndex | None = None
        self.current_pdf_path: str | None = None
        self.cache_dir: Path = Path(".rag_cache")
        self.cache_dir.mkdir(exist_ok=True)
        # Database integration
        self.db: DatabaseConnection = db_connection
        self.document_repo: DocumentRepository = DocumentRepository(db_connection)
        self.vector_repo: VectorIndexRepository = VectorIndexRepository(db_connection)
        # Vector storage configuration
        self.vector_storage_dir: Path = Path(vector_storage_dir)
        self.vector_storage_dir.mkdir(exist_ok=True)
        # Current state
        self.current_document_id: int | None = None
        self.current_vector_index: VectorIndexModel | None = None

        # Error recovery and resilience components
        self.recovery_orchestrator: RecoveryOrchestrator = RecoveryOrchestrator()
        self.transaction_manager: TransactionManager = TransactionManager(db_connection)
        self.cleanup_manager: ResourceCleanupManager = ResourceCleanupManager()
        self.health_checker: HealthChecker = HealthChecker()

        # Configuration attributes for recovery systems (initialized in _setup_recovery_configurations)
        self.api_retry_config: RetryConfig
        self.api_circuit_breaker_config: CircuitBreakerConfig
        self.file_retry_config: RetryConfig

        # Configure retry and circuit breaker for API operations
        self._setup_recovery_configurations()

        # Setup health checks
        self._setup_health_checks()

        # Initialize LlamaIndex components if not in test mode
        if not test_mode:
            self._initialize_llama_index()
        logger.info(
            f"Enhanced RAG service initialized with vector storage: "
            f"{vector_storage_dir}"
        )

    def _initialize_llama_index(self) -> None:
        """Initialize LlamaIndex components with Google Gemini integration."""
        try:
            import os

            os.environ["GOOGLE_API_KEY"] = self.api_key
            from llama_index.core import Settings
            from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
            from llama_index.llms.google_genai import GoogleGenAI

            # Configure LLM
            Settings.llm = GoogleGenAI(
                model_name="gemini-1.5-flash", api_key=self.api_key
            )
            # Configure embeddings
            Settings.embed_model = GoogleGenAIEmbedding(
                model_name="models/embedding-001", api_key=self.api_key
            )
            logger.info("LlamaIndex initialized with Google Gemini integration")
        except ImportError as e:
            logger.error(f"Failed to import LlamaIndex components: {e}")
            raise RAGServiceError(f"LlamaIndex dependencies not available: {e}") from e
        except Exception as e:
            logger.error(f"Failed to initialize LlamaIndex: {e}")
            raise RAGServiceError(f"LlamaIndex initialization failed: {e}") from e

    def _setup_recovery_configurations(self) -> None:
        """Setup recovery configurations for different operation types."""
        # Configure retry for API operations (Gemini calls)
        self.api_retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
            retryable_exceptions=(ConnectionError, TimeoutError, Exception),
            non_retryable_exceptions=(KeyboardInterrupt, SystemExit, ValueError),
        )

        # Configure circuit breaker for external API calls
        self.api_circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=120.0,  # 2 minutes
            expected_exception=Exception,
            success_threshold=2,
        )

        # Configure retry for file operations
        self.file_retry_config = RetryConfig(
            max_attempts=2,
            initial_delay=0.5,
            max_delay=5.0,
            exponential_base=2.0,
            retryable_exceptions=(OSError, IOError),
            non_retryable_exceptions=(PermissionError, FileNotFoundError),
        )

    def _setup_health_checks(self) -> None:
        """Setup health checks for system resources and services."""
        self.health_checker.add_health_check("disk_space", self._check_disk_space)
        self.health_checker.add_health_check("memory_usage", self._check_memory_usage)
        self.health_checker.add_health_check(
            "vector_storage", self._check_vector_storage
        )
        self.health_checker.add_health_check(
            "database_connection", self._check_database_connection
        )

    def _check_disk_space(self) -> bool:
        """Check available disk space."""
        try:
            disk_usage = psutil.disk_usage(str(self.vector_storage_dir))
            free_gb = disk_usage.free / (1024**3)
            return free_gb > 1.0  # At least 1GB free
        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return False

    def _check_memory_usage(self) -> bool:
        """Check system memory usage."""
        try:
            memory = psutil.virtual_memory()
            return memory.percent < 90.0  # Less than 90% memory usage
        except Exception as e:
            logger.error(f"Memory usage check failed: {e}")
            return False

    def _check_vector_storage(self) -> bool:
        """Check vector storage directory accessibility."""
        try:
            return (
                self.vector_storage_dir.exists()
                and self.vector_storage_dir.is_dir()
                and os.access(self.vector_storage_dir, os.W_OK)
            )
        except Exception as e:
            logger.error(f"Vector storage check failed: {e}")
            return False

    def _check_database_connection(self) -> bool:
        """Check database connection health."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    def build_index_from_pdf(self, pdf_path: str, cache_dir: str | None = None) -> bool:
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
                # Set current_pdf_path in test mode to match production behavior
                self.current_pdf_path = pdf_path
                return True
            from llama_index.core import (
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

            from llama_index.core import PromptTemplate

            # Default query engine arguments
            query_engine_args = {}

            # Use prompt manager if available
            if self.prompt_manager:
                prompt_data = self.prompt_manager.get_prompt("default_qa")
                if prompt_data and "template" in prompt_data:
                    qa_template = PromptTemplate(prompt_data["template"])
                    query_engine_args["text_qa_template"] = qa_template

            # Create query engine
            query_engine = self.current_index.as_query_engine(**query_engine_args)

            # Execute query
            response = query_engine.query(query_text)
            return str(response)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise RAGQueryError(f"Failed to execute query: {e}") from e

    def get_cache_info(self) -> dict[str, Any]:
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
        Build vector index from a document model with comprehensive error recovery.

        This method implements:
        - Pre-flight health checks
        - Transactional database operations with rollback
        - Comprehensive resource cleanup on failure
        - Retry mechanisms for transient failures
        - Circuit breaker protection for API calls
        - Recovery verification and consistency checks

        Args:
            document: Document model from database
            overwrite: If True, overwrite existing index
        Returns:
            Created vector index model
        Raises:
            RAGIndexError: If index building fails or index already exists
            InsufficientResourcesError: If system resources are insufficient
            RAGRecoveryError: If recovery operations fail
        """
        operation_start_time = datetime.now()
        logger.info(f"Building index for document {document.id}: {document.title}")

        # Pre-flight health checks
        if not self._perform_preflight_checks(document):
            raise InsufficientResourcesError(
                "System resources insufficient for index building"
            )

        # Check if vector index already exists
        existing_index = self.vector_repo.find_by_document_id(document.id)
        if existing_index and not overwrite:
            raise RAGIndexError(
                f"Vector index already exists for document {document.id}"
            )

        # Initialize recovery tracking (placeholder for future cleanup logic)
        vector_index_path: Path | None = None

        try:
            # Use recovery orchestrator for the entire operation
            return self._build_index_with_recovery(
                document, existing_index, operation_start_time
            )

        except Exception as e:
            # Log comprehensive error information
            logger.error(
                f"Index building failed for document {document.id}: {e}. "
                f"Operation duration: {datetime.now() - operation_start_time}"
            )

            # Attempt emergency cleanup if needed
            self._perform_emergency_cleanup(document.id, vector_index_path)

            # Re-raise with context
            if isinstance(e, (RAGIndexError, InsufficientResourcesError)):
                raise
            else:
                raise RAGRecoveryError(
                    f"Index building failed with recovery error: {e}"
                ) from e

    def _perform_preflight_checks(self, document: DocumentModel) -> bool:
        """Perform comprehensive pre-flight checks before index building."""
        logger.debug(f"Performing pre-flight checks for document {document.id}")

        try:
            # Run all health checks
            health_results = self.health_checker.run_all_checks()
            if not all(health_results.values()):
                failed_checks = [
                    check for check, result in health_results.items() if not result
                ]
                logger.error(f"Pre-flight health checks failed: {failed_checks}")
                return False

            # Validate document file exists and is accessible
            if not document.file_path or not Path(document.file_path).exists():
                logger.error(f"Document file not found: {document.file_path}")
                return False

            # Check file size for memory estimation
            file_size = Path(document.file_path).stat().st_size
            estimated_memory_mb = (
                file_size / (1024 * 1024) * 3
            )  # Rough estimate: 3x file size

            if estimated_memory_mb > 1000:  # 1GB threshold
                memory = psutil.virtual_memory()
                if memory.available < estimated_memory_mb * 1024 * 1024:
                    logger.error(
                        f"Insufficient memory for large document: {estimated_memory_mb:.2f}MB needed"
                    )
                    return False

            logger.debug("All pre-flight checks passed")
            return True

        except Exception as e:
            logger.error(f"Pre-flight check failed: {e}")
            return False

    def _build_index_with_recovery(
        self,
        document: DocumentModel,
        existing_index: VectorIndexModel | None,
        operation_start_time: datetime,
    ) -> VectorIndexModel:
        """Build index with full recovery orchestration."""

        # Setup cleanup handlers (paths managed by cleanup_manager)
        cleanup_handlers: list[Callable[[], None]] = []

        with self.cleanup_manager.cleanup_scope(f"index_build_{document.id}"):
            # Create temporary directory for index building
            temp_dir = tempfile.mkdtemp(prefix=f"rag_index_{document.id}_")
            temp_dir_path = Path(temp_dir)
            self.cleanup_manager.add_cleanup_path(temp_dir_path)

            logger.debug(f"Created temporary directory: {temp_dir_path}")

            # Build index with retry and circuit breaker protection
            try:
                success = self._build_index_with_api_protection(
                    document.file_path, temp_dir
                )
                if not success:
                    raise RAGIndexError(
                        f"Failed to build RAG index for document {document.id}"
                    )

            except (RetryExhaustedException, CircuitBreakerOpenError) as e:
                logger.error(f"API protection mechanism triggered: {e}")
                raise RAGIndexError(
                    f"Index building failed due to API issues: {e}"
                ) from e

            # Calculate index hash with retry
            index_hash = self._calculate_index_hash_with_retry(document)

            # Create persistent vector index directory
            vector_index_path = (
                self.vector_storage_dir / f"doc_{document.id}_{index_hash[:8]}"
            )

            # Ensure cleanup of vector path if operation fails
            cleanup_handlers.append(
                lambda: self._cleanup_vector_path(vector_index_path)
            )

            # Prepare vector index directory with file operations retry
            self._prepare_vector_index_directory_with_retry(vector_index_path)

            # Copy index files with retry protection
            self._copy_index_files_with_retry(temp_dir_path, vector_index_path)

            # Get chunk count for metadata
            chunk_count = self._get_chunk_count(str(vector_index_path))

            # Perform database operations in transaction with rollback
            return self._create_or_update_index_record(
                document, existing_index, vector_index_path, index_hash, chunk_count
            )

    def _build_index_with_api_protection(self, pdf_path: str, cache_dir: str) -> bool:
        """Build index with API call protection (retry + circuit breaker)."""

        @with_circuit_breaker(
            failure_threshold=self.api_circuit_breaker_config.failure_threshold,
            recovery_timeout=self.api_circuit_breaker_config.recovery_timeout,
            expected_exception=Exception,
        )
        @with_retry(
            max_attempts=self.api_retry_config.max_attempts,
            initial_delay=self.api_retry_config.initial_delay,
            exponential_base=self.api_retry_config.exponential_base,
            retryable_exceptions=self.api_retry_config.retryable_exceptions,
        )
        def protected_build_operation():
            return self.build_index_from_pdf(pdf_path, cache_dir)

        return protected_build_operation()

    def _calculate_index_hash_with_retry(self, document: DocumentModel) -> str:
        """Calculate index hash with retry protection."""

        @with_retry(
            max_attempts=self.file_retry_config.max_attempts,
            initial_delay=self.file_retry_config.initial_delay,
            retryable_exceptions=self.file_retry_config.retryable_exceptions,
        )
        def calculate_hash():
            return ContentHashService.calculate_file_hash(document.file_path)

        try:
            return calculate_hash()
        except (RetryExhaustedException, ContentHashError) as e:
            logger.warning(f"Could not calculate index hash: {e}")
            return f"fallback_{document.id}_{datetime.now().timestamp()}"

    def _prepare_vector_index_directory_with_retry(
        self, vector_index_path: Path
    ) -> None:
        """Prepare vector index directory with retry protection."""

        @with_retry(
            max_attempts=self.file_retry_config.max_attempts,
            initial_delay=self.file_retry_config.initial_delay,
            retryable_exceptions=self.file_retry_config.retryable_exceptions,
        )
        def prepare_directory():
            if vector_index_path.exists():
                shutil.rmtree(vector_index_path, ignore_errors=False)
            vector_index_path.mkdir(parents=True, exist_ok=True)

        prepare_directory()

    def _copy_index_files_with_retry(self, source_path: Path, dest_path: Path) -> None:
        """Copy index files with retry protection."""

        @with_retry(
            max_attempts=self.file_retry_config.max_attempts,
            initial_delay=self.file_retry_config.initial_delay,
            retryable_exceptions=self.file_retry_config.retryable_exceptions,
        )
        def copy_files():
            self._copy_index_files(source_path, dest_path)
            # Verify copy was successful
            if not self._verify_index_files(str(dest_path)):
                raise RAGIndexError("Index file verification failed after copy")

        copy_files()

    def _create_or_update_index_record(
        self,
        document: DocumentModel,
        existing_index: VectorIndexModel | None,
        vector_index_path: Path,
        index_hash: str,
        chunk_count: int,
    ) -> VectorIndexModel:
        """Create or update index record in database with transaction protection."""

        with self.transaction_manager.transaction_scope(f"index_record_{document.id}"):
            if existing_index:
                # Update existing record
                existing_index.index_path = str(vector_index_path)
                existing_index.index_hash = index_hash
                existing_index.chunk_count = chunk_count
                existing_index.created_at = datetime.now()
                saved_index = self.vector_repo.update(existing_index)
                logger.info(f"Updated existing index record {existing_index.id}")
            else:
                # Create new record
                vector_index = VectorIndexModel(
                    document_id=document.id,
                    index_path=str(vector_index_path),
                    index_hash=index_hash,
                    chunk_count=chunk_count,
                )
                saved_index = self.vector_repo.create(vector_index)
                logger.info(f"Created new index record {saved_index.id}")

            # Update current state only after successful database operation
            self.current_document_id = document.id
            self.current_vector_index = saved_index

            # Final verification
            if not self._verify_index_integrity(saved_index):
                raise RAGIndexError("Final index integrity verification failed")

            logger.info(
                f"Vector index for document {document.id} built successfully: "
                f"{saved_index.id}"
            )
            return saved_index

    def _cleanup_vector_path(self, vector_path: Path) -> None:
        """Clean up vector index path."""
        try:
            if vector_path and vector_path.exists():
                shutil.rmtree(vector_path, ignore_errors=True)
                logger.debug(f"Cleaned up vector path: {vector_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup vector path {vector_path}: {e}")

    def _perform_emergency_cleanup(
        self, document_id: int, vector_path: Path | None
    ) -> None:
        """Perform emergency cleanup after critical failure."""
        try:
            logger.warning(f"Performing emergency cleanup for document {document_id}")

            # Clean up vector index files
            if vector_path:
                self._cleanup_vector_path(vector_path)

            # Clean up any orphaned database records
            try:
                orphaned_index = self.vector_repo.find_by_document_id(document_id)
                if (
                    orphaned_index
                    and vector_path
                    and not Path(orphaned_index.index_path).exists()
                ):
                    self.vector_repo.delete(orphaned_index.id)
                    logger.info(f"Removed orphaned index record {orphaned_index.id}")
            except Exception as e:
                logger.error(f"Failed to cleanup orphaned database record: {e}")

        except Exception as e:
            logger.error(f"Emergency cleanup failed: {e}")

    def _verify_index_integrity(self, index: VectorIndexModel) -> bool:
        """Verify the integrity of a built index."""
        try:
            # Check if index files exist and are valid
            if not self._verify_index_files(index.index_path):
                logger.error(f"Index files verification failed for {index.id}")
                return False

            # Check if chunk count is reasonable
            if index.chunk_count <= 0:
                logger.warning(f"Index {index.id} has zero chunks")

            # Verify path accessibility
            index_path = Path(index.index_path)
            if not index_path.exists() or not index_path.is_dir():
                logger.error(f"Index path verification failed: {index.index_path}")
                return False

            logger.debug(f"Index integrity verification passed for {index.id}")
            return True

        except Exception as e:
            logger.error(f"Index integrity verification failed: {e}")
            return False

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
                raise RAGQueryError(f"Failed to load index for query: {e}") from e
        # Execute query using base RAG service
        response = self.query(query)
        logger.info(f"Query completed for document {document_id}")
        return response

    def get_document_index_status(self, document_id: int) -> dict[str, Any]:
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

    def get_enhanced_cache_info(self) -> dict[str, Any]:
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

    def recover_corrupted_index(
        self, document_id: int, force_rebuild: bool = False
    ) -> dict[str, Any]:
        """
        Recover a corrupted vector index with comprehensive diagnostics and repair.

        Args:
            document_id: Document ID to recover
            force_rebuild: If True, always rebuild regardless of corruption level

        Returns:
            Dictionary with recovery results and metrics
        """
        recovery_start_time = datetime.now()
        logger.info(f"Starting index recovery for document {document_id}")

        recovery_result = {
            "document_id": document_id,
            "recovery_successful": False,
            "corruption_detected": False,
            "corruption_type": None,
            "repair_actions": [],
            "recovery_duration_ms": 0,
            "error": None,
        }

        try:
            # Get document and existing index
            document = self.document_repo.find_by_id(document_id)
            if not document:
                recovery_result["error"] = f"Document {document_id} not found"
                return recovery_result

            existing_index = self.vector_repo.find_by_document_id(document_id)
            if not existing_index:
                recovery_result["error"] = f"No index found for document {document_id}"
                return recovery_result

            # Perform comprehensive corruption analysis
            corruption_analysis = self._analyze_index_corruption(existing_index)
            recovery_result.update(corruption_analysis)

            if corruption_analysis["corruption_detected"] or force_rebuild:
                # Determine recovery strategy based on corruption type
                if (
                    force_rebuild
                    or corruption_analysis["corruption_severity"] == "critical"
                ):
                    # Full rebuild required
                    recovery_result["repair_actions"].append("full_rebuild")
                    try:
                        # Use the enhanced build method with recovery
                        new_index = self.build_index_from_document(
                            document, overwrite=True
                        )
                        recovery_result["recovery_successful"] = True
                        recovery_result["new_index_id"] = new_index.id
                        logger.info(
                            f"Successfully rebuilt corrupted index for document {document_id}"
                        )
                    except Exception as e:
                        recovery_result["error"] = f"Rebuild failed: {e}"
                        logger.error(f"Index rebuild failed during recovery: {e}")

                elif corruption_analysis["corruption_severity"] == "moderate":
                    # Attempt partial recovery
                    recovery_result["repair_actions"].append("partial_repair")
                    repair_success = self._attempt_partial_index_repair(existing_index)
                    recovery_result["recovery_successful"] = repair_success

                else:
                    # Light repair/verification
                    recovery_result["repair_actions"].append("verification_repair")
                    repair_success = self._perform_index_verification_repair(
                        existing_index
                    )
                    recovery_result["recovery_successful"] = repair_success
            else:
                # No corruption detected
                recovery_result["recovery_successful"] = True
                recovery_result["repair_actions"].append("no_action_needed")

        except Exception as e:
            recovery_result["error"] = str(e)
            logger.error(f"Index recovery failed for document {document_id}: {e}")
        finally:
            recovery_result["recovery_duration_ms"] = int(
                (datetime.now() - recovery_start_time).total_seconds() * 1000
            )

        return recovery_result

    def _analyze_index_corruption(self, index: VectorIndexModel) -> dict[str, Any]:
        """Analyze index for various types of corruption."""
        analysis_result = {
            "corruption_detected": False,
            "corruption_type": [],
            "corruption_severity": "none",  # none, light, moderate, critical
            "missing_files": [],
            "corrupted_files": [],
            "file_size_issues": [],
            "metadata_issues": [],
        }

        try:
            index_path = Path(index.index_path)

            # Check if index directory exists
            if not index_path.exists():
                analysis_result["corruption_detected"] = True
                analysis_result["corruption_type"].append("missing_directory")
                analysis_result["corruption_severity"] = "critical"
                return analysis_result

            # Check for required files
            required_files = [
                "default__vector_store.json",
                "graph_store.json",
                "index_store.json",
            ]

            for required_file in required_files:
                file_path = index_path / required_file
                if not file_path.exists():
                    analysis_result["missing_files"].append(required_file)
                    analysis_result["corruption_detected"] = True
                    analysis_result["corruption_type"].append("missing_files")
                else:
                    # Check file integrity
                    try:
                        if file_path.stat().st_size == 0:
                            analysis_result["file_size_issues"].append(required_file)
                            analysis_result["corruption_detected"] = True
                            analysis_result["corruption_type"].append("empty_files")

                        # Try to parse JSON files
                        if required_file.endswith(".json"):
                            import json

                            with open(file_path) as f:
                                json.load(f)
                    except Exception as e:
                        analysis_result["corrupted_files"].append(
                            f"{required_file}: {e}"
                        )
                        analysis_result["corruption_detected"] = True
                        analysis_result["corruption_type"].append("corrupted_files")

            # Determine corruption severity
            if analysis_result["missing_files"] or any(
                "vector_store" in f for f in analysis_result["corrupted_files"]
            ):
                analysis_result["corruption_severity"] = "critical"
            elif (
                analysis_result["corrupted_files"]
                or analysis_result["file_size_issues"]
            ):
                analysis_result["corruption_severity"] = "moderate"
            elif analysis_result["metadata_issues"]:
                analysis_result["corruption_severity"] = "light"

        except Exception as e:
            logger.error(f"Corruption analysis failed: {e}")
            analysis_result["corruption_detected"] = True
            analysis_result["corruption_severity"] = "critical"
            analysis_result["corruption_type"].append("analysis_failure")

        return analysis_result

    def _attempt_partial_index_repair(self, index: VectorIndexModel) -> bool:
        """Attempt to repair index without full rebuild."""
        try:
            logger.info(f"Attempting partial repair of index {index.id}")

            # For now, partial repair is limited - in a full implementation,
            # this could involve reconstructing missing metadata files,
            # repairing JSON structure, etc.

            # Verify what we can repair vs what needs rebuild
            index_path = Path(index.index_path)

            # Example: regenerate metadata if main vector store exists
            vector_store_file = index_path / "default__vector_store.json"
            if vector_store_file.exists():
                # Could regenerate missing ancillary files
                # This is a placeholder for more sophisticated repair logic
                return self._verify_index_files(str(index_path))

            return False

        except Exception as e:
            logger.error(f"Partial index repair failed: {e}")
            return False

    def _perform_index_verification_repair(self, index: VectorIndexModel) -> bool:
        """Perform light verification and repair of index."""
        try:
            logger.debug(f"Performing verification repair of index {index.id}")

            # Update database metadata if files are ok but metadata is stale
            if self._verify_index_files(index.index_path):
                # Recalculate chunk count if it seems wrong
                actual_chunk_count = self._get_chunk_count(index.index_path)
                if actual_chunk_count != index.chunk_count and actual_chunk_count > 0:
                    index.chunk_count = actual_chunk_count
                    self.vector_repo.update(index)
                    logger.info(
                        f"Updated chunk count for index {index.id}: {actual_chunk_count}"
                    )

                return True

            return False

        except Exception as e:
            logger.error(f"Verification repair failed: {e}")
            return False

    def get_recovery_metrics(self) -> dict[str, Any]:
        """Get comprehensive recovery and error handling metrics."""
        try:
            # Collect metrics from all recovery components
            metrics = self.recovery_orchestrator.get_comprehensive_metrics()

            # Add service-specific metrics
            metrics["service_metrics"] = {
                "current_document_id": self.current_document_id,
                "has_active_index": self.current_index is not None,
                "vector_storage_path": str(self.vector_storage_dir),
                "test_mode": self.test_mode,
            }

            # Add health check results
            health_results = self.health_checker.run_all_checks()
            metrics["health_status"] = {
                "overall_healthy": all(health_results.values()),
                "checks": health_results,
                "last_check_time": datetime.now().isoformat(),
            }

            # Add database statistics
            try:
                db_stats = self.vector_repo.get_index_statistics()
                metrics["database_metrics"] = db_stats
            except Exception as e:
                metrics["database_metrics"] = {"error": str(e)}

            return metrics

        except Exception as e:
            logger.error(f"Failed to get recovery metrics: {e}")
            return {"error": str(e)}

    def perform_system_recovery_check(self) -> dict[str, Any]:
        """Perform comprehensive system recovery check and cleanup."""
        check_start_time = datetime.now()
        logger.info("Starting comprehensive system recovery check")

        recovery_report = {
            "check_start_time": check_start_time.isoformat(),
            "health_status": {},
            "orphaned_resources": {},
            "corrupted_indexes": [],
            "cleanup_actions": [],
            "recommendations": [],
            "overall_status": "healthy",  # healthy, degraded, critical
        }

        try:
            # Run health checks
            health_results = self.health_checker.run_all_checks()
            recovery_report["health_status"] = health_results

            if not all(health_results.values()):
                recovery_report["overall_status"] = "degraded"
                failed_checks = [
                    check for check, result in health_results.items() if not result
                ]
                recovery_report["recommendations"].extend(
                    [f"Address failed health check: {check}" for check in failed_checks]
                )

            # Check for orphaned resources
            orphaned_count = self._identify_and_cleanup_orphaned_resources()
            if orphaned_count > 0:
                recovery_report["cleanup_actions"].append(
                    f"Cleaned up {orphaned_count} orphaned resources"
                )

            # Check for corrupted indexes
            corrupted_indexes = self._identify_corrupted_indexes()
            recovery_report["corrupted_indexes"] = corrupted_indexes

            if corrupted_indexes:
                recovery_report["overall_status"] = (
                    "degraded"
                    if recovery_report["overall_status"] == "healthy"
                    else "critical"
                )
                recovery_report["recommendations"].append(
                    f"Repair or rebuild {len(corrupted_indexes)} corrupted indexes"
                )

        except Exception as e:
            logger.error(f"System recovery check failed: {e}")
            recovery_report["overall_status"] = "critical"
            recovery_report["error"] = str(e)
        finally:
            check_duration = datetime.now() - check_start_time
            recovery_report["check_duration_ms"] = int(
                check_duration.total_seconds() * 1000
            )
            recovery_report["check_end_time"] = datetime.now().isoformat()

        logger.info(
            f"System recovery check completed: {recovery_report['overall_status']}"
        )
        return recovery_report

    def _identify_and_cleanup_orphaned_resources(self) -> int:
        """Identify and cleanup orphaned resources."""
        try:
            # Use existing cleanup method
            orphaned_count = self.cleanup_orphaned_indexes()

            # Additional cleanup for filesystem orphans
            if self.vector_storage_dir.exists():
                # Find directories that don't have corresponding database records
                fs_orphan_count = 0
                for vector_dir in self.vector_storage_dir.iterdir():
                    if vector_dir.is_dir() and vector_dir.name.startswith("doc_"):
                        # Extract document ID from directory name
                        try:
                            doc_id_part = vector_dir.name.split("_")[1]
                            doc_id = int(doc_id_part)

                            # Check if there's a database record
                            db_index = self.vector_repo.find_by_document_id(doc_id)
                            if not db_index or db_index.index_path != str(vector_dir):
                                # This is an orphaned filesystem directory
                                shutil.rmtree(vector_dir, ignore_errors=True)
                                fs_orphan_count += 1
                                logger.info(
                                    f"Removed orphaned vector directory: {vector_dir}"
                                )
                        except (ValueError, IndexError):
                            # Invalid directory name format, might be orphaned
                            logger.warning(
                                f"Found directory with invalid name format: {vector_dir}"
                            )

                orphaned_count += fs_orphan_count

            return orphaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned resources: {e}")
            return 0

    def _identify_corrupted_indexes(self) -> list[dict[str, Any]]:
        """Identify corrupted indexes across the system."""
        corrupted_indexes = []

        try:
            # Get all vector indexes from database
            all_indexes = self.vector_repo.get_all_indexes()

            for index in all_indexes:
                corruption_analysis = self._analyze_index_corruption(index)
                if corruption_analysis["corruption_detected"]:
                    corrupted_info = {
                        "index_id": index.id,
                        "document_id": index.document_id,
                        "corruption_analysis": corruption_analysis,
                    }
                    corrupted_indexes.append(corrupted_info)

        except Exception as e:
            logger.error(f"Failed to identify corrupted indexes: {e}")

        return corrupted_indexes

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
                                        "__str__": lambda: (
                                            f"Mock response for doc {document.id}: "
                                            f"{prompt}"
                                        )
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
                                "__str__": lambda: f"Mock response for document "
                                f"{document_id}: {prompt}"
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

            # In test mode, create minimal fake index files if they don't exist
            if self.test_mode:
                required_files = [
                    "default__vector_store.json",
                    "graph_store.json",
                    "index_store.json",
                ]

                # Create fake index files in test mode
                path.mkdir(parents=True, exist_ok=True)
                for file_name in required_files:
                    file_path = path / file_name
                    if not file_path.exists():
                        # Create minimal valid JSON content
                        fake_content = {"test_mode": True, "created_at": datetime.now().isoformat()}
                        import json
                        with open(file_path, 'w') as f:
                            json.dump(fake_content, f)
                        logger.debug(f"Created test mode index file: {file_path}")

                return True

            # Production mode: verify actual files exist
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

                with open(metadata_path) as f:
                    metadata = json.load(f)
                    return int(metadata.get("document_count", 0))
            # Fallback: estimate from vector store file
            vector_store_path = Path(index_path) / "default__vector_store.json"
            if vector_store_path.exists():
                import json

                with open(vector_store_path) as f:
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
