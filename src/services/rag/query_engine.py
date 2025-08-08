"""
RAG Query Engine Service

Handles vector index loading and query execution including:
- Loading existing vector indexes from storage
- Query processing and response generation
- Index state management and caching
- Query result optimization

This service focuses solely on querying operations and provides
a clean interface for document query functionality.
"""

import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex, QueryEngine

from src.database.models import DocumentModel, VectorIndexModel
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from .file_manager import RAGFileManager

logger = logging.getLogger(__name__)


class RAGQueryError(Exception):
    """Base exception for RAG query errors."""
    pass


class IndexLoadError(RAGQueryError):
    """Exception raised when index loading fails."""
    pass


class QueryExecutionError(RAGQueryError):
    """Exception raised when query execution fails."""
    pass


class RAGQueryEngine:
    """
    Handles vector index loading and query execution.
    
    Responsibilities:
    - Loading vector indexes from persistent storage
    - Managing current index state and caching
    - Processing user queries against loaded indexes
    - Query result generation and formatting
    """
    
    def __init__(
        self,
        document_repo: DocumentRepository,
        vector_repo: VectorIndexRepository,
        file_manager: RAGFileManager,
        test_mode: bool = False
    ):
        """
        Initialize RAG query engine.
        
        Args:
            document_repo: Document repository instance
            vector_repo: Vector index repository instance
            file_manager: RAG file manager instance
            test_mode: If True, use mock indexes for testing
        """
        self.document_repo = document_repo
        self.vector_repo = vector_repo
        self.file_manager = file_manager
        self.test_mode = test_mode
        
        # Current state
        self.current_index: Optional['VectorStoreIndex'] = None
        self.current_document_id: Optional[int] = None
        self.current_vector_index: Optional[VectorIndexModel] = None
        self.current_pdf_path: Optional[str] = None
        
        logger.info("RAG Query Engine initialized")

    def load_index_for_document(self, document_id: int) -> bool:
        """
        Load vector index for a specific document.
        
        Args:
            document_id: Document ID to load index for
            
        Returns:
            True if index loaded successfully
            
        Raises:
            IndexLoadError: If loading fails or index not found
        """
        logger.info(f"Loading vector index for document {document_id}")
        
        try:
            # Get document from repository
            document = self.document_repo.find_by_id(document_id)
            if not document:
                raise IndexLoadError(f"Document not found: {document_id}")

            # Get vector index from repository
            vector_index = self.vector_repo.find_by_document_id(document_id)
            if not vector_index:
                raise IndexLoadError(f"No vector index found for document {document_id}")

            # Verify index files exist
            if not self.file_manager.verify_index_files(vector_index.index_path):
                raise IndexLoadError(f"Vector index files missing or corrupted: {vector_index.index_path}")

            # Load the actual index
            loaded_index = self._load_vector_index(vector_index)
            
            # Update current state
            self.current_index = loaded_index
            self.current_document_id = document_id
            self.current_vector_index = vector_index
            self.current_pdf_path = document.file_path

            # Update document access time
            self.document_repo.update_access_time(document_id)

            logger.info(f"Vector index loaded successfully for document {document_id}")
            return True
            
        except IndexLoadError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error loading index for document {document_id}: {e}"
            logger.error(error_msg)
            raise IndexLoadError(error_msg) from e

    def _load_vector_index(self, vector_index: VectorIndexModel) -> 'VectorStoreIndex':
        """
        Load vector index from storage.
        
        Args:
            vector_index: Vector index model with storage path
            
        Returns:
            Loaded VectorStoreIndex instance
            
        Raises:
            IndexLoadError: If loading fails
        """
        try:
            if self.test_mode:
                # Create mock index for testing
                return self._create_mock_index(vector_index.document_id)
                
            from llama_index.core import StorageContext, load_index_from_storage

            storage_context = StorageContext.from_defaults(
                persist_dir=vector_index.index_path
            )
            loaded_index = load_index_from_storage(storage_context)
            
            logger.debug(f"Loaded vector index from: {vector_index.index_path}")
            return loaded_index
            
        except Exception as e:
            error_msg = f"Failed to load vector index from {vector_index.index_path}: {e}"
            logger.error(error_msg)
            raise IndexLoadError(error_msg) from e

    def _create_mock_index(self, document_id: int) -> Any:
        """Create a mock index for testing purposes."""
        
        class MockQueryEngine:
            def __init__(self, doc_id: int):
                self.doc_id = doc_id
                
            def query(self, query_text: str) -> 'MockResponse':
                return MockResponse(f"Mock response for document {self.doc_id}: {query_text}")
        
        class MockResponse:
            def __init__(self, response_text: str):
                self.response_text = response_text
                
            def __str__(self) -> str:
                return self.response_text
        
        class MockIndex:
            def __init__(self, doc_id: int):
                self.doc_id = doc_id
                
            def as_query_engine(self, **kwargs) -> MockQueryEngine:
                return MockQueryEngine(self.doc_id)
                
        return MockIndex(document_id)

    def query_document(self, query: str, document_id: int) -> str:
        """
        Query a specific document using its vector index.
        
        Args:
            query: User query string
            document_id: Document ID to query
            
        Returns:
            RAG response string
            
        Raises:
            QueryExecutionError: If query execution fails
        """
        query_start_time = datetime.now()
        logger.info(f"Querying document {document_id} with query: {query[:100]}...")
        
        try:
            # Load index if not current or different document
            if self.current_document_id != document_id or not self.current_index:
                try:
                    self.load_index_for_document(document_id)
                except IndexLoadError as e:
                    raise QueryExecutionError(f"Failed to load index for query: {e}") from e

            # Execute query
            response = self._execute_query(query)
            
            query_duration = datetime.now() - query_start_time
            logger.info(f"Query completed for document {document_id} in {query_duration.total_seconds():.2f}s")
            
            return response
            
        except QueryExecutionError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error during query execution: {e}"
            logger.error(error_msg)
            raise QueryExecutionError(error_msg) from e

    def _execute_query(self, query_text: str) -> str:
        """
        Execute query against current loaded index.
        
        Args:
            query_text: User query string
            
        Returns:
            Query response string
            
        Raises:
            QueryExecutionError: If query execution fails
        """
        if not self.current_index:
            raise QueryExecutionError("No vector index loaded. Load an index first.")
            
        try:
            if self.test_mode:
                return f"Test mode response for query: {query_text}"
                
            # Create query engine and execute query
            query_engine = self.current_index.as_query_engine()
            response = query_engine.query(query_text)
            
            return str(response)
            
        except Exception as e:
            error_msg = f"Query execution failed: {e}"
            logger.error(error_msg)
            raise QueryExecutionError(error_msg) from e

    def query_current_document(self, query: str) -> str:
        """
        Query the currently loaded document.
        
        Args:
            query: User query string
            
        Returns:
            RAG response string
            
        Raises:
            QueryExecutionError: If no document is loaded or query fails
        """
        if not self.current_document_id:
            raise QueryExecutionError("No document currently loaded")
            
        return self.query_document(query, self.current_document_id)

    def get_current_document_info(self) -> Dict[str, Any]:
        """
        Get information about the currently loaded document and index.
        
        Returns:
            Dictionary with current document information
        """
        return {
            "current_document_id": self.current_document_id,
            "has_loaded_index": self.current_index is not None,
            "current_pdf_path": self.current_pdf_path,
            "vector_index_info": {
                "index_id": self.current_vector_index.id if self.current_vector_index else None,
                "index_path": self.current_vector_index.index_path if self.current_vector_index else None,
                "chunk_count": self.current_vector_index.chunk_count if self.current_vector_index else 0,
                "created_at": self.current_vector_index.created_at.isoformat() if self.current_vector_index and self.current_vector_index.created_at else None
            } if self.current_vector_index else None,
            "test_mode": self.test_mode
        }

    def get_document_query_status(self, document_id: int) -> Dict[str, Any]:
        """
        Get query readiness status for a document.
        
        Args:
            document_id: Document ID to check
            
        Returns:
            Dictionary with query status information
        """
        status = {
            "document_id": document_id,
            "can_query": False,
            "has_index": False,
            "index_valid": False,
            "index_path": None,
            "chunk_count": 0,
            "created_at": None,
            "is_currently_loaded": False,
            "error": None
        }
        
        try:
            # Check if vector index exists
            vector_index = self.vector_repo.find_by_document_id(document_id)
            if vector_index:
                status["has_index"] = True
                status["index_path"] = vector_index.index_path
                status["chunk_count"] = vector_index.chunk_count or 0
                status["created_at"] = vector_index.created_at.isoformat() if vector_index.created_at else None
                
                # Verify index files
                status["index_valid"] = self.file_manager.verify_index_files(vector_index.index_path)
                status["can_query"] = status["index_valid"]
                
                # Check if currently loaded
                status["is_currently_loaded"] = (
                    self.current_document_id == document_id and 
                    self.current_index is not None
                )
                
        except Exception as e:
            logger.error(f"Failed to get query status for document {document_id}: {e}")
            status["error"] = str(e)
            
        return status

    def clear_current_index(self) -> None:
        """Clear the currently loaded index and reset state."""
        self.current_index = None
        self.current_document_id = None
        self.current_vector_index = None
        self.current_pdf_path = None
        logger.debug("Current index state cleared")

    def preload_index(self, document_id: int) -> bool:
        """
        Preload index for a document to improve query performance.
        
        Args:
            document_id: Document ID to preload
            
        Returns:
            True if preloading was successful
        """
        try:
            self.load_index_for_document(document_id)
            logger.info(f"Index preloaded successfully for document {document_id}")
            return True
            
        except IndexLoadError as e:
            logger.warning(f"Failed to preload index for document {document_id}: {e}")
            return False

    def get_query_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the query engine.
        
        Returns:
            Dictionary with service statistics
        """
        stats = {
            "service_name": "RAGQueryEngine",
            "test_mode": self.test_mode,
            "current_state": self.get_current_document_info(),
            "storage_stats": self.file_manager.get_storage_statistics()
        }
        
        return stats