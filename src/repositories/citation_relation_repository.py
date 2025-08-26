"""
Citation Relation Repository Implementation
Implements ICitationRelationRepository interface following Repository pattern
and SOLID principles.
Handles all database operations for CitationRelationModel entities.
"""

import logging
from typing import Any

from src.database.connection import DatabaseConnection
from src.database.models import CitationRelationModel
from src.interfaces.repository_interfaces import ICitationRelationRepository
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class CitationRelationRepository(
    BaseRepository[CitationRelationModel], ICitationRelationRepository
):
    """
    {
        "name": "CitationRelationRepository",
        "version": "1.0.0",
        "description": (
            "Repository for CitationRelationModel following SOLID principles "
            "and Repository pattern."
        ),
        "dependencies": [
            "DatabaseConnection", "BaseRepository", "ICitationRelationRepository"
        ],
        "interface": {
            "inputs": ["DatabaseConnection"],
            "outputs": "Citation relation CRUD operations and network analysis"
        }
    }
    Citation relation repository implementation providing CRUD operations
    and network analysis.
    Follows Single Responsibility Principle - handles only citation
    relationship data access.
    Implements Interface Segregation Principle - implements only needed
    relation methods.
    """

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize citation relation repository.

        Args:
            db_connection: Database connection following Dependency Inversion Principle
        """
        super().__init__(db_connection)
        self.db = db_connection

    def get_table_name(self) -> str:
        """Get the database table name for citation relations."""
        return "citation_relations"

    def to_model(self, row: dict[str, Any]) -> CitationRelationModel:
        """Convert database row to CitationRelationModel."""
        return CitationRelationModel.from_database_row(row)

    def to_database_dict(self, model: CitationRelationModel) -> dict[str, Any]:
        """Convert CitationRelationModel to database dictionary."""
        return model.to_database_dict()

    def create(self, relation: CitationRelationModel) -> CitationRelationModel:
        """
        Create a new citation relation in the database.

        Args:
            relation: Citation relation model to create

        Returns:
            Created relation with assigned ID

        Raises:
            DatabaseError: If creation fails
        """
        try:
            relation_dict = relation.to_database_dict()
            # Remove id for insertion
            relation_dict.pop("id", None)

            # Build SQL dynamically based on provided fields
            columns = list(relation_dict.keys())
            placeholders = ["?" for _ in columns]
            values = [relation_dict[col] for col in columns]

            sql = f"""
                INSERT INTO citation_relations ({", ".join(columns)})
                VALUES ({", ".join(placeholders)})
            """

            self.db.execute(sql, values)

            # Get the inserted ID
            result = self.db.fetch_one("SELECT last_insert_rowid() as id")
            if result:
                relation.id = result["id"]

            logger.info(f"Created citation relation with ID {relation.id}")
            return relation

        except Exception as e:
            logger.error(f"Failed to create citation relation: {e}")
            raise

    def get_by_id(self, relation_id: int) -> CitationRelationModel | None:
        """
        Get citation relation by ID.

        Args:
            relation_id: Relation ID

        Returns:
            Citation relation model or None if not found
        """
        try:
            sql = "SELECT * FROM citation_relations WHERE id = ?"
            result = self.db.fetch_one(sql, (relation_id,))

            if result:
                return CitationRelationModel.from_database_row(result)

            return None

        except Exception as e:
            logger.error(f"Failed to get citation relation by ID {relation_id}: {e}")
            raise

    def update(self, relation: CitationRelationModel) -> CitationRelationModel:
        """
        Update an existing citation relation.

        Args:
            relation: Citation relation model to update

        Returns:
            Updated relation model

        Raises:
            ValueError: If relation has no ID
            DatabaseError: If update fails
        """
        if not relation.id:
            raise ValueError("Citation relation must have an ID to update")

        try:
            relation_dict = relation.to_database_dict()
            relation_dict.pop("id")  # Don't update the ID

            # Build dynamic UPDATE SQL
            set_clauses = [f"{col} = ?" for col in relation_dict]
            values = list(relation_dict.values()) + [relation.id]

            sql = f"""
                UPDATE citation_relations
                SET {", ".join(set_clauses)}
                WHERE id = ?
            """

            self.db.execute(sql, values)

            logger.info(f"Updated citation relation with ID {relation.id}")
            return relation

        except Exception as e:
            logger.error(f"Failed to update citation relation {relation.id}: {e}")
            raise

    def delete(self, relation_id: int) -> bool:
        """
        Delete a citation relation by ID.

        Args:
            relation_id: Relation ID to delete

        Returns:
            True if relation was deleted, False if not found

        Raises:
            DatabaseError: If deletion fails
        """
        try:
            sql = "DELETE FROM citation_relations WHERE id = ?"
            self.db.execute(sql, (relation_id,))

            # Check if any rows were affected
            rows_affected = self.db.get_last_change_count()
            success = rows_affected > 0

            if success:
                logger.info(f"Deleted citation relation with ID {relation_id}")
            else:
                logger.warning(
                    f"Citation relation with ID {relation_id} not found for deletion"
                )

            return success

        except Exception as e:
            logger.error(f"Failed to delete citation relation {relation_id}: {e}")
            raise

    def get_by_ids(self, relation_ids: list[int]) -> list[CitationRelationModel]:
        """
        Get multiple citation relations by their IDs.

        Args:
            relation_ids: List of relation IDs to retrieve

        Returns:
            List of found relations (may be fewer than requested if some don't exist)
        """
        if not relation_ids:
            return []

        try:
            # Create placeholders for IN clause
            placeholders = ",".join(["?" for _ in relation_ids])
            sql = f"""
                SELECT * FROM citation_relations
                WHERE id IN ({placeholders})
                ORDER BY id
            """
            results = self.db.fetch_all(sql, tuple(relation_ids))

            relations = [CitationRelationModel.from_database_row(row) for row in results]
            logger.debug(f"Found {len(relations)} relations from {len(relation_ids)} IDs")

            return relations

        except Exception as e:
            logger.error(f"Failed to get citation relations by IDs {relation_ids}: {e}")
            raise

    def find_by_source_document(
        self, source_document_id: int
    ) -> list[CitationRelationModel]:
        """
        Find all relations where specified document is the source.

        Args:
            source_document_id: Source document ID

        Returns:
            List of citation relations originating from the document
        """
        try:
            sql = """
                SELECT * FROM citation_relations
                WHERE source_document_id = ?
                ORDER BY created_at DESC
            """
            results = self.db.fetch_all(sql, (source_document_id,))

            relations = [
                CitationRelationModel.from_database_row(dict(row)) for row in results
            ]
            logger.debug(
                f"Found {len(relations)} relations from source document "
                f"{source_document_id}"
            )

            return relations

        except Exception as e:
            logger.error(
                f"Failed to find relations for source document "
                f"{source_document_id}: {e}"
            )
            raise

    def find_by_target_document(
        self, target_document_id: int
    ) -> list[CitationRelationModel]:
        """
        Find all relations where specified document is the target.

        Args:
            target_document_id: Target document ID

        Returns:
            List of citation relations pointing to the document
        """
        try:
            sql = """
                SELECT * FROM citation_relations
                WHERE target_document_id = ?
                ORDER BY created_at DESC
            """
            results = self.db.fetch_all(sql, (target_document_id,))

            relations = [
                CitationRelationModel.from_database_row(dict(row)) for row in results
            ]
            logger.debug(
                f"Found {len(relations)} relations to target document "
                f"{target_document_id}"
            )

            return relations

        except Exception as e:
            logger.error(
                f"Failed to find relations for target document "
                f"{target_document_id}: {e}"
            )
            raise

    def find_by_citation(self, citation_id: int) -> list[CitationRelationModel]:
        """
        Find all relations involving a specific citation.

        Args:
            citation_id: Citation ID

        Returns:
            List of citation relations involving the citation
        """
        try:
            sql = """
                SELECT * FROM citation_relations
                WHERE source_citation_id = ? OR target_citation_id = ?
                ORDER BY created_at DESC
            """
            results = self.db.fetch_all(sql, (citation_id, citation_id))

            relations = [
                CitationRelationModel.from_database_row(dict(row)) for row in results
            ]
            logger.debug(
                f"Found {len(relations)} relations involving citation {citation_id}"
            )

            return relations

        except Exception as e:
            logger.error(f"Failed to find relations for citation {citation_id}: {e}")
            raise

    def get_citation_network(self, document_id: int, depth: int = 1) -> dict[str, Any]:
        """
        Get citation network for a document up to specified depth.

        Args:
            document_id: Document ID to start from
            depth: Network depth to traverse

        Returns:
            Dictionary containing nodes and edges for network visualization
        """
        try:
            nodes = set()
            edges = []
            processed_docs = set()

            def _traverse_network(doc_id: int, current_depth: int) -> None:
                if current_depth > depth or doc_id in processed_docs:
                    return

                processed_docs.add(doc_id)
                nodes.add(doc_id)

                # Get outgoing citations (documents this one cites)
                outgoing_sql = """
                    SELECT cr.*, d.title as target_title
                    FROM citation_relations cr
                    LEFT JOIN documents d ON cr.target_document_id = d.id
                    WHERE cr.source_document_id = ?
                    AND cr.target_document_id IS NOT NULL
                """
                outgoing = self.db.fetch_all(outgoing_sql, (doc_id,))

                for relation in outgoing:
                    target_id = relation["target_document_id"]
                    if target_id:
                        nodes.add(target_id)
                        edges.append(
                            {
                                "source": doc_id,
                                "target": target_id,
                                "type": relation["relation_type"],
                                "confidence": relation["confidence_score"],
                            }
                        )
                        if current_depth < depth:
                            _traverse_network(target_id, current_depth + 1)

                # Get incoming citations (documents that cite this one)
                incoming_sql = """
                    SELECT cr.*, d.title as source_title
                    FROM citation_relations cr
                    LEFT JOIN documents d ON cr.source_document_id = d.id
                    WHERE cr.target_document_id = ?
                """
                incoming = self.db.fetch_all(incoming_sql, (doc_id,))

                for relation in incoming:
                    source_id = relation["source_document_id"]
                    nodes.add(source_id)
                    edges.append(
                        {
                            "source": source_id,
                            "target": doc_id,
                            "type": relation["relation_type"],
                            "confidence": relation["confidence_score"],
                        }
                    )
                    if current_depth < depth:
                        _traverse_network(source_id, current_depth + 1)

            # Start traversal
            _traverse_network(document_id, 0)

            # Get node details
            node_details = {}
            if nodes:
                placeholders = ",".join(["?" for _ in nodes])
                node_sql = f"""
                    SELECT id, title, created_at
                    FROM documents
                    WHERE id IN ({placeholders})
                """
                node_results = self.db.fetch_all(node_sql, list(nodes))

                for node in node_results:
                    node_details[node["id"]] = {
                        "id": node["id"],
                        "title": node["title"],
                        "created_at": node["created_at"],
                    }

            network = {
                "nodes": [
                    node_details.get(node_id, {"id": node_id}) for node_id in nodes
                ],
                "edges": edges,
                "center_document": document_id,
                "depth": depth,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }

            logger.debug(
                f"Generated citation network for document {document_id} with "
                f"{len(nodes)} nodes and {len(edges)} edges"
            )
            return network

        except Exception as e:
            logger.error(
                f"Failed to generate citation network for document {document_id}: {e}"
            )
            raise

    def get_most_cited_documents(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get most cited documents in the library.

        Args:
            limit: Maximum number of results

        Returns:
            List of documents with citation counts
        """
        try:
            sql = """
                SELECT
                    d.id as document_id,
                    d.title,
                    d.created_at,
                    COUNT(cr.target_document_id) as citation_count
                FROM documents d
                LEFT JOIN citation_relations cr ON d.id = cr.target_document_id
                GROUP BY d.id, d.title, d.created_at
                HAVING citation_count > 0
                ORDER BY citation_count DESC, d.created_at DESC
                LIMIT ?
            """
            results = self.db.fetch_all(sql, (limit,))

            cited_docs = [
                {
                    "document_id": row["document_id"],
                    "title": row["title"],
                    "citation_count": row["citation_count"],
                    "created_at": row["created_at"],
                }
                for row in results
            ]

            logger.debug(f"Found {len(cited_docs)} most cited documents")
            return cited_docs

        except Exception as e:
            logger.error(f"Failed to get most cited documents: {e}")
            raise

    def cleanup_orphaned_relations(self) -> int:
        """
        Remove relations pointing to non-existent documents or citations.

        Returns:
            Number of orphaned relations removed
        """
        try:
            # Remove relations with invalid source documents
            sql1 = """
                DELETE FROM citation_relations
                WHERE source_document_id NOT IN (SELECT id FROM documents)
            """
            self.db.execute(sql1)
            removed_source = self.db.get_last_change_count()

            # Remove relations with invalid target documents (if specified)
            sql2 = """
                DELETE FROM citation_relations
                WHERE target_document_id IS NOT NULL
                AND target_document_id NOT IN (SELECT id FROM documents)
            """
            self.db.execute(sql2)
            removed_target = self.db.get_last_change_count()

            # Remove relations with invalid source citations
            sql3 = """
                DELETE FROM citation_relations
                WHERE source_citation_id NOT IN (SELECT id FROM citations)
            """
            self.db.execute(sql3)
            removed_source_citation = self.db.get_last_change_count()

            # Remove relations with invalid target citations (if specified)
            sql4 = """
                DELETE FROM citation_relations
                WHERE target_citation_id IS NOT NULL
                AND target_citation_id NOT IN (SELECT id FROM citations)
            """
            self.db.execute(sql4)
            removed_target_citation = self.db.get_last_change_count()

            total_removed = (
                removed_source
                + removed_target
                + removed_source_citation
                + removed_target_citation
            )

            logger.info(f"Cleaned up {total_removed} orphaned citation relations")
            return total_removed

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned relations: {e}")
            raise

    def get_relations_by_source(
        self, source_document_id: int
    ) -> list[CitationRelationModel]:
        """
        Get all citation relations by source document.

        Args:
            source_document_id: Source document ID

        Returns:
            List of citation relations
        """
        try:
            sql = """
                SELECT * FROM citation_relations
                WHERE source_document_id = ?
                ORDER BY created_at DESC
            """
            results = self.db.fetch_all(sql, (source_document_id,))

            relations = [
                CitationRelationModel.from_database_row(dict(row)) for row in results
            ]
            logger.debug(
                f"Found {len(relations)} relations for source document "
                f"{source_document_id}"
            )
            return relations

        except Exception as e:
            logger.error(
                f"Failed to get relations by source document {source_document_id}: {e}"
            )
            raise

    def get_all_relations(self) -> list[CitationRelationModel]:
        """
        Get all citation relations in the system.

        Returns:
            List of all citation relations
        """
        try:
            sql = """
                SELECT * FROM citation_relations
                ORDER BY created_at DESC
            """
            results = self.db.fetch_all(sql)

            relations = [
                CitationRelationModel.from_database_row(dict(row)) for row in results
            ]
            logger.debug(f"Retrieved {len(relations)} total citation relations")
            return relations

        except Exception as e:
            logger.error(f"Failed to get all citation relations: {e}")
            raise
