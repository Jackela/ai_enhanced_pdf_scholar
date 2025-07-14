"""
Vector Index Repository

Implements data access layer for vector indexes with relationship management.
Provides methods for index management and document-index associations.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from .base_repository import BaseRepository
from src.database.models import VectorIndexModel
from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class VectorIndexRepository(BaseRepository[VectorIndexModel]):
    """
    {
        "name": "VectorIndexRepository",
        "version": "1.0.0",
        "description": "Repository for vector index data access with document relationship management.",
        "dependencies": ["BaseRepository", "VectorIndexModel", "DatabaseConnection"],
        "interface": {
            "inputs": ["database_connection: DatabaseConnection"],
            "outputs": "Vector index CRUD operations with document associations"
        }
    }
    
    Repository for vector index entities with document relationship management.
    Handles index lifecycle, cleanup, and integrity verification.
    """
    
    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize vector index repository.
        
        Args:
            db_connection: Database connection instance
        """
        super().__init__(db_connection)
    
    def get_table_name(self) -> str:
        """Get the database table name."""
        return "vector_indexes"
    
    def to_model(self, row: Dict[str, Any]) -> VectorIndexModel:
        """Convert database row to VectorIndexModel."""
        return VectorIndexModel.from_database_row(row)
    
    def to_database_dict(self, model: VectorIndexModel) -> Dict[str, Any]:
        """Convert VectorIndexModel to database dictionary."""
        return model.to_database_dict()
    
    def find_by_document_id(self, document_id: int) -> Optional[VectorIndexModel]:
        """
        Find vector index by document ID.
        
        Args:
            document_id: Document primary key
            
        Returns:
            Vector index model or None if not found
        """
        try:
            query = "SELECT * FROM vector_indexes WHERE document_id = ?"
            row = self.db.fetch_one(query, (document_id,))
            
            if row:
                return self.to_model(dict(row))
            return None
            
        except Exception as e:
            logger.error(f"Failed to find vector index by document ID {document_id}: {e}")
            raise
    
    def find_by_index_hash(self, index_hash: str) -> Optional[VectorIndexModel]:
        """
        Find vector index by index hash.
        
        Args:
            index_hash: Unique index hash
            
        Returns:
            Vector index model or None if not found
        """
        try:
            query = "SELECT * FROM vector_indexes WHERE index_hash = ?"
            row = self.db.fetch_one(query, (index_hash,))
            
            if row:
                return self.to_model(dict(row))
            return None
            
        except Exception as e:
            logger.error(f"Failed to find vector index by hash {index_hash}: {e}")
            raise
    
    def find_all_with_documents(self) -> List[Dict[str, Any]]:
        """
        Find all vector indexes with associated document information.
        
        Returns:
            List of dictionaries with index and document data
        """
        try:
            query = """
            SELECT 
                vi.*,
                d.title as document_title,
                d.file_path as document_path,
                d.file_size as document_size
            FROM vector_indexes vi
            JOIN documents d ON vi.document_id = d.id
            ORDER BY vi.created_at DESC
            """
            
            rows = self.db.fetch_all(query)
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to find vector indexes with documents: {e}")
            raise
    
    def delete_by_document_id(self, document_id: int) -> bool:
        """
        Delete vector index by document ID.
        
        Args:
            document_id: Document primary key
            
        Returns:
            True if deleted, False if not found
        """
        try:
            query = "DELETE FROM vector_indexes WHERE document_id = ?"
            result = self.db.execute(query, (document_id,))
            
            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Deleted vector index for document {document_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete vector index for document {document_id}: {e}")
            raise
    
    def find_orphaned_indexes(self) -> List[VectorIndexModel]:
        """
        Find vector indexes that don't have corresponding documents.
        
        Returns:
            List of orphaned vector indexes
        """
        try:
            query = """
            SELECT vi.* 
            FROM vector_indexes vi 
            LEFT JOIN documents d ON vi.document_id = d.id 
            WHERE d.id IS NULL
            """
            
            rows = self.db.fetch_all(query)
            return [self.to_model(dict(row)) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to find orphaned vector indexes: {e}")
            raise
    
    def find_invalid_indexes(self) -> List[VectorIndexModel]:
        """
        Find vector indexes where the index files no longer exist.
        
        Returns:
            List of invalid vector indexes
        """
        try:
            all_indexes = self.find_all()
            invalid_indexes = []
            
            for index in all_indexes:
                if not index.is_index_available():
                    invalid_indexes.append(index)
                    logger.debug(f"Found invalid index: {index.index_path}")
            
            return invalid_indexes
            
        except Exception as e:
            logger.error(f"Failed to find invalid vector indexes: {e}")
            raise
    
    def cleanup_orphaned_indexes(self) -> int:
        """
        Remove orphaned vector indexes from database.
        
        Returns:
            Number of indexes cleaned up
        """
        try:
            orphaned = self.find_orphaned_indexes()
            
            if not orphaned:
                logger.info("No orphaned vector indexes found")
                return 0
            
            orphaned_ids = [index.id for index in orphaned]
            
            # Delete orphaned indexes
            query = f"DELETE FROM vector_indexes WHERE id IN ({','.join(['?' for _ in orphaned_ids])})"
            result = self.db.execute(query, tuple(orphaned_ids))
            
            cleaned_count = result.rowcount
            logger.info(f"Cleaned up {cleaned_count} orphaned vector indexes")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned vector indexes: {e}")
            raise
    
    def cleanup_invalid_indexes(self, remove_files: bool = False) -> int:
        """
        Remove invalid vector indexes and optionally clean up files.
        
        Args:
            remove_files: Whether to also remove index files from disk
            
        Returns:
            Number of indexes cleaned up
        """
        try:
            invalid = self.find_invalid_indexes()
            
            if not invalid:
                logger.info("No invalid vector indexes found")
                return 0
            
            cleaned_count = 0
            
            for index in invalid:
                try:
                    # Remove from database
                    if self.delete(index.id):
                        cleaned_count += 1
                        logger.debug(f"Removed invalid index from database: {index.id}")
                    
                    # Optionally remove files
                    if remove_files and Path(index.index_path).exists():
                        import shutil
                        shutil.rmtree(index.index_path, ignore_errors=True)
                        logger.debug(f"Removed index files: {index.index_path}")
                        
                except Exception as e:
                    logger.warning(f"Failed to cleanup individual index {index.id}: {e}")
                    continue
            
            logger.info(f"Cleaned up {cleaned_count} invalid vector indexes")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup invalid vector indexes: {e}")
            raise
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """
        Get vector index repository statistics.
        
        Returns:
            Dictionary with index statistics
        """
        try:
            stats = {}
            
            # Total count
            stats["total_indexes"] = self.count()
            
            # Chunk statistics
            chunk_query = """
            SELECT 
                COUNT(*) as count,
                AVG(chunk_count) as avg_chunks,
                MIN(chunk_count) as min_chunks,
                MAX(chunk_count) as max_chunks,
                SUM(chunk_count) as total_chunks
            FROM vector_indexes 
            WHERE chunk_count IS NOT NULL
            """
            chunk_result = self.db.fetch_one(chunk_query)
            if chunk_result:
                stats["chunk_stats"] = dict(chunk_result)
            
            # Document coverage
            coverage_query = """
            SELECT 
                COUNT(DISTINCT d.id) as documents_with_index,
                (SELECT COUNT(*) FROM documents) as total_documents
            FROM documents d
            JOIN vector_indexes vi ON d.id = vi.document_id
            """
            coverage_result = self.db.fetch_one(coverage_query)
            if coverage_result:
                stats["coverage"] = dict(coverage_result)
                if stats["coverage"]["total_documents"] > 0:
                    stats["coverage"]["coverage_percentage"] = (
                        stats["coverage"]["documents_with_index"] / 
                        stats["coverage"]["total_documents"] * 100
                    )
            
            # Orphaned and invalid counts
            stats["orphaned_count"] = len(self.find_orphaned_indexes())
            stats["invalid_count"] = len(self.find_invalid_indexes())
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get vector index statistics: {e}")
            raise
    
    def verify_index_integrity(self, index_id: int) -> Dict[str, Any]:
        """
        Verify the integrity of a specific vector index.
        
        Args:
            index_id: Vector index ID
            
        Returns:
            Dictionary with integrity check results
        """
        try:
            index = self.find_by_id(index_id)
            if not index:
                return {"exists": False, "error": "Index not found in database"}
            
            result = {
                "exists": True,
                "index_id": index_id,
                "document_id": index.document_id,
                "index_path": index.index_path,
                "index_hash": index.index_hash,
                "files_exist": index.is_index_available(),
                "errors": []
            }
            
            # Check if document still exists
            doc_check = self.db.fetch_one("SELECT id FROM documents WHERE id = ?", (index.document_id,))
            result["document_exists"] = doc_check is not None
            
            if not result["document_exists"]:
                result["errors"].append("Associated document no longer exists")
            
            if not result["files_exist"]:
                result["errors"].append("Index files are missing or incomplete")
            
            # Check index path accessibility
            try:
                index_path = Path(index.index_path)
                result["path_accessible"] = index_path.exists() and index_path.is_dir()
            except Exception as e:
                result["path_accessible"] = False
                result["errors"].append(f"Index path not accessible: {e}")
            
            result["is_valid"] = (
                result["document_exists"] and 
                result["files_exist"] and 
                result["path_accessible"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to verify index integrity for {index_id}: {e}")
            return {"exists": False, "error": str(e)}