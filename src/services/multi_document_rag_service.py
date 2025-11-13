"""
Multi-Document RAG Service
Service for managing document collections and performing cross-document queries.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from llama_index.core import (
        StorageContext,
        VectorStoreIndex,
        load_index_from_storage,
    )
    from llama_index.core.schema import Document as LlamaDocument
except ImportError:  # pragma: no cover - optional dependency
    StorageContext = None  # type: ignore
    VectorStoreIndex = None  # type: ignore
    load_index_from_storage = None  # type: ignore
    LlamaDocument = None  # type: ignore

from src.database.models import DocumentModel
from src.database.multi_document_models import (
    CrossDocumentQueryModel,
    CrossReference,
    DocumentSource,
    MultiDocumentCollectionModel,
    MultiDocumentIndexModel,
)
from src.interfaces.repository_interfaces import (
    ICrossDocumentQueryRepository,
    IDocumentRepository,
    IMultiDocumentCollectionRepository,
    IMultiDocumentIndexRepository,
)
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)

if StorageContext is None or VectorStoreIndex is None:  # pragma: no cover
    logger.warning(
        "llama_index is not installed - multi-document RAG features are disabled."
    )


@dataclass
class MultiDocumentQueryResponse:
    """Response object for multi-document queries."""

    answer: str
    confidence: float
    sources: list[DocumentSource]
    cross_references: list[CrossReference]
    processing_time_ms: int
    tokens_used: int | None = None


class CollectionIndexManager:
    """Manages vector indexes for document collections."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        Path(storage_path).mkdir(parents=True, exist_ok=True)

    def create_index(self, documents: list[DocumentModel], collection_id: int) -> str:
        """
        Create a vector index for a collection of documents.

        Args:
            documents: List of documents to index
            collection_id: ID of the collection

        Returns:
            Path to the created index
        """
        logger.info(
            f"Creating index for collection {collection_id} with {len(documents)} documents"
        )

        # Convert documents to LlamaIndex documents
        llama_docs = []
        for doc in documents:
            # Load document content (simplified - in reality would parse PDF)
            content = f"Document: {doc.title}\nFile: {doc.file_path}\nID: {doc.id}"
            llama_doc = LlamaDocument(
                text=content,
                metadata={
                    "document_id": doc.id,
                    "title": doc.title,
                    "file_path": doc.file_path,
                    "file_size": doc.file_size,
                },
            )
            llama_docs.append(llama_doc)

        # Create index
        index = VectorStoreIndex.from_documents(llama_docs)

        # Persist index
        index_path = self.get_index_path(collection_id)
        Path(index_path).mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=index_path)

        logger.info(f"Index created and persisted to {index_path}")
        return index_path

    def get_index_path(self, collection_id: int) -> str:
        """Get the file path for a collection's index."""
        return str(Path(self.storage_path) / f"collection_{collection_id}")

    def index_exists(self, collection_id: int) -> bool:
        """Check if an index exists for the collection."""
        index_path = Path(self.get_index_path(collection_id))
        if not index_path.exists():
            return False

        # Check for essential LlamaIndex files
        required_files = [
            "default__vector_store.json",
            "graph_store.json",
            "index_store.json",
        ]
        return all((index_path / file_name).exists() for file_name in required_files)

    def load_index(self, collection_id: int) -> VectorStoreIndex | None:
        """Load an existing index for the collection."""
        if not self.index_exists(collection_id):
            return None

        index_path = self.get_index_path(collection_id)
        storage_context = StorageContext.from_defaults(persist_dir=index_path)
        return load_index_from_storage(storage_context)

    def delete_index(self, collection_id: int) -> bool:
        """Delete the index for a collection."""
        index_path = Path(self.get_index_path(collection_id))
        if index_path.exists():
            shutil.rmtree(index_path)
            logger.info(f"Deleted index for collection {collection_id}")
            return True
        return False


