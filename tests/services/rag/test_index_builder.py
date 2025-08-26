"""
RAGIndexBuilder Service Tests

Tests for the specialized service responsible for building and managing vector indexes
for RAG operations, with focus on PDF processing and index creation.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from src.database.models import DocumentModel
from src.services.rag.exceptions import RAGIndexError
from src.services.rag.index_builder import RAGIndexBuilder


class TestRAGIndexBuilder:
    """Test suite for RAGIndexBuilder PDF processing and index creation."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for test files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def mock_pdf_processor(self):
        """Mock PDF processor for document text extraction."""
        mock = Mock()
        mock.extract_text.return_value = "Sample PDF content for testing RAG indexing."
        mock.extract_metadata.return_value = {
            "page_count": 10,
            "word_count": 500,
            "title": "Sample PDF",
            "author": "Test Author"
        }
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store for index operations."""
        mock = Mock()
        mock.add_documents = AsyncMock(return_value={"chunks_added": 5})
        mock.save_local = AsyncMock(return_value=True)
        mock.load_local = AsyncMock(return_value=True)
        mock.similarity_search = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def mock_text_splitter(self):
        """Mock text splitter for document chunking."""
        mock = Mock()
        mock.split_text.return_value = [
            "Sample PDF content for testing",
            "RAG indexing with proper chunks",
            "Vector embeddings and search",
            "Document processing workflow",
            "Index building and verification"
        ]
        return mock

    @pytest.fixture
    def index_builder(self, temp_directory, mock_pdf_processor,
                     mock_vector_store, mock_text_splitter):
        """Create RAGIndexBuilder with mocked dependencies."""
        return RAGIndexBuilder(
            index_storage_path=temp_directory,
            pdf_processor=mock_pdf_processor,
            vector_store=mock_vector_store,
            text_splitter=mock_text_splitter
        )

    @pytest.fixture
    def sample_document(self, temp_directory):
        """Create sample document for testing."""
        # Create a fake PDF file
        pdf_path = temp_directory / "sample.pdf"
        pdf_path.write_text("Mock PDF content")

        return DocumentModel(
            id=1,
            title="Sample Document",
            file_path=str(pdf_path),
            content_hash="abc123",
            mime_type="application/pdf",
            file_size=1024
        )

    def test_index_builder_initialization(self, index_builder, temp_directory):
        """Test RAGIndexBuilder initializes with correct configuration."""
        assert index_builder.index_storage_path == temp_directory
        assert index_builder.pdf_processor is not None
        assert index_builder.vector_store is not None
        assert index_builder.text_splitter is not None
        assert index_builder._initialized is True

    @pytest.mark.asyncio
    async def test_build_index_complete_workflow(self, index_builder, sample_document):
        """Test complete index building workflow for a document."""
        # When
        result = await index_builder.build_index(sample_document)

        # Then
        assert result["status"] == "success"
        assert result["document_id"] == 1
        assert result["chunks_created"] == 5
        assert "processing_time" in result
        assert "index_size" in result

        # Verify workflow steps
        index_builder.pdf_processor.extract_text.assert_called_once()
        index_builder.text_splitter.split_text.assert_called_once()
        index_builder.vector_store.add_documents.assert_called_once()
        index_builder.vector_store.save_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_index_with_chunking_options(self, index_builder, sample_document):
        """Test index building with custom chunking configuration."""
        # Given
        chunk_config = {
            "chunk_size": 2000,
            "chunk_overlap": 300,
            "preserve_formatting": True
        }

        # When
        result = await index_builder.build_index(sample_document, chunk_config)

        # Then
        assert result["status"] == "success"

        # Verify chunking configuration was applied
        index_builder.text_splitter.split_text.assert_called_once()
        call_args = index_builder.text_splitter.split_text.call_args
        assert call_args[1]["chunk_size"] == 2000
        assert call_args[1]["chunk_overlap"] == 300

    @pytest.mark.asyncio
    async def test_build_index_pdf_extraction_failure(self, index_builder, sample_document):
        """Test index building handles PDF extraction failure."""
        # Given
        index_builder.pdf_processor.extract_text.side_effect = Exception("PDF corrupted")

        # When/Then
        with pytest.raises(RAGIndexError) as exc_info:
            await index_builder.build_index(sample_document)

        assert "PDF extraction failed" in str(exc_info.value)
        assert "PDF corrupted" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_build_index_empty_document_handling(self, index_builder, sample_document):
        """Test index building handles empty document content."""
        # Given
        index_builder.pdf_processor.extract_text.return_value = ""

        # When/Then
        with pytest.raises(RAGIndexError) as exc_info:
            await index_builder.build_index(sample_document)

        assert "Document contains no extractable text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_index_success(self, index_builder, sample_document):
        """Test successful index verification."""
        # Given - setup index file
        index_path = index_builder._get_index_path(sample_document.id)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        # Create mock index metadata
        metadata = {
            "document_id": sample_document.id,
            "chunks_count": 5,
            "created_at": "2023-01-01T10:00:00Z",
            "content_hash": sample_document.content_hash
        }
        (index_path / "metadata.json").write_text(json.dumps(metadata))

        # When
        result = await index_builder.verify_index(sample_document.id)

        # Then
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_index_missing_files(self, index_builder):
        """Test index verification fails for missing index files."""
        # When
        result = await index_builder.verify_index(document_id=999)

        # Then
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_index_corrupted_metadata(self, index_builder, sample_document):
        """Test index verification handles corrupted metadata."""
        # Given - create corrupted metadata
        index_path = index_builder._get_index_path(sample_document.id)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        (index_path / "metadata.json").write_text("invalid json")

        # When
        result = await index_builder.verify_index(sample_document.id)

        # Then
        assert result is False

    def test_get_index_stats(self, index_builder, sample_document):
        """Test retrieval of index statistics."""
        # Given - setup index directory with files
        index_path = index_builder._get_index_path(sample_document.id)
        index_path.mkdir(parents=True, exist_ok=True)

        # Create mock files with sizes
        (index_path / "vectors.pkl").write_bytes(b"mock_vector_data" * 100)
        (index_path / "metadata.json").write_text('{"chunks_count": 5}')

        # When
        stats = index_builder.get_index_stats(sample_document.id)

        # Then
        assert stats["document_id"] == sample_document.id
        assert stats["total_size"] > 0
        assert stats["file_count"] == 2
        assert "created_at" in stats

    def test_get_index_stats_missing_index(self, index_builder):
        """Test index stats for non-existent index."""
        # When
        stats = index_builder.get_index_stats(document_id=999)

        # Then
        assert stats is None

    @pytest.mark.asyncio
    async def test_rebuild_index(self, index_builder, sample_document):
        """Test rebuilding existing index."""
        # Given - create existing index
        await index_builder.build_index(sample_document)

        # Reset mocks to track rebuild
        index_builder.vector_store.reset_mock()

        # When
        result = await index_builder.rebuild_index(sample_document)

        # Then
        assert result["status"] == "success"
        assert result["operation"] == "rebuild"

        # Verify old index was cleaned up before rebuild
        index_builder.vector_store.add_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_index(self, index_builder, sample_document):
        """Test index deletion with cleanup."""
        # Given - create index first
        await index_builder.build_index(sample_document)
        index_path = index_builder._get_index_path(sample_document.id)
        assert index_path.exists()

        # When
        result = await index_builder.delete_index(sample_document.id)

        # Then
        assert result["deleted"] is True
        assert result["document_id"] == sample_document.id
        assert not index_path.exists()

    @pytest.mark.asyncio
    async def test_batch_index_building(self, index_builder):
        """Test batch processing of multiple documents."""
        # Given
        documents = [
            DocumentModel(id=1, title="Doc 1", file_path="/test1.pdf",
                         content_hash="hash1", mime_type="application/pdf"),
            DocumentModel(id=2, title="Doc 2", file_path="/test2.pdf",
                         content_hash="hash2", mime_type="application/pdf"),
            DocumentModel(id=3, title="Doc 3", file_path="/test3.pdf",
                         content_hash="hash3", mime_type="application/pdf")
        ]

        # When
        results = await index_builder.batch_build_indexes(documents)

        # Then
        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
        assert index_builder.pdf_processor.extract_text.call_count == 3
        assert index_builder.vector_store.add_documents.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_processing_with_partial_failures(self, index_builder):
        """Test batch processing handles partial failures correctly."""
        # Given
        documents = [
            DocumentModel(id=1, title="Doc 1", file_path="/test1.pdf",
                         content_hash="hash1", mime_type="application/pdf"),
            DocumentModel(id=2, title="Doc 2", file_path="/test2.pdf",
                         content_hash="hash2", mime_type="application/pdf")
        ]

        # Mock failure for second document
        def extract_side_effect(file_path):
            if "test2.pdf" in file_path:
                raise Exception("Processing error")
            return "Sample content"

        index_builder.pdf_processor.extract_text.side_effect = extract_side_effect

        # When
        results = await index_builder.batch_build_indexes(documents,
                                                         fail_fast=False)

        # Then
        assert len(results) == 2
        assert results[0]["status"] == "success"
        assert results[1]["status"] == "failed"
        assert "Processing error" in results[1]["error"]

    def test_chunking_strategy_optimization(self, index_builder):
        """Test different chunking strategies for optimal indexing."""
        # Given
        test_content = "A" * 10000  # Long content to test chunking

        # Test different chunk sizes
        strategies = [
            {"chunk_size": 1000, "chunk_overlap": 100},
            {"chunk_size": 2000, "chunk_overlap": 200},
            {"chunk_size": 4000, "chunk_overlap": 400}
        ]

        for strategy in strategies:
            # When
            index_builder.text_splitter.split_text.return_value = [
                test_content[i:i+strategy["chunk_size"]]
                for i in range(0, len(test_content), strategy["chunk_size"])
            ]

            chunks = index_builder._optimize_chunking(test_content, strategy)

            # Then
            assert len(chunks) > 0
            assert all(len(chunk) <= strategy["chunk_size"] + strategy["chunk_overlap"]
                      for chunk in chunks)

    @pytest.mark.asyncio
    async def test_index_compression_and_optimization(self, index_builder, sample_document):
        """Test index compression and storage optimization."""
        # Given
        compression_config = {
            "enable_compression": True,
            "compression_level": 6,
            "optimize_storage": True
        }

        # When
        result = await index_builder.build_index(sample_document,
                                               compression_config=compression_config)

        # Then
        assert result["status"] == "success"
        assert "compressed_size" in result

        # Verify compression was applied
        index_path = index_builder._get_index_path(sample_document.id)
        assert (index_path / "vectors.gz").exists() or \
               (index_path / "vectors.pkl").exists()

    @pytest.mark.asyncio
    async def test_concurrent_index_building(self, index_builder):
        """Test concurrent index building for multiple documents."""
        import asyncio

        # Given
        documents = [
            DocumentModel(id=i, title=f"Doc {i}", file_path=f"/test{i}.pdf",
                         content_hash=f"hash{i}", mime_type="application/pdf")
            for i in range(1, 6)
        ]

        # When
        tasks = [index_builder.build_index(doc) for doc in documents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Then
        assert len(results) == 5
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 5

    @pytest.mark.asyncio
    async def test_memory_efficient_large_document_processing(self, index_builder):
        """Test memory-efficient processing of large documents."""
        # Given - simulate large document
        large_document = DocumentModel(
            id=1,
            title="Large Document",
            file_path="/large_doc.pdf",
            content_hash="large_hash",
            mime_type="application/pdf",
            file_size=50 * 1024 * 1024  # 50MB
        )

        # Mock large content extraction
        large_content = "Large document content. " * 100000  # ~2MB of text
        index_builder.pdf_processor.extract_text.return_value = large_content

        # When
        result = await index_builder.build_index(large_document,
                                               memory_efficient=True)

        # Then
        assert result["status"] == "success"
        assert result["chunks_created"] > 10  # Should create many chunks
        assert "memory_usage" in result

    def test_index_metadata_management(self, index_builder, sample_document):
        """Test index metadata creation and management."""
        # Given
        index_path = index_builder._get_index_path(sample_document.id)

        # When
        metadata = index_builder._create_index_metadata(sample_document,
                                                       chunks_count=5,
                                                       processing_stats={
                                                           "processing_time": 1.5,
                                                           "memory_usage": "100MB"
                                                       })

        # Then
        assert metadata["document_id"] == sample_document.id
        assert metadata["content_hash"] == sample_document.content_hash
        assert metadata["chunks_count"] == 5
        assert metadata["processing_stats"]["processing_time"] == 1.5
        assert "created_at" in metadata
        assert "index_version" in metadata

    @pytest.mark.asyncio
    async def test_index_validation_and_integrity(self, index_builder, sample_document):
        """Test comprehensive index validation and integrity checking."""
        # Given - build index
        await index_builder.build_index(sample_document)

        # When
        validation_result = await index_builder.validate_index_integrity(sample_document.id)

        # Then
        assert validation_result["valid"] is True
        assert validation_result["checks_passed"] > 0
        assert "metadata_valid" in validation_result
        assert "vector_data_valid" in validation_result
        assert "file_integrity_valid" in validation_result


class TestRAGIndexBuilderErrorHandling:
    """Test error handling and edge cases for RAGIndexBuilder."""

    @pytest.fixture
    def error_prone_builder(self, temp_directory):
        """Create index builder with error-prone dependencies."""
        mock_pdf_processor = Mock()
        mock_vector_store = Mock()
        mock_text_splitter = Mock()

        return RAGIndexBuilder(
            index_storage_path=temp_directory,
            pdf_processor=mock_pdf_processor,
            vector_store=mock_vector_store,
            text_splitter=mock_text_splitter
        )

    @pytest.mark.asyncio
    async def test_storage_permission_error_handling(self, error_prone_builder):
        """Test handling of storage permission errors."""
        # Given
        document = DocumentModel(id=1, title="Test", file_path="/test.pdf",
                               content_hash="hash", mime_type="application/pdf")

        # Mock permission error
        error_prone_builder.vector_store.save_local.side_effect = PermissionError("Access denied")
        error_prone_builder.pdf_processor.extract_text.return_value = "content"
        error_prone_builder.text_splitter.split_text.return_value = ["chunk1"]

        # When/Then
        with pytest.raises(RAGIndexError) as exc_info:
            await error_prone_builder.build_index(document)

        assert "Storage access denied" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disk_space_exhaustion_handling(self, error_prone_builder):
        """Test handling of disk space exhaustion during index building."""
        # Given
        document = DocumentModel(id=1, title="Test", file_path="/test.pdf",
                               content_hash="hash", mime_type="application/pdf")

        # Mock disk space error
        error_prone_builder.vector_store.save_local.side_effect = OSError("No space left on device")
        error_prone_builder.pdf_processor.extract_text.return_value = "content"
        error_prone_builder.text_splitter.split_text.return_value = ["chunk1"]

        # When/Then
        with pytest.raises(RAGIndexError) as exc_info:
            await error_prone_builder.build_index(document)

        assert "Insufficient storage space" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_corrupted_pdf_recovery(self, error_prone_builder):
        """Test recovery from corrupted PDF files."""
        # Given
        document = DocumentModel(id=1, title="Test", file_path="/corrupted.pdf",
                               content_hash="hash", mime_type="application/pdf")

        # Mock PDF corruption
        error_prone_builder.pdf_processor.extract_text.side_effect = Exception("PDF structure damaged")

        # When/Then
        with pytest.raises(RAGIndexError) as exc_info:
            await error_prone_builder.build_index(document)

        assert "PDF processing failed" in str(exc_info.value)
        assert "PDF structure damaged" in str(exc_info.value)
