"""
Citation Service Implementation
Implements business logic for citation management following SOLID principles.
"""

from __future__ import annotations

import logging
from typing import Any

from src.database.models import CitationModel, CitationRelationModel, DocumentModel
from src.interfaces.repository_interfaces import (
    ICitationRelationRepository,
    ICitationRepository,
)

logger = logging.getLogger(__name__)


class CitationService:
    """
    {
        "name": "CitationService",
        "version": "1.0.0",
        "description": "Business logic service for citation management following SOLID principles.",
        "dependencies": ["ICitationRepository", "ICitationRelationRepository"],
        "interface": {
            "inputs": ["Repository interfaces"],
            "outputs": "Citation business operations"
        }
    }
    Citation service providing business logic for citation management.
    Follows Single Responsibility Principle - handles only citation business logic.
    Implements Dependency Inversion Principle - depends on repository abstractions.
    """

    def __init__(
        self,
        citation_repository: ICitationRepository,
        relation_repository: ICitationRelationRepository,
    ) -> None:
        """
        Initialize citation service.

        Args:
            citation_repository: Citation repository interface
            relation_repository: Citation relation repository interface
        """
        self.citation_repo: ICitationRepository = citation_repository
        self.relation_repo: ICitationRelationRepository = relation_repository

    def extract_citations_from_document(
        self, document: DocumentModel
    ) -> list[CitationModel]:
        """
        Extract citations from a document.

        Args:
            document: Document to extract citations from

        Returns:
            List of extracted citation models

        Raises:
            ValueError: If document is invalid
        """
        try:
            if not document or not document.id:
                raise ValueError("Document must have a valid ID")

            logger.info(f"Extracting citations from document {document.id}")

            # For now, return a simple mock citation
            # This will be enhanced with actual parsing logic
            sample_citation = CitationModel(
                document_id=document.id,
                raw_text="Sample citation extracted from document",
                authors="Sample Author",
                title="Sample Title",
                publication_year=2023,
                confidence_score=0.8,
            )

            # Create the citation in the repository
            created_citation = self.citation_repo.create(sample_citation)

            logger.info(
                f"Successfully extracted and created citation {created_citation.id}"
            )
            return [created_citation]

        except Exception as e:
            logger.error(
                f"Failed to extract citations from document {document.id}: {e}"
            )
            raise

    def get_citations_for_document(self, document_id: int) -> list[CitationModel]:
        """
        Get all citations for a specific document.

        Args:
            document_id: Document ID

        Returns:
            List of citations for the document
        """
        try:
            logger.debug(f"Getting citations for document {document_id}")
            citations = self.citation_repo.find_by_document_id(document_id)
            logger.debug(f"Found {len(citations)} citations for document {document_id}")
            return citations

        except Exception as e:
            logger.error(f"Failed to get citations for document {document_id}: {e}")
            raise

    def search_citations_by_author(
        self, author: str, limit: int = 50
    ) -> list[CitationModel]:
        """
        Search citations by author name.

        Args:
            author: Author name to search for
            limit: Maximum number of results

        Returns:
            List of matching citations
        """
        try:
            logger.debug(f"Searching citations by author '{author}' with limit {limit}")
            citations = self.citation_repo.search_by_author(author, limit)
            logger.debug(f"Found {len(citations)} citations for author '{author}'")
            return citations

        except Exception as e:
            logger.error(f"Failed to search citations by author '{author}': {e}")
            raise

    def get_citation_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive citation statistics.

        Returns:
            Dictionary containing citation statistics
        """
        try:
            logger.debug("Getting citation statistics")
            stats = self.citation_repo.get_statistics()
            logger.debug("Successfully retrieved citation statistics")
            return stats

        except Exception as e:
            logger.error(f"Failed to get citation statistics: {e}")
            raise

    def build_citation_network(
        self, document_id: int, depth: int = 1
    ) -> dict[str, Any]:
        """
        Build comprehensive citation network for a document with enhanced analytics.

        Args:
            document_id: Document ID to start from
            depth: Network depth to traverse (1-3)

        Returns:
            Enhanced citation network data with metrics and analysis
        """
        try:
            logger.debug(
                f"Building citation network for document {document_id} with depth {depth}"
            )

            # Validate depth parameter
            if not 1 <= depth <= 3:
                raise ValueError("Depth must be between 1 and 3")

            # Get base network from repository
            network = self.relation_repo.get_citation_network(document_id, depth)

            # Enhance with network metrics
            network = self._enhance_network_with_metrics(network)

            # Add citation density analysis
            network["analytics"] = self._calculate_network_analytics(network)

            # Add influential documents identification
            network["influential_documents"] = self._identify_influential_documents(
                network
            )

            logger.debug(
                f"Successfully built enhanced citation network with {network.get('total_nodes', 0)} nodes"
            )
            return network

        except Exception as e:
            logger.error(
                f"Failed to build citation network for document {document_id}: {e}"
            )
            raise

    def create_citation_relation(
        self,
        source_document_id: int,
        source_citation_id: int,
        target_document_id: int | None = None,
        target_citation_id: int | None = None,
        relation_type: str = "cites",
        confidence_score: float = 1.0,
    ) -> CitationRelationModel:
        """
        Create a citation relation between documents or citations.

        Args:
            source_document_id: Source document ID
            source_citation_id: Source citation ID
            target_document_id: Target document ID (optional)
            target_citation_id: Target citation ID (optional)
            relation_type: Type of relation
            confidence_score: Confidence score

        Returns:
            Created citation relation
        """
        try:
            logger.debug(
                f"Creating citation relation from doc {source_document_id} to doc {target_document_id}"
            )

            relation = CitationRelationModel(
                source_document_id=source_document_id,
                source_citation_id=source_citation_id,
                target_document_id=target_document_id,
                target_citation_id=target_citation_id,
                relation_type=relation_type,
                confidence_score=confidence_score,
            )

            created_relation = self.relation_repo.create(relation)
            logger.info(f"Successfully created citation relation {created_relation.id}")
            return created_relation

        except Exception as e:
            logger.error(f"Failed to create citation relation: {e}")
            raise

    def update_citation(self, citation: CitationModel) -> CitationModel:
        """
        Update an existing citation.

        Args:
            citation: Citation to update

        Returns:
            Updated citation
        """
        try:
            logger.debug(f"Updating citation {citation.id}")
            updated_citation = self.citation_repo.update(citation)
            logger.info(f"Successfully updated citation {citation.id}")
            return updated_citation

        except Exception as e:
            logger.error(f"Failed to update citation {citation.id}: {e}")
            raise

    def delete_citation(self, citation_id: int) -> bool:
        """
        Delete a citation.

        Args:
            citation_id: Citation ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            logger.debug(f"Deleting citation {citation_id}")
            success = self.citation_repo.delete(citation_id)

            if success:
                logger.info(f"Successfully deleted citation {citation_id}")
            else:
                logger.warning(f"Citation {citation_id} not found for deletion")

            return success

        except Exception as e:
            logger.error(f"Failed to delete citation {citation_id}: {e}")
            raise

    # Network Analysis Enhancement Methods

    def _enhance_network_with_metrics(self, network: dict[str, Any]) -> dict[str, Any]:
        """
        Enhance network data with node and edge metrics.

        Args:
            network: Base network data

        Returns:
            Enhanced network with metrics
        """
        try:
            nodes = network.get("nodes", [])
            edges = network.get("edges", [])

            # Calculate node degrees (in-degree, out-degree, total degree)
            node_metrics = {}

            for node in nodes:
                node_id = node.get("id")
                if node_id is None:
                    continue

                in_degree = len([e for e in edges if e.get("target") == node_id])
                out_degree = len([e for e in edges if e.get("source") == node_id])

                node_metrics[node_id] = {
                    "in_degree": in_degree,
                    "out_degree": out_degree,
                    "total_degree": in_degree + out_degree,
                    "citing_documents": in_degree,  # Documents that cite this one
                    "cited_documents": out_degree,  # Documents this one cites
                }

                # Add metrics to node data
                node["metrics"] = node_metrics[node_id]

            # Calculate edge weights and confidence distribution
            if edges:
                confidences = [e.get("confidence", 0.0) for e in edges]
                network["edge_metrics"] = {
                    "avg_confidence": sum(confidences) / len(confidences),
                    "min_confidence": min(confidences),
                    "max_confidence": max(confidences),
                    "high_confidence_count": len([c for c in confidences if c >= 0.8]),
                }

            network["node_metrics"] = node_metrics
            return network

        except Exception as e:
            logger.warning(f"Failed to enhance network with metrics: {e}")
            return network

    def _calculate_network_analytics(self, network: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate comprehensive network analytics.

        Args:
            network: Enhanced network data

        Returns:
            Network analytics dictionary
        """
        try:
            nodes = network.get("nodes", [])
            edges = network.get("edges", [])
            total_nodes = len(nodes)
            total_edges = len(edges)

            analytics = {
                "network_size": total_nodes,
                "connection_count": total_edges,
                "density": 0.0,
                "avg_degree": 0.0,
                "citation_patterns": {},
                "temporal_analysis": {},
                "centrality_measures": {},
            }

            if total_nodes == 0:
                return analytics

            # Calculate network density
            max_possible_edges = total_nodes * (total_nodes - 1)
            if max_possible_edges > 0:
                analytics["density"] = total_edges / max_possible_edges

            # Calculate average degree
            node_metrics = network.get("node_metrics", {})
            if node_metrics:
                total_degrees = sum(
                    metrics.get("total_degree", 0) for metrics in node_metrics.values()
                )
                analytics["avg_degree"] = total_degrees / total_nodes

            # Analyze citation patterns
            analytics["citation_patterns"] = self._analyze_citation_patterns(edges)

            # Temporal analysis (if node dates are available)
            analytics["temporal_analysis"] = self._analyze_temporal_patterns(nodes)

            # Calculate centrality measures
            analytics["centrality_measures"] = self._calculate_centrality_measures(
                network
            )

            return analytics

        except Exception as e:
            logger.warning(f"Failed to calculate network analytics: {e}")
            return {"error": str(e)}

    def _identify_influential_documents(
        self, network: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Identify most influential documents in the network.

        Args:
            network: Enhanced network data

        Returns:
            List of influential documents with influence scores
        """
        try:
            nodes = network.get("nodes", [])
            node_metrics = network.get("node_metrics", {})

            influential_docs = []

            for node in nodes:
                node_id = node.get("id")
                if node_id is None or node_id not in node_metrics:
                    continue

                metrics = node_metrics[node_id]

                # Calculate influence score based on multiple factors
                in_degree = metrics.get("in_degree", 0)
                out_degree = metrics.get("out_degree", 0)

                # Influence score: higher weight for being cited (in_degree)
                # but also consider citing others (out_degree) as scholarly engagement
                influence_score = (in_degree * 2.0) + (out_degree * 0.5)

                influential_docs.append(
                    {
                        "document_id": node_id,
                        "title": node.get("title", f"Document {node_id}"),
                        "influence_score": influence_score,
                        "times_cited": in_degree,
                        "documents_cited": out_degree,
                        "created_at": node.get("created_at"),
                        "metrics": metrics,
                    }
                )

            # Sort by influence score descending
            influential_docs.sort(key=lambda x: x["influence_score"], reverse=True)

            # Return top 10 or all if fewer
            return influential_docs[:10]

        except Exception as e:
            logger.warning(f"Failed to identify influential documents: {e}")
            return []

    def _analyze_citation_patterns(self, edges: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze citation patterns in the network.

        Args:
            edges: List of network edges

        Returns:
            Citation pattern analysis
        """
        try:
            if not edges:
                return {"pattern_count": 0}

            # Analyze relation types
            relation_types: dict[str, Any] = {}
            confidence_distribution = {"high": 0, "medium": 0, "low": 0}

            for edge in edges:
                # Count relation types
                rel_type = edge.get("type", "unknown")
                relation_types[rel_type] = relation_types.get(rel_type, 0) + 1

                # Categorize confidence levels
                confidence = edge.get("confidence", 0.0)
                if confidence >= 0.8:
                    confidence_distribution["high"] += 1
                elif confidence >= 0.5:
                    confidence_distribution["medium"] += 1
                else:
                    confidence_distribution["low"] += 1

            return {
                "pattern_count": len(edges),
                "relation_types": relation_types,
                "confidence_distribution": confidence_distribution,
                "dominant_relation_type": (
                    max(relation_types.items(), key=lambda x: x[1])[0]
                    if relation_types
                    else "none"
                ),
            }

        except Exception as e:
            logger.warning(f"Failed to analyze citation patterns: {e}")
            return {"error": str(e)}

    def _analyze_temporal_patterns(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze temporal patterns in the citation network.

        Args:
            nodes: List of network nodes

        Returns:
            Temporal analysis results
        """
        try:
            if not nodes:
                return {"temporal_span": 0}

            # Extract creation dates
            dates = []
            for node in nodes:
                created_at = node.get("created_at")
                if created_at:
                    dates.append(created_at)

            if not dates:
                return {"temporal_span": 0, "date_coverage": "unknown"}

            # Basic temporal analysis
            dates.sort()
            earliest = dates[0]
            latest = dates[-1]

            return {
                "temporal_span": len(dates),
                "earliest_document": earliest,
                "latest_document": latest,
                "date_coverage": f"{earliest} to {latest}",
                "chronological_distribution": len(set[str](dates)),  # Unique dates
            }

        except Exception as e:
            logger.warning(f"Failed to analyze temporal patterns: {e}")
            return {"error": str(e)}

    def _calculate_centrality_measures(self, network: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate centrality measures for network nodes.

        Args:
            network: Network data

        Returns:
            Centrality measures
        """
        try:
            node_metrics = network.get("node_metrics", {})

            if not node_metrics:
                return {"centrality_calculated": False}

            # Degree centrality (normalized)
            max_possible_degree = len(node_metrics) - 1
            degree_centrality = {}

            for node_id, metrics in node_metrics.items():
                if max_possible_degree > 0:
                    degree_centrality[node_id] = (
                        metrics.get("total_degree", 0) / max_possible_degree
                    )
                else:
                    degree_centrality[node_id] = 0.0

            # Find most central nodes
            most_central = sorted(
                degree_centrality.items(), key=lambda x: x[1], reverse=True
            )[:5]

            return {
                "centrality_calculated": True,
                "degree_centrality": degree_centrality,
                "most_central_nodes": [
                    {"node_id": node_id, "centrality": centrality}
                    for node_id, centrality in most_central
                ],
                "avg_centrality": (
                    sum(degree_centrality.values()) / len(degree_centrality)
                    if degree_centrality
                    else 0.0
                ),
            }

        except Exception as e:
            logger.warning(f"Failed to calculate centrality measures: {e}")
            return {"error": str(e)}

    # Advanced Network Analysis Methods

    def get_citation_recommendations(
        self, document_id: int, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Get citation recommendations based on network analysis.

        Args:
            document_id: Document ID to get recommendations for
            limit: Maximum number of recommendations

        Returns:
            List of recommended documents to cite
        """
        try:
            logger.debug(f"Getting citation recommendations for document {document_id}")

            # Get the document's current citation network
            self.build_citation_network(document_id, depth=2)

            # Find documents that are highly cited by similar documents
            recommendations = []

            # Get documents that cite similar papers
            similar_citing_docs = self._find_similar_citing_documents(document_id)

            # Get most cited documents by those similar documents
            recommendations.extend(
                [
                    {
                        "document_id": similar_doc.get("document_id"),
                        "title": similar_doc.get("title"),
                        "recommendation_score": similar_doc.get(
                            "similarity_score", 0.0
                        ),
                        "reason": "cited by similar documents",
                    }
                    for similar_doc in similar_citing_docs[:limit]
                ]
            )

            logger.debug(f"Generated {len(recommendations)} citation recommendations")
            return recommendations

        except Exception as e:
            logger.error(
                f"Failed to get citation recommendations for document {document_id}: {e}"
            )
            return []

    def _find_similar_citing_documents(self, document_id: int) -> list[dict[str, Any]]:
        """
        Find documents that cite similar papers to the given document.

        Args:
            document_id: Document ID to find similar citing patterns for

        Returns:
            List of similar documents
        """
        try:
            # This is a simplified similarity calculation
            # In practice, this could be enhanced with more sophisticated algorithms

            # Get what the current document cites
            current_citations = self.relation_repo.get_relations_by_source(document_id)
            cited_doc_ids = [
                rel.target_document_id
                for rel in current_citations
                if rel.target_document_id
            ]

            if not cited_doc_ids:
                return []

            # Find other documents that cite the same papers
            similar_docs: list[Any] = []

            # This is a placeholder for more sophisticated similarity calculation
            # In a full implementation, you would use techniques like:
            # - Jaccard similarity of citation sets
            # - Cosine similarity based on citation vectors
            # - Collaborative filtering approaches

            return similar_docs

        except Exception as e:
            logger.warning(f"Failed to find similar citing documents: {e}")
            return []

    def detect_citation_clusters(
        self, min_cluster_size: int = 3
    ) -> list[dict[str, Any]]:
        """
        Detect clusters of highly interconnected documents.

        Args:
            min_cluster_size: Minimum number of documents to form a cluster

        Returns:
            List of detected citation clusters
        """
        try:
            logger.debug(
                f"Detecting citation clusters with minimum size {min_cluster_size}"
            )

            # Get all citation relations
            all_relations = self.relation_repo.get_all_relations()

            # Build adjacency information
            adjacency = {}
            for relation in all_relations:
                source_id = relation.source_document_id
                target_id = relation.target_document_id

                if source_id not in adjacency:
                    adjacency[source_id] = set[str]()
                if target_id not in adjacency:
                    adjacency[target_id] = set[str]()

                adjacency[source_id].add(target_id)
                adjacency[target_id].add(
                    source_id
                )  # Treat as undirected for clustering

            # Simple clustering algorithm (connected components)
            visited = set[str]()
            clusters: list[Any] = []

            def dfs_cluster(node_id, current_cluster) -> None:
                if node_id in visited:
                    return
                visited.add(node_id)
                current_cluster.append(node_id)

                for neighbor in adjacency.get(node_id, set[str]()):
                    if neighbor not in visited:
                        dfs_cluster(neighbor, current_cluster)

            for doc_id in adjacency:
                if doc_id not in visited:
                    cluster: list[Any] = []
                    dfs_cluster(doc_id, cluster)

                    if len(cluster) >= min_cluster_size:
                        clusters.append(
                            {
                                "cluster_id": len(clusters) + 1,
                                "document_ids": cluster,
                                "size": len(cluster),
                                "internal_connections": self._count_internal_connections(
                                    cluster, all_relations
                                ),
                            }
                        )

            logger.debug(f"Detected {len(clusters)} citation clusters")
            return clusters

        except Exception as e:
            logger.error(f"Failed to detect citation clusters: {e}")
            return []

    def _count_internal_connections(
        self, cluster_docs: list[int], all_relations: list[Any]
    ) -> int:
        """
        Count internal connections within a cluster.

        Args:
            cluster_docs: List of document IDs in the cluster
            all_relations: All citation relations

        Returns:
            Number of internal connections
        """
        cluster_set = set[str](cluster_docs)
        internal_count = 0

        for relation in all_relations:
            if (
                relation.source_document_id in cluster_set
                and relation.target_document_id in cluster_set
            ):
                internal_count += 1

        return internal_count