class CrossDocumentAnalyzer:
    """Analyzes queries across multiple documents."""

    def __init__(self, enhanced_rag_service: EnhancedRAGService):
        self.enhanced_rag = enhanced_rag_service

    async def analyze_cross_document_query(
        self,
        query: str,
        documents: list[DocumentModel],
        index_path: str,
        max_results: int = 10,
    ) -> MultiDocumentQueryResponse:
        """
        Analyze a query across multiple documents.

        Args:
            query: The user's query
            documents: List of documents in the collection
            index_path: Path to the collection's vector index
            max_results: Maximum number of results to return

        Returns:
            MultiDocumentQueryResponse with analysis results
        """
        start_time = time.time()

        try:
            # Load the collection index
            storage_context = StorageContext.from_defaults(persist_dir=index_path)
            index = load_index_from_storage(storage_context)

            # Create query engine
            query_engine = index.as_query_engine(
                similarity_top_k=max_results, response_mode="tree_summarize"
            )

            # Perform query
            response = query_engine.query(query)

            # Extract sources from response
            sources = self._extract_sources(response, documents)

            # Calculate confidence score
            confidence = self._calculate_confidence_score(sources)

            # Extract cross-references
            cross_references = self._extract_cross_references(sources, query)

            processing_time = int((time.time() - start_time) * 1000)

            return MultiDocumentQueryResponse(
                answer=str(response.response),
                confidence=confidence,
                sources=sources,
                cross_references=cross_references,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"Error in cross-document analysis: {e}")
            raise

    def _extract_sources(
        self, response, documents: list[DocumentModel]
    ) -> list[DocumentSource]:
        """Extract document sources from query response."""
        sources = []
        doc_lookup = {doc.id: doc for doc in documents}

        if hasattr(response, "source_nodes") and response.source_nodes:
            for node in response.source_nodes:
                metadata = node.node.metadata
                doc_id = metadata.get("document_id")
                if doc_id and doc_id in doc_lookup:
                    source = DocumentSource(
                        document_id=doc_id,
                        relevance_score=getattr(node, "score", 0.5),
                        excerpt=node.node.text[:200] + "..."
                        if len(node.node.text) > 200
                        else node.node.text,
                        page_number=metadata.get("page_number"),
                        chunk_id=metadata.get("chunk_id"),
                    )
                    sources.append(source)

        return sources

    def _calculate_confidence_score(self, sources: list[DocumentSource]) -> float:
        """Calculate overall confidence score based on source relevance."""
        if not sources:
            return 0.0

        # Weight by relevance scores
        total_score = sum(source.relevance_score for source in sources)
        avg_score = total_score / len(sources)

        # Boost confidence if multiple documents contribute
        num_docs = len(set(source.document_id for source in sources))
        diversity_boost = min(num_docs * 0.1, 0.3)

        confidence = min(avg_score + diversity_boost, 1.0)
        return round(confidence, 3)

    def _extract_cross_references(
        self, sources: list[DocumentSource], query: str
    ) -> list[CrossReference]:
        """Extract cross-references between documents based on content similarity."""
        cross_refs = []

        # Simple cross-reference detection based on keyword overlap
        for i, source1 in enumerate(sources):
            for j, source2 in enumerate(sources[i + 1 :], i + 1):
                if source1.document_id != source2.document_id:
                    # Calculate content similarity (simplified)
                    similarity = self._calculate_content_similarity(
                        source1.excerpt, source2.excerpt
                    )

                    if similarity > 0.3:  # Threshold for meaningful relationship
                        relation_type = self._determine_relation_type(
                            source1.excerpt, source2.excerpt, query
                        )

                        cross_ref = CrossReference(
                            source_doc_id=source1.document_id,
                            target_doc_id=source2.document_id,
                            relation_type=relation_type,
                            confidence=similarity,
                            description=f"Related content about: {query[:50]}...",
                        )
                        cross_refs.append(cross_ref)

        return cross_refs

    def _calculate_content_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text excerpts."""
        # Simple word-based similarity (could be enhanced with embeddings)
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _determine_relation_type(self, text1: str, text2: str, query: str) -> str:
        """Determine the type of relationship between two text excerpts."""
        # Simple heuristic-based relation detection
        if any(
            word in text1.lower() and word in text2.lower()
            for word in ["support", "agree", "confirm"]
        ):
            return "supports"
        elif any(
            word in text1.lower() or word in text2.lower()
            for word in ["however", "but", "contrast", "differ"]
        ):
            return "contradicts"
        elif any(
            word in text1.lower() or word in text2.lower()
            for word in ["extend", "build", "further", "additional"]
        ):
            return "extends"
        else:
            return "relates_to"


class MultiDocumentRAGService:
    """Main service for multi-document RAG functionality."""

    def __init__(
        self,
        collection_repository: IMultiDocumentCollectionRepository,
        index_repository: IMultiDocumentIndexRepository,
        query_repository: ICrossDocumentQueryRepository,
        document_repository: IDocumentRepository,
        enhanced_rag_service: EnhancedRAGService,
        index_storage_path: str = "./data/multi_doc_indexes",
    ):
        self.collection_repo = collection_repository
        self.index_repo = index_repository
        self.query_repo = query_repository
        self.document_repo = document_repository
        self.enhanced_rag = enhanced_rag_service

        self.index_manager = CollectionIndexManager(index_storage_path)
        self.analyzer = CrossDocumentAnalyzer(enhanced_rag_service)

    def create_collection(
        self, name: str, document_ids: list[int], description: str | None = None
    ) -> MultiDocumentCollectionModel:
        """
        Create a new document collection.

        Args:
            name: Name of the collection
            document_ids: List of document IDs to include
            description: Optional description

        Returns:
            Created collection model

        Raises:
            ValueError: If documents don't exist
        """
        # Validate that all documents exist
        existing_docs = self.document_repo.get_by_ids(document_ids)
        existing_ids = {doc.id for doc in existing_docs}
        missing_ids = [doc_id for doc_id in document_ids if doc_id not in existing_ids]

        if missing_ids:
            raise ValueError(f"Documents not found: {missing_ids}")

        # Create collection
        collection = MultiDocumentCollectionModel(
            name=name, description=description, document_ids=document_ids
        )

        return self.collection_repo.create(collection)

    def get_collection(self, collection_id: int) -> MultiDocumentCollectionModel:
        """Get a collection by ID."""
        collection = self.collection_repo.get_by_id(collection_id)
        if not collection:
            raise ValueError(f"Collection not found: {collection_id}")
        return collection

    def get_all_collections(self) -> list[MultiDocumentCollectionModel]:
        """Get all collections."""
        return self.collection_repo.get_all()

    def add_document_to_collection(
        self, collection_id: int, document_id: int
    ) -> MultiDocumentCollectionModel:
        """Add a document to an existing collection."""
        collection = self.get_collection(collection_id)

        # Validate document exists
        if not self.document_repo.get_by_id(document_id):
            raise ValueError(f"Document not found: {document_id}")

        collection.add_document(document_id)
        self.collection_repo.update(collection)

        # Invalidate existing index if present
        self._invalidate_collection_index(collection_id)

        return collection

    def remove_document_from_collection(
        self, collection_id: int, document_id: int
    ) -> MultiDocumentCollectionModel:
        """Remove a document from a collection."""
        collection = self.get_collection(collection_id)
        collection.remove_document(document_id)
        self.collection_repo.update(collection)

        # Invalidate existing index if present
        self._invalidate_collection_index(collection_id)

        return collection

    def create_collection_index(self, collection_id: int) -> MultiDocumentIndexModel:
        """Create a vector index for a collection."""
        collection = self.get_collection(collection_id)
        documents = self.document_repo.get_by_ids(collection.document_ids)

        # Create index
        index_path = self.index_manager.create_index(documents, collection_id)

        # Calculate index hash
        index_hash = self._calculate_index_hash(documents)

        # Create index model
        index_model = MultiDocumentIndexModel(
            collection_id=collection_id,
            index_path=index_path,
            index_hash=index_hash,
            chunk_count=len(documents),  # Simplified
        )

        return self.index_repo.create(index_model)

    async def query_collection(
        self,
        collection_id: int,
        query: str,
        user_id: str | None = None,
        max_results: int = 10,
    ) -> MultiDocumentQueryResponse:
        """
        Perform a cross-document query on a collection.

        Args:
            collection_id: ID of the collection to query
            query: The user's query
            user_id: Optional user ID for tracking
            max_results: Maximum number of results

        Returns:
            Query response with cross-document analysis
        """
        # Validate collection exists
        collection = self.get_collection(collection_id)

        # Create query record
        query_model = CrossDocumentQueryModel(
            collection_id=collection_id, query_text=query, user_id=user_id
        )
        query_model = self.query_repo.create(query_model)

        try:
            # Ensure index exists
            await self._ensure_collection_index(collection_id)

            # Get index path
            index_model = self.index_repo.get_by_collection_id(collection_id)
            if not index_model:
                raise ValueError(f"No index found for collection {collection_id}")

            # Get documents
            documents = self.document_repo.get_by_ids(collection.document_ids)

            # Perform analysis
            response = await self.analyzer.analyze_cross_document_query(
                query=query,
                documents=documents,
                index_path=index_model.index_path,
                max_results=max_results,
            )

            # Update query record with results
            query_model.set_response(
                answer=response.answer,
                confidence=response.confidence,
                sources=response.sources,
                cross_references=response.cross_references,
                processing_time_ms=response.processing_time_ms,
                tokens_used=response.tokens_used,
            )
            self.query_repo.update(query_model)

            return response

        except Exception as e:
            # Update query record with error
            query_model.set_error(str(e))
            self.query_repo.update(query_model)
            raise

    def delete_collection(self, collection_id: int) -> bool:
        """Delete a collection and its associated index."""
        # Delete index first
        index_model = self.index_repo.get_by_collection_id(collection_id)
        if index_model:
            self.index_manager.delete_index(collection_id)
            self.index_repo.delete(index_model.id)

        # Delete collection
        return self.collection_repo.delete(collection_id)

    def get_collection_statistics(self, collection_id: int) -> dict[str, Any]:
        """Get statistics for a collection."""
        collection = self.get_collection(collection_id)
        documents = self.document_repo.get_by_ids(collection.document_ids)

        total_size = sum(doc.file_size for doc in documents)
        avg_size = total_size // len(documents) if documents else 0

        return {
            "collection_id": collection_id,
            "name": collection.name,
            "document_count": len(documents),
            "total_file_size": total_size,
            "avg_file_size": avg_size,
            "created_at": collection.created_at.isoformat()
            if collection.created_at
            else None,
        }

    async def _ensure_collection_index(self, collection_id: int) -> None:
        """Ensure that a collection has a valid index."""
        index_model = self.index_repo.get_by_collection_id(collection_id)

        if not index_model or not self.index_manager.index_exists(collection_id):
            logger.info(f"Creating index for collection {collection_id}")
            self.create_collection_index(collection_id)

    def _invalidate_collection_index(self, collection_id: int) -> None:
        """Invalidate (delete) a collection's index when documents change."""
        index_model = self.index_repo.get_by_collection_id(collection_id)
        if index_model:
            self.index_manager.delete_index(collection_id)
            self.index_repo.delete(index_model.id)
            logger.info(f"Invalidated index for collection {collection_id}")

    def _calculate_index_hash(self, documents: list[DocumentModel]) -> str:
        """Calculate a hash for the collection index based on document content."""
        content = ""
        for doc in sorted(documents, key=lambda d: d.id):
            content += f"{doc.id}:{doc.file_hash}:{doc.content_hash or ''}"

        return hashlib.sha256(content.encode()).hexdigest()[:16]
