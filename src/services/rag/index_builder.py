"""
RAG Index Builder Service

Handles PDF processing and vector index creation including:
- PDF document ingestion and chunking
- Vector embedding generation using Google Gemini
- Index persistence and storage management
- Error recovery and retry mechanisms

This service focuses solely on building vector indexes from documents
and provides a clean interface for index creation operations.
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex

from src.database.models import DocumentModel
from src.services.content_hash_service import ContentHashError, ContentHashService
from src.services.error_recovery import (
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    ResourceCleanupManager,
    RetryConfig,
    RetryExhaustedException,
    with_circuit_breaker,
    with_retry,
)

from .file_manager import RAGFileManager

logger = logging.getLogger(__name__)


class RAGIndexBuilderError(Exception):
    """Base exception for RAG index builder errors."""

    pass


class IndexCreationError(RAGIndexBuilderError):
    """Exception raised when index creation fails."""

    pass


class RAGIndexBuilder:
    """
    Handles PDF processing and vector index creation.

    Responsibilities:
    - PDF document processing using LlamaIndex
    - Vector embedding generation with Google Gemini
    - Index storage and persistence
    - Error recovery and cleanup
    """

    def __init__(
        self, api_key: str, file_manager: RAGFileManager, test_mode: bool = False
    ) -> None:
        """
        Initialize RAG index builder.

        Args:
            api_key: Google Gemini API key
            file_manager: RAG file manager instance
            test_mode: If True, skip actual API initialization for testing
        """
        self.api_key = api_key
        self.file_manager = file_manager
        self.test_mode = test_mode
        self.cleanup_manager = ResourceCleanupManager()

        # Configure retry and circuit breaker for API operations
        self.api_retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True,
            retryable_exceptions=(ConnectionError, TimeoutError, Exception),
            non_retryable_exceptions=(KeyboardInterrupt, SystemExit, ValueError),
        )

        self.api_circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=120.0,  # 2 minutes
            expected_exception=Exception,
            success_threshold=2,
        )

        # Initialize LlamaIndex components if not in test mode
        if not test_mode:
            self._initialize_llama_index()

        logger.info("RAG Index Builder initialized")

    def _initialize_llama_index(self) -> None:
        """Initialize LlamaIndex components with Google Gemini integration."""
        try:
            os.environ["GOOGLE_API_KEY"] = self.api_key

            from llama_index.core import Settings
            from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
            from llama_index.llms.google_genai import GoogleGenAI

            # Configure LLM and embeddings
            Settings.llm = GoogleGenAI(
                model_name="gemini-1.5-flash", api_key=self.api_key
            )
            Settings.embed_model = GoogleGenAIEmbedding(
                model_name="models/embedding-001", api_key=self.api_key
            )

            logger.info("LlamaIndex initialized with Google Gemini")

        except ImportError as e:
            error_msg = f"LlamaIndex dependencies not available: {e}"
            logger.error(error_msg)
            raise RAGIndexBuilderError(error_msg) from e

        except Exception as e:
            error_msg = f"LlamaIndex initialization failed: {e}"
            logger.error(error_msg)
            raise RAGIndexBuilderError(error_msg) from e

    def build_index_from_pdf(self, pdf_path: str, temp_dir: str) -> bool:
        """
        Build vector index from PDF file using LlamaIndex.

        Args:
            pdf_path: Path to PDF file
            temp_dir: Temporary directory for index storage

        Returns:
            True if index was built successfully

        Raises:
            IndexCreationError: If index building fails
        """
        try:
            if self.test_mode:
                logger.info(f"Test mode: Simulating index build for {pdf_path}")
                return True

            from llama_index.core import StorageContext
            from llama_index.readers.file import PDFReader

            # Validate PDF file exists
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                raise IndexCreationError(f"PDF file not found: {pdf_path}")

            # Load PDF document
            reader = PDFReader()
            documents = reader.load_data(file=pdf_file)

            if not documents:
                raise IndexCreationError(f"No content extracted from PDF: {pdf_path}")

            logger.debug(f"Extracted {len(documents)} documents from PDF")

            # Create vector index with error protection
            index = self._create_vector_index_with_protection(documents)

            # Persist index to temporary storage
            storage_dir = Path(temp_dir)
            storage_dir.mkdir(exist_ok=True)

            storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
            index.storage_context = storage_context
            index.storage_context.persist(persist_dir=str(storage_dir))

            # Verify index was created successfully
            if not self.file_manager.verify_index_files(str(storage_dir)):
                raise IndexCreationError(
                    "Index files verification failed after creation"
                )

            logger.info(f"Vector index built successfully for {pdf_path}")
            return True

        except IndexCreationError:
            raise
        except Exception as e:
            error_msg = f"Failed to build index from PDF {pdf_path}: {e}"
            logger.error(error_msg)
            raise IndexCreationError(error_msg) from e

    def _create_vector_index_with_protection(self, documents) -> "VectorStoreIndex":
        """Create vector index with API protection (retry + circuit breaker)."""

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
        def protected_creation() -> Any:
            from llama_index.core import VectorStoreIndex

            return VectorStoreIndex.from_documents(documents)

        try:
            return protected_creation()
        except (RetryExhaustedException, CircuitBreakerOpenError) as e:
            raise IndexCreationError(
                f"Index creation failed due to API issues: {e}"
            ) from e

    def build_index_for_document(
        self, document: DocumentModel, overwrite: bool = False
    ) -> dict[str, Any]:
        """
        Build complete vector index for a document with full error recovery.

        Args:
            document: Document model to build index for
            overwrite: If True, overwrite existing index

        Returns:
            Dictionary with build results including paths and metadata

        Raises:
            RAGIndexBuilderError: If index building fails
        """
        build_start_time = datetime.now()
        logger.info(f"Building index for document {document.id}: {document.title}")

        build_result = {
            "document_id": document.id,
            "success": False,
            "index_path": None,
            "index_hash": None,
            "chunk_count": 0,
            "build_duration_ms": 0,
            "error": None,
        }

        temp_dir_path: Path | None = None
        final_index_path: Path | None = None

        try:
            # Validate document file
            if not document.file_path or not Path(document.file_path).exists():
                raise RAGIndexBuilderError(
                    f"Document file not found: {document.file_path}"
                )

            # Calculate content hash for index uniqueness
            try:
                content_hash = ContentHashService.calculate_file_hash(
                    document.file_path
                )
            except ContentHashError as e:
                logger.warning(f"Could not calculate content hash: {e}")
                content_hash = f"fallback_{document.id}_{datetime.now().timestamp()}"

            # Generate final index path
            final_index_path = self.file_manager.generate_index_path(
                document.id, content_hash
            )

            # Check if index already exists
            if final_index_path.exists() and not overwrite:
                raise RAGIndexBuilderError(
                    f"Index already exists for document {document.id}"
                )

            with self.cleanup_manager.cleanup_scope(f"index_build_{document.id}"):
                # Create temporary directory for index building
                temp_dir = tempfile.mkdtemp(prefix=f"rag_index_{document.id}_")
                temp_dir_path = Path(temp_dir)
                self.cleanup_manager.add_cleanup_path(temp_dir_path)

                logger.debug(f"Building index in temporary directory: {temp_dir_path}")

                # Build index in temporary directory
                build_success = self.build_index_from_pdf(
                    document.file_path, str(temp_dir_path)
                )
                if not build_success:
                    raise IndexCreationError("Index building returned failure status")

                # Prepare final index directory
                self.file_manager.prepare_index_directory(
                    final_index_path, overwrite=overwrite
                )

                # Copy index files to final location
                self.file_manager.copy_index_files(temp_dir_path, final_index_path)

                # Verify final index
                if not self.file_manager.verify_index_files(str(final_index_path)):
                    raise IndexCreationError("Final index verification failed")

                # Get chunk count for metadata
                chunk_count = self.file_manager.get_chunk_count(str(final_index_path))

                # Update build result
                build_result.update(
                    {
                        "success": True,
                        "index_path": str(final_index_path),
                        "index_hash": content_hash,
                        "chunk_count": chunk_count,
                    }
                )

                logger.info(
                    f"Index built successfully for document {document.id} "
                    f"with {chunk_count} chunks"
                )

        except Exception as e:
            build_result["error"] = str(e)
            logger.error(f"Index building failed for document {document.id}: {e}")

            # Emergency cleanup
            if final_index_path and final_index_path.exists():
                self.file_manager.cleanup_index_files(str(final_index_path))

            raise RAGIndexBuilderError(f"Index building failed: {e}") from e

        finally:
            build_duration = datetime.now() - build_start_time
            build_result["build_duration_ms"] = int(
                build_duration.total_seconds() * 1000
            )

        return build_result

    def validate_build_requirements(self, document: DocumentModel) -> dict[str, Any]:
        """
        Validate that all requirements are met for building an index.

        Args:
            document: Document to validate

        Returns:
            Dictionary with validation results
        """
        validation_result = {"valid": True, "issues": [], "warnings": []}

        try:
            # Check document file exists
            if not document.file_path:
                validation_result["issues"].append("Document has no file path")
                validation_result["valid"] = False

            elif not Path(document.file_path).exists():
                validation_result["issues"].append(
                    f"Document file not found: {document.file_path}"
                )
                validation_result["valid"] = False

            else:
                # Check file size for memory estimation
                file_size = Path(document.file_path).stat().st_size
                if file_size == 0:
                    validation_result["issues"].append("Document file is empty")
                    validation_result["valid"] = False

                elif file_size > 100 * 1024 * 1024:  # 100MB threshold
                    validation_result["warnings"].append(
                        f"Large file may require significant memory: {file_size / (1024 * 1024):.1f}MB"
                    )

            # Check storage accessibility
            if not self.file_manager.is_accessible():
                validation_result["issues"].append(
                    "Vector storage directory is not accessible"
                )
                validation_result["valid"] = False

            # Check API availability (if not in test mode)
            if not self.test_mode and not self.api_key:
                validation_result["issues"].append("Google API key is not configured")
                validation_result["valid"] = False

        except Exception as e:
            validation_result["issues"].append(f"Validation error: {e}")
            validation_result["valid"] = False

        return validation_result

    def get_build_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the index building service.

        Returns:
            Dictionary with service statistics
        """
        stats = {
            "service_name": "RAGIndexBuilder",
            "test_mode": self.test_mode,
            "storage_stats": self.file_manager.get_storage_statistics(),
            "config": {
                "api_retry_attempts": self.api_retry_config.max_attempts,
                "circuit_breaker_threshold": self.api_circuit_breaker_config.failure_threshold,
                "recovery_timeout": self.api_circuit_breaker_config.recovery_timeout,
            },
        }

        return stats
