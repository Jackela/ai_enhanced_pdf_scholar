"""
Citation Repository Implementation
Implements ICitationRepository interface following Repository pattern and SOLID principles.
Handles all database operations for CitationModel entities.
"""

import logging
from typing import Any

from src.database.connection import DatabaseConnection
from src.database.models import CitationModel
from src.interfaces.repository_interfaces import ICitationRepository
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CitationRepository(BaseRepository[CitationModel], ICitationRepository):
    """
    {
        "name": "CitationRepository",
        "version": "1.0.0",
        "description": "Repository for CitationModel following SOLID principles and Repository pattern.",
        "dependencies": ["DatabaseConnection", "BaseRepository", "ICitationRepository"],
        "interface": {
            "inputs": ["DatabaseConnection"],
            "outputs": "Citation CRUD operations and specialized queries"
        }
    }
    Citation repository implementation providing CRUD operations and specialized queries.
    Follows Single Responsibility Principle - handles only citation data access.
    Implements Interface Segregation Principle - implements only needed citation methods.
    """

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize citation repository.
        
        Args:
            db_connection: Database connection following Dependency Inversion Principle
        """
        super().__init__(db_connection)
        self.db = db_connection

    def get_table_name(self) -> str:
        """Get the database table name for citations."""
        return "citations"

    def to_model(self, row: dict[str, Any]) -> CitationModel:
        """Convert database row to CitationModel."""
        return CitationModel.from_database_row(row)

    def to_database_dict(self, model: CitationModel) -> dict[str, Any]:
        """Convert CitationModel to database dictionary."""
        return model.to_database_dict()

    def create(self, citation: CitationModel) -> CitationModel:
        """
        Create a new citation in the database.
        
        Args:
            citation: Citation model to create
            
        Returns:
            Created citation with assigned ID
            
        Raises:
            DatabaseError: If creation fails
        """
        try:
            citation_dict = citation.to_database_dict()
            # Remove id for insertion
            citation_dict.pop("id", None)
            
            # Build SQL dynamically based on provided fields
            columns = list(citation_dict.keys())
            placeholders = ["?" for _ in columns]
            values = [citation_dict[col] for col in columns]
            
            sql = f"""
                INSERT INTO citations ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """
            
            self.db.execute(sql, values)
            
            # Get the inserted ID
            result = self.db.fetch_one("SELECT last_insert_rowid() as id")
            if result:
                citation.id = result["id"]
            
            logger.info(f"Created citation with ID {citation.id}")
            return citation
            
        except Exception as e:
            logger.error(f"Failed to create citation: {e}")
            raise

    def get_by_id(self, citation_id: int) -> CitationModel | None:
        """
        Get citation by ID.
        
        Args:
            citation_id: Citation ID
            
        Returns:
            Citation model or None if not found
        """
        try:
            sql = "SELECT * FROM citations WHERE id = ?"
            result = self.db.fetch_one(sql, (citation_id,))
            
            if result:
                return CitationModel.from_database_row(result)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get citation by ID {citation_id}: {e}")
            raise

    def update(self, citation: CitationModel) -> CitationModel:
        """
        Update an existing citation.
        
        Args:
            citation: Citation model to update
            
        Returns:
            Updated citation model
            
        Raises:
            ValueError: If citation has no ID
            DatabaseError: If update fails
        """
        if not citation.id:
            raise ValueError("Citation must have an ID to update")
            
        try:
            citation_dict = citation.to_database_dict()
            citation_dict.pop("id")  # Don't update the ID
            
            # Build dynamic UPDATE SQL
            set_clauses = [f"{col} = ?" for col in citation_dict.keys()]
            values = list(citation_dict.values()) + [citation.id]
            
            sql = f"""
                UPDATE citations 
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """
            
            self.db.execute(sql, values)
            
            logger.info(f"Updated citation with ID {citation.id}")
            return citation
            
        except Exception as e:
            logger.error(f"Failed to update citation {citation.id}: {e}")
            raise

    def delete(self, citation_id: int) -> bool:
        """
        Delete a citation by ID.
        
        Args:
            citation_id: Citation ID to delete
            
        Returns:
            True if citation was deleted, False if not found
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            sql = "DELETE FROM citations WHERE id = ?"
            self.db.execute(sql, (citation_id,))
            
            # Check if any rows were affected
            rows_affected = self.db.get_last_change_count()
            success = rows_affected > 0
            
            if success:
                logger.info(f"Deleted citation with ID {citation_id}")
            else:
                logger.warning(f"Citation with ID {citation_id} not found for deletion")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete citation {citation_id}: {e}")
            raise

    def find_by_document_id(self, document_id: int) -> list[CitationModel]:
        """
        Find all citations for a specific document.
        
        Args:
            document_id: Document ID to search for
            
        Returns:
            List of citations for the document
        """
        try:
            sql = """
                SELECT * FROM citations 
                WHERE document_id = ?
                ORDER BY created_at DESC
            """
            results = self.db.fetch_all(sql, (document_id,))
            
            citations = [CitationModel.from_database_row(row) for row in results]
            logger.debug(f"Found {len(citations)} citations for document {document_id}")
            
            return citations
            
        except Exception as e:
            logger.error(f"Failed to find citations for document {document_id}: {e}")
            raise

    def search_by_author(self, author: str, limit: int = 50) -> list[CitationModel]:
        """
        Search citations by author name (partial match).
        
        Args:
            author: Author name to search for
            limit: Maximum number of results
            
        Returns:
            List of matching citations
        """
        try:
            sql = """
                SELECT * FROM citations 
                WHERE authors LIKE ? 
                ORDER BY publication_year DESC, created_at DESC
                LIMIT ?
            """
            search_term = f"%{author}%"
            results = self.db.fetch_all(sql, (search_term, limit))
            
            citations = [CitationModel.from_database_row(row) for row in results]
            logger.debug(f"Found {len(citations)} citations for author '{author}'")
            
            return citations
            
        except Exception as e:
            logger.error(f"Failed to search citations by author '{author}': {e}")
            raise

    def search_by_title(self, title: str, limit: int = 50) -> list[CitationModel]:
        """
        Search citations by title (partial match).
        
        Args:
            title: Title keywords to search for
            limit: Maximum number of results
            
        Returns:
            List of matching citations
        """
        try:
            sql = """
                SELECT * FROM citations 
                WHERE title LIKE ? 
                ORDER BY publication_year DESC, created_at DESC
                LIMIT ?
            """
            search_term = f"%{title}%"
            results = self.db.fetch_all(sql, (search_term, limit))
            
            citations = [CitationModel.from_database_row(row) for row in results]
            logger.debug(f"Found {len(citations)} citations for title '{title}'")
            
            return citations
            
        except Exception as e:
            logger.error(f"Failed to search citations by title '{title}': {e}")
            raise

    def find_by_doi(self, doi: str) -> CitationModel | None:
        """
        Find citation by DOI (exact match).
        
        Args:
            doi: DOI to search for
            
        Returns:
            Citation model or None if not found
        """
        try:
            sql = "SELECT * FROM citations WHERE doi = ?"
            result = self.db.fetch_one(sql, (doi,))
            
            if result:
                citation = CitationModel.from_database_row(result)
                logger.debug(f"Found citation with DOI {doi}")
                return citation
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find citation by DOI '{doi}': {e}")
            raise

    def find_by_year_range(self, start_year: int, end_year: int) -> list[CitationModel]:
        """
        Find citations within a year range.
        
        Args:
            start_year: Start year (inclusive)
            end_year: End year (inclusive)
            
        Returns:
            List of citations in the year range
        """
        try:
            sql = """
                SELECT * FROM citations 
                WHERE publication_year BETWEEN ? AND ?
                ORDER BY publication_year DESC, created_at DESC
            """
            results = self.db.fetch_all(sql, (start_year, end_year))
            
            citations = [CitationModel.from_database_row(row) for row in results]
            logger.debug(f"Found {len(citations)} citations between {start_year}-{end_year}")
            
            return citations
            
        except Exception as e:
            logger.error(f"Failed to find citations in year range {start_year}-{end_year}: {e}")
            raise

    def get_by_type(self, citation_type: str) -> list[CitationModel]:
        """
        Get citations by type (journal, conference, book, etc.).
        
        Args:
            citation_type: Citation type to filter by
            
        Returns:
            List of citations of the specified type
        """
        try:
            sql = """
                SELECT * FROM citations 
                WHERE citation_type = ?
                ORDER BY publication_year DESC, created_at DESC
            """
            results = self.db.fetch_all(sql, (citation_type,))
            
            citations = [CitationModel.from_database_row(row) for row in results]
            logger.debug(f"Found {len(citations)} citations of type '{citation_type}'")
            
            return citations
            
        except Exception as e:
            logger.error(f"Failed to find citations by type '{citation_type}': {e}")
            raise

    def get_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive citation statistics.
        
        Returns:
            Dictionary containing various citation statistics
        """
        try:
            stats: dict[str, Any] = {}
            
            # Total citations
            result = self.db.fetch_one("SELECT COUNT(*) as count FROM citations")
            stats["total_citations"] = result["count"] if result else 0
            
            # Complete citations (have authors, title, and year)
            result = self.db.fetch_one("""
                SELECT COUNT(*) as count FROM citations 
                WHERE authors IS NOT NULL 
                AND title IS NOT NULL 
                AND publication_year IS NOT NULL
            """)
            stats["complete_citations"] = result["count"] if result else 0
            
            # Average confidence score
            result = self.db.fetch_one("""
                SELECT AVG(confidence_score) as avg_confidence 
                FROM citations 
                WHERE confidence_score IS NOT NULL
            """)
            stats["avg_confidence_score"] = result["avg_confidence"] if result and result["avg_confidence"] else 0.0
            
            # Citation types breakdown
            type_results = self.db.fetch_all("""
                SELECT citation_type, COUNT(*) as count 
                FROM citations 
                WHERE citation_type IS NOT NULL
                GROUP BY citation_type
                ORDER BY count DESC
            """)
            stats["citation_types"] = {row["citation_type"]: row["count"] for row in type_results}
            
            # Years breakdown (last 10 years)
            year_results = self.db.fetch_all("""
                SELECT publication_year, COUNT(*) as count 
                FROM citations 
                WHERE publication_year IS NOT NULL
                AND publication_year >= datetime('now', '-10 years')
                GROUP BY publication_year
                ORDER BY publication_year DESC
            """)
            stats["years_breakdown"] = {row["publication_year"]: row["count"] for row in year_results}
            
            # Document coverage
            result = self.db.fetch_one("""
                SELECT COUNT(DISTINCT document_id) as docs_with_citations 
                FROM citations
            """)
            stats["documents_with_citations"] = result["docs_with_citations"] if result else 0
            
            logger.debug("Generated citation statistics")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get citation statistics: {e}")
            raise