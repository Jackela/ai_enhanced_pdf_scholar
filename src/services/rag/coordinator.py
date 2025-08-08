"""
RAG Coordinator Service

Orchestrates interactions between focused RAG services including:
- Coordinating index building, querying, and recovery operations
- Managing service dependencies and lifecycle
- Providing unified interface for RAG functionality
- Handling cross-service workflows and transactions

This service acts as a facade that coordinates the focused RAG services
while maintaining backward compatibility with the original interface.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel, VectorIndexModel
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from src.services.error_recovery import HealthChecker, TransactionManager

from .file_manager import RAGFileManager
from .index_builder import RAGIndexBuilder, RAGIndexBuilderError
from .query_engine import RAGQueryEngine, RAGQueryError
from .recovery_service import RAGRecoveryService, RAGRecoveryError

logger = logging.getLogger(__name__)


class RAGCoordinatorError(Exception):
    """Base exception for RAG coordinator errors."""
    pass


class RAGCoordinator:
    """
    Orchestrates interactions between focused RAG services.
    
    This coordinator provides a unified interface for RAG operations while
    delegating specific responsibilities to focused service components:
    - RAGFileManager: File system operations
    - RAGIndexBuilder: Index creation and building
    - RAGQueryEngine: Index loading and querying
    - RAGRecoveryService: Corruption detection and repair
    
    The coordinator maintains backward compatibility with the original
    EnhancedRAGService interface while providing improved maintainability
    through service decomposition.
    """
    
    def __init__(
        self,
        api_key: str,
        db_connection: DatabaseConnection,
        vector_storage_dir: str = "vector_indexes",
        test_mode: bool = False
    ):
        """
        Initialize RAG coordinator with service dependencies.
        
        Args:
            api_key: Google Gemini API key
            db_connection: Database connection instance
            vector_storage_dir: Directory for storing vector indexes
            test_mode: If True, use test mode for all services
        """
        self.api_key = api_key
        self.db_connection = db_connection
        self.test_mode = test_mode
        
        # Initialize repositories
        self.document_repo = DocumentRepository(db_connection)
        self.vector_repo = VectorIndexRepository(db_connection)
        
        # Initialize transaction manager for cross-service operations
        self.transaction_manager = TransactionManager(db_connection)
        
        # Initialize focused services
        self.file_manager = RAGFileManager(vector_storage_dir)
        self.index_builder = RAGIndexBuilder(api_key, self.file_manager, test_mode)
        self.query_engine = RAGQueryEngine(
            self.document_repo, self.vector_repo, self.file_manager, test_mode
        )
        
        # Initialize recovery service with health checker
        self.health_checker = HealthChecker()
        self.recovery_service = RAGRecoveryService(
            self.vector_repo, self.file_manager, self.health_checker
        )
        
        logger.info(f"RAG Coordinator initialized with storage: {vector_storage_dir}")

    # Main API methods - backward compatibility with EnhancedRAGService
    
    def build_index_from_document(
        self, 
        document: DocumentModel, 
        overwrite: bool = False
    ) -> VectorIndexModel:
        """
        Build vector index from a document model with comprehensive error recovery.
        
        Args:
            document: Document model from database
            overwrite: If True, overwrite existing index
            
        Returns:
            Created vector index model
            
        Raises:
            RAGCoordinatorError: If index building fails
        """
        operation_start_time = datetime.now()
        logger.info(f"Coordinating index build for document {document.id}: {document.title}")
        
        try:
            # Check if index already exists
            existing_index = self.vector_repo.find_by_document_id(document.id)
            if existing_index and not overwrite:
                raise RAGCoordinatorError(f"Vector index already exists for document {document.id}")
            
            # Validate build requirements
            validation_result = self.index_builder.validate_build_requirements(document)
            if not validation_result["valid"]:
                issues = ", ".join(validation_result["issues"])
                raise RAGCoordinatorError(f"Build validation failed: {issues}")
            
            # Build index using index builder service
            build_result = self.index_builder.build_index_for_document(document, overwrite)
            
            if not build_result["success"]:
                error_msg = build_result.get("error", "Unknown build error")
                raise RAGCoordinatorError(f"Index building failed: {error_msg}")
            
            # Create or update database record within transaction
            with self.transaction_manager.transaction_scope(f"index_record_{document.id}"):
                if existing_index:
                    # Update existing record
                    existing_index.index_path = build_result["index_path"]
                    existing_index.index_hash = build_result["index_hash"]
                    existing_index.chunk_count = build_result["chunk_count"]
                    existing_index.created_at = datetime.now()
                    saved_index = self.vector_repo.update(existing_index)
                    logger.info(f"Updated existing index record {existing_index.id}")
                else:
                    # Create new record
                    vector_index = VectorIndexModel(
                        document_id=document.id,
                        index_path=build_result["index_path"],
                        index_hash=build_result["index_hash"],
                        chunk_count=build_result["chunk_count"]
                    )
                    saved_index = self.vector_repo.create(vector_index)
                    logger.info(f"Created new index record {saved_index.id}")
            
            operation_duration = datetime.now() - operation_start_time
            logger.info(
                f"Index build coordinated successfully for document {document.id} "
                f"in {operation_duration.total_seconds():.2f}s"
            )
            
            return saved_index
            
        except RAGIndexBuilderError as e:
            raise RAGCoordinatorError(f"Index building failed: {e}") from e
        except Exception as e:
            error_msg = f"Index building coordination failed: {e}"
            logger.error(error_msg)
            raise RAGCoordinatorError(error_msg) from e

    def load_index_for_document(self, document_id: int) -> bool:
        """
        Load vector index for a specific document.
        
        Args:
            document_id: Document ID to load index for
            
        Returns:
            True if index loaded successfully
            
        Raises:
            RAGCoordinatorError: If loading fails
        """
        try:
            return self.query_engine.load_index_for_document(document_id)
        except RAGQueryError as e:
            raise RAGCoordinatorError(f"Index loading failed: {e}") from e

    def query_document(self, query: str, document_id: int) -> str:
        """
        Query a specific document using its vector index.
        
        Args:
            query: User query
            document_id: Document ID to query
            
        Returns:
            RAG response string
            
        Raises:
            RAGCoordinatorError: If query fails
        """
        try:
            return self.query_engine.query_document(query, document_id)
        except RAGQueryError as e:
            raise RAGCoordinatorError(f"Document query failed: {e}") from e

    def get_document_index_status(self, document_id: int) -> Dict[str, Any]:
        """
        Get the indexing status for a document.
        
        Args:
            document_id: Document ID to check
            
        Returns:
            Dictionary with index status information
        """
        try:
            return self.query_engine.get_document_query_status(document_id)
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
            
        Raises:
            RAGCoordinatorError: If rebuild fails
        """
        logger.info(f"Coordinating index rebuild for document {document_id}")
        
        try:
            # Get document
            document = self.document_repo.find_by_id(document_id)
            if not document:
                raise RAGCoordinatorError(f"Document not found: {document_id}")
            
            # Remove existing index if present
            existing_index = self.vector_repo.find_by_document_id(document_id)
            if existing_index:
                self.file_manager.cleanup_index_files(existing_index.index_path)
                self.vector_repo.delete(existing_index.id)
                logger.debug(f"Removed existing index for document {document_id}")
            
            # Build new index
            return self.build_index_from_document(document, overwrite=True)
            
        except Exception as e:
            error_msg = f"Index rebuild coordination failed: {e}"
            logger.error(error_msg)
            raise RAGCoordinatorError(error_msg) from e

    def recover_corrupted_index(
        self, 
        document_id: int, 
        force_rebuild: bool = False
    ) -> Dict[str, Any]:
        """
        Recover a corrupted vector index with comprehensive diagnostics and repair.
        
        Args:
            document_id: Document ID to recover
            force_rebuild: If True, always rebuild regardless of corruption level
            
        Returns:
            Dictionary with recovery results and metrics
            
        Raises:
            RAGCoordinatorError: If recovery fails
        """
        logger.info(f"Coordinating index recovery for document {document_id}")
        
        try:
            # Get document and existing index
            document = self.document_repo.find_by_id(document_id)
            if not document:
                raise RAGCoordinatorError(f"Document not found: {document_id}")
                
            existing_index = self.vector_repo.find_by_document_id(document_id)
            if not existing_index:
                raise RAGCoordinatorError(f"No index found for document {document_id}")
            
            # Define rebuild callback for recovery service
            def rebuild_callback(vector_index: VectorIndexModel) -> bool:
                try:
                    self.rebuild_index(document_id)
                    return True
                except Exception as e:
                    logger.error(f"Rebuild callback failed: {e}")
                    return False
            
            # Perform recovery using recovery service
            recovery_result = self.recovery_service.recover_corrupted_index(
                existing_index, force_rebuild, rebuild_callback
            )
            
            logger.info(f"Index recovery completed for document {document_id}")
            return recovery_result
            
        except RAGRecoveryError as e:
            raise RAGCoordinatorError(f"Index recovery failed: {e}") from e
        except Exception as e:
            error_msg = f"Index recovery coordination failed: {e}"
            logger.error(error_msg)
            raise RAGCoordinatorError(error_msg) from e

    def cleanup_orphaned_indexes(self) -> int:
        """
        Clean up orphaned vector indexes.
        
        Returns:
            Number of orphaned indexes cleaned up
        """
        try:
            return self.recovery_service.cleanup_orphaned_resources()
        except Exception as e:
            logger.error(f"Orphaned index cleanup failed: {e}")
            raise RAGCoordinatorError(f"Cleanup failed: {e}") from e

    def perform_system_recovery_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive system recovery check and cleanup.
        
        Returns:
            Dictionary with recovery check results
        """
        try:
            return self.recovery_service.perform_system_health_check()
        except Exception as e:
            logger.error(f"System recovery check failed: {e}")
            raise RAGCoordinatorError(f"System check failed: {e}") from e

    # Enhanced service information methods
    
    def get_enhanced_cache_info(self) -> Dict[str, Any]:
        """
        Get comprehensive cache and service information.
        
        Returns:
            Dictionary with comprehensive service information
        """
        try:
            cache_info = {
                "coordinator_info": {
                    "test_mode": self.test_mode,
                    "vector_storage_dir": str(self.file_manager.vector_storage_dir),
                    "current_document": self.query_engine.get_current_document_info()
                },
                "service_stats": {
                    "file_manager": self.file_manager.get_storage_statistics(),
                    "index_builder": self.index_builder.get_build_statistics(),
                    "query_engine": self.query_engine.get_query_statistics(),
                    "recovery_service": self.recovery_service.get_recovery_metrics()
                }
            }
            
            # Add database statistics
            try:
                db_stats = self.vector_repo.get_index_statistics()
                cache_info["database_stats"] = db_stats
            except Exception as e:
                cache_info["database_stats"] = {"error": str(e)}
                
            return cache_info
            
        except Exception as e:
            logger.error(f"Failed to get enhanced cache info: {e}")
            return {"error": str(e)}

    def get_service_health_status(self) -> Dict[str, Any]:
        """
        Get health status of all coordinated services.
        
        Returns:
            Dictionary with service health information
        """
        try:
            health_status = {
                "overall_healthy": True,
                "services": {
                    "file_manager": {
                        "healthy": self.file_manager.is_accessible(),
                        "storage_accessible": self.file_manager.is_accessible()
                    },
                    "database": {
                        "healthy": True,
                        "connection_valid": True
                    },
                    "recovery_service": {
                        "healthy": True,
                        "health_checks": {}
                    }
                },
                "recommendations": []
            }
            
            # Test database connection
            try:
                self.vector_repo.get_index_statistics()
            except Exception as e:
                health_status["services"]["database"]["healthy"] = False
                health_status["services"]["database"]["error"] = str(e)
                health_status["overall_healthy"] = False
                health_status["recommendations"].append("Check database connection")
            
            # Get detailed health checks from recovery service
            try:
                recovery_health = self.recovery_service.health_checker.run_all_checks()
                health_status["services"]["recovery_service"]["health_checks"] = recovery_health
                
                if not all(recovery_health.values()):
                    health_status["services"]["recovery_service"]["healthy"] = False
                    health_status["overall_healthy"] = False
                    failed_checks = [check for check, result in recovery_health.items() if not result]
                    health_status["recommendations"].extend([
                        f"Address failed health check: {check}" for check in failed_checks
                    ])
                    
            except Exception as e:
                health_status["services"]["recovery_service"]["healthy"] = False
                health_status["services"]["recovery_service"]["error"] = str(e)
                health_status["overall_healthy"] = False
                
            return health_status
            
        except Exception as e:
            logger.error(f"Failed to get service health status: {e}")
            return {"error": str(e), "overall_healthy": False}

    # Convenience methods for common operations
    
    def preload_document_index(self, document_id: int) -> bool:
        """
        Preload index for improved query performance.
        
        Args:
            document_id: Document ID to preload
            
        Returns:
            True if preloading was successful
        """
        try:
            return self.query_engine.preload_index(document_id)
        except Exception as e:
            logger.warning(f"Index preloading failed for document {document_id}: {e}")
            return False

    def clear_current_index(self) -> None:
        """Clear the currently loaded index state."""
        self.query_engine.clear_current_index()

    def get_current_document_info(self) -> Dict[str, Any]:
        """Get information about the currently loaded document."""
        return self.query_engine.get_current_document_info()

    # Legacy compatibility methods (for gradual migration)
    
    def query(self, query_text: str) -> str:
        """
        Legacy method: Query the current vector index.
        
        Args:
            query_text: User query string
            
        Returns:
            RAG response string
            
        Raises:
            RAGCoordinatorError: If no index is loaded or query fails
        """
        try:
            return self.query_engine.query_current_document(query_text)
        except RAGQueryError as e:
            raise RAGCoordinatorError(f"Legacy query failed: {e}") from e

    def get_cache_info(self) -> Dict[str, Any]:
        """Legacy method: Get basic cache information."""
        current_info = self.query_engine.get_current_document_info()
        storage_stats = self.file_manager.get_storage_statistics()
        
        return {
            "has_current_index": current_info["has_loaded_index"],
            "current_pdf_path": current_info["current_pdf_path"],
            "current_document_id": current_info["current_document_id"],
            "test_mode": self.test_mode,
            "vector_indexes_count": storage_stats["total_indexes"]
        }