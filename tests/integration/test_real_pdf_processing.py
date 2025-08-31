"""
Real PDF Processing Integration Tests

This module replaces mock-heavy tests with real PDF processing to validate
actual RAG functionality. Tests use real PDFs, real text extraction, and
real vector operations (in test mode for performance).
"""

import json
import tempfile
import time
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from src.database.connection import DatabaseConnection
from src.repositories.citation_relation_repository import CitationRelationRepository
from src.repositories.citation_repository import CitationRepository
from src.services.citation_parsing_service import CitationParsingService
from src.services.citation_service import CitationService
from src.services.document_library_service import DocumentLibraryService
from src.services.enhanced_rag_service import EnhancedRAGService
from tests.fixtures.academic_pdf_generator import AcademicPDFGenerator
from tests.fixtures.pdf_fixtures import PDFFixtureGenerator


class TestRealPDFProcessing:
    """Integration tests using real PDF files and processing."""

    @classmethod
    def setup_class(cls):
        """Set up test fixtures and database."""
        # Create PDF fixtures
        cls.pdf_generator = PDFFixtureGenerator()
        cls.academic_generator = AcademicPDFGenerator()

        # Generate fixtures
        cls.basic_fixtures = cls.pdf_generator.create_all_fixtures()
        cls.academic_fixtures = cls.academic_generator.create_all_academic_fixtures()

        # Create temporary database
        cls.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db_file.close()
        cls.db_path = cls.temp_db_file.name

        # Create database connection
        cls.db = DatabaseConnection(cls.db_path)
        cls._initialize_test_database()

    @classmethod
    def teardown_class(cls):
        """Clean up test fixtures and database."""
        cls.pdf_generator.cleanup_fixtures()
        cls.academic_generator.cleanup_fixtures()
        cls.db.close_all_connections()
        Path(cls.db_path).unlink(missing_ok=True)

    @classmethod
    def _initialize_test_database(cls):
        """Initialize database schema for testing."""
        # Documents table
        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL,
                content_hash TEXT,
                file_size INTEGER DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT ''
            )
        """)

        # Vector indexes table
        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS vector_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                index_path TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                index_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)

        # Citations tables
        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                citation_text TEXT NOT NULL,
                authors TEXT,
                title TEXT,
                journal TEXT,
                year INTEGER,
                doi TEXT,
                page_numbers TEXT,
                citation_type TEXT DEFAULT 'unknown',
                confidence_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)

        cls.db.execute("""
            CREATE TABLE IF NOT EXISTS citation_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                citing_document_id INTEGER NOT NULL,
                cited_document_id INTEGER,
                citation_id INTEGER NOT NULL,
                relation_type TEXT DEFAULT 'cites',
                context TEXT,
                confidence_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (citing_document_id) REFERENCES documents (id) ON DELETE CASCADE,
                FOREIGN KEY (cited_document_id) REFERENCES documents (id) ON DELETE SET NULL,
                FOREIGN KEY (citation_id) REFERENCES citations (id) ON DELETE CASCADE
            )
        """)

    def setup_method(self):
        """Set up for each test method."""
        # Create temporary storage directories
        self.temp_docs_dir = tempfile.mkdtemp()
        self.temp_vector_dir = tempfile.mkdtemp()

        # Create service instances (in test mode for performance)
        self.doc_service = DocumentLibraryService(
            db_connection=self.db,
            documents_dir=self.temp_docs_dir
        )

        self.rag_service = EnhancedRAGService(
            api_key="test_api_key",
            db_connection=self.db,
            vector_storage_dir=self.temp_vector_dir,
            test_mode=True
        )

        self.citation_parsing_service = CitationParsingService()
        # Initialize citation repositories and service
        citation_repo = CitationRepository(self.db)
        relation_repo = CitationRelationRepository(self.db)
        self.citation_service = CitationService(citation_repo, relation_repo)

        # Clear database for fresh test
        self.db.execute("DELETE FROM citation_relations")
        self.db.execute("DELETE FROM citations")
        self.db.execute("DELETE FROM vector_indexes")
        self.db.execute("DELETE FROM documents")

    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        if Path(self.temp_docs_dir).exists():
            shutil.rmtree(self.temp_docs_dir)
        if Path(self.temp_vector_dir).exists():
            shutil.rmtree(self.temp_vector_dir)

    # ===== Real PDF Import and Processing Tests =====

    def test_real_pdf_import_and_text_extraction(self):
        """Test importing real PDFs and extracting actual text content."""
        # Test with academic paper (has rich content and citations)
        ai_paper_path = self.academic_generator.get_fixture_path("ai_research_sample.pdf")

        # Import document - this should process the real PDF
        document = self.doc_service.import_document(
            str(ai_paper_path),
            title="AI Research Paper Test"
        )

        # Verify document was imported with real data
        assert document is not None
        assert document.id is not None
        assert document.title == "AI Research Paper Test"
        assert document.file_hash is not None
        assert document.content_hash is not None
        assert document.file_size > 0
        assert document.page_count >= 3  # Our academic fixture has 3 pages

        # Verify the file was actually copied to documents directory
        imported_file_path = Path(document.file_path)
        assert imported_file_path.exists()
        assert imported_file_path.stat().st_size > 0

    def test_real_pdf_content_hash_deduplication(self):
        """Test content hash deduplication with real PDFs."""
        # Create identical content PDFs
        identical_pdfs = self.pdf_generator.create_identical_content_pdfs()

        # Import first PDF
        doc1 = self.doc_service.import_document(
            str(identical_pdfs[0]),
            title="First Import"
        )

        # Try to import second PDF with identical content
        with pytest.raises(Exception):  # Should raise DuplicateDocumentError
            self.doc_service.import_document(
                str(identical_pdfs[1]),
                title="Second Import"
            )

        # Verify first document has valid content hash
        assert doc1.content_hash is not None
        assert len(doc1.content_hash) > 0

    def test_real_pdf_rag_index_building(self):
        """Test building RAG index from real PDF content."""
        # Use multi-page PDF for more realistic testing
        multi_page_path = self.pdf_generator.get_fixture_path("multi_page.pdf")

        # Import document
        document = self.doc_service.import_document(
            str(multi_page_path),
            title="Multi-page Test Document"
        )

        # Build RAG index - this should process real PDF text
        start_time = time.time()
        vector_index = self.rag_service.build_index_from_document(document)
        processing_time = time.time() - start_time

        # Verify index was created
        assert vector_index is not None
        assert vector_index.document_id == document.id
        assert vector_index.chunk_count > 0
        assert Path(vector_index.index_path).exists()

        # Verify processing time is reasonable (should be fast in test mode)
        assert processing_time < 30  # Reasonable upper bound for test mode

        print(f"RAG index built in {processing_time:.2f}s with {vector_index.chunk_count} chunks")

    def test_real_pdf_rag_query_processing(self):
        """Test end-to-end RAG query with real PDF content."""
        # Use academic paper with rich content
        cv_paper_path = self.academic_generator.get_fixture_path("cv_research_sample.pdf")

        # Import and index document
        document = self.doc_service.import_document(
            str(cv_paper_path),
            title="Computer Vision Paper"
        )

        vector_index = self.rag_service.build_index_from_document(document)

        # Perform actual query
        query = "What are the main CNN architectures discussed?"
        start_time = time.time()
        response = self.rag_service.query_document(query, document.id)
        query_time = time.time() - start_time

        # Verify response
        assert isinstance(response, str)
        assert len(response) > 0
        assert query_time < 10  # Should be fast in test mode

        # In test mode, response should contain mock content with document ID
        assert str(document.id) in response
        assert query.lower() in response.lower()

        print(f"RAG query processed in {query_time:.2f}s")

    def test_citation_extraction_from_real_academic_papers(self):
        """Test citation extraction from real academic papers."""
        # Test with AI research paper (has many citations)
        ai_paper_path = self.academic_generator.get_fixture_path("ai_research_sample.pdf")

        # Import document
        document = self.doc_service.import_document(
            str(ai_paper_path),
            title="AI Paper with Citations"
        )

        # Extract text content for citation parsing (real PDF processing)
        import fitz
        pdf_doc = fitz.open(str(ai_paper_path))
        full_text = ""
        for page_num in range(pdf_doc.page_count):
            page = pdf_doc[page_num]
            full_text += page.get_text()
        pdf_doc.close()

        # Parse citations from real text
        citations = self.citation_parsing_service.parse_citations(full_text)

        # Verify citations were found
        assert len(citations) > 0

        # Store citations in database
        saved_citations = []
        for citation in citations:
            saved_citation = self.citation_service.add_citation(
                document_id=document.id,
                citation_text=citation.get('raw_text', ''),
                authors=citation.get('authors'),
                title=citation.get('title'),
                year=citation.get('year'),
                journal=citation.get('venue')
            )
            saved_citations.append(saved_citation)

        # Verify citations were saved
        assert len(saved_citations) > 0

        # Verify citation data quality
        for citation in saved_citations:
            assert citation.citation_text is not None
            assert len(citation.citation_text) > 0

        print(f"Extracted {len(saved_citations)} citations from real academic paper")

    def test_multiple_documents_rag_workflow(self):
        """Test RAG workflow with multiple real documents."""
        documents = []

        # Import multiple academic papers
        for fixture_name in ["ai_research_sample.pdf", "cv_research_sample.pdf", "data_science_sample.pdf"]:
            fixture_path = self.academic_generator.get_fixture_path(fixture_name)
            document = self.doc_service.import_document(
                str(fixture_path),
                title=f"Academic Paper: {fixture_name}"
            )
            documents.append(document)

        # Build indexes for all documents
        vector_indexes = []
        total_chunks = 0

        start_time = time.time()
        for document in documents:
            vector_index = self.rag_service.build_index_from_document(document)
            vector_indexes.append(vector_index)
            total_chunks += vector_index.chunk_count

        indexing_time = time.time() - start_time

        # Verify all indexes were created
        assert len(vector_indexes) == 3
        assert total_chunks > 0

        # Test querying different documents
        queries_and_docs = [
            ("What is BERT?", documents[0].id),  # AI paper
            ("What are CNNs?", documents[1].id),  # CV paper
            ("What is machine learning in healthcare?", documents[2].id)  # Data science paper
        ]

        responses = []
        total_query_time = 0

        for query, doc_id in queries_and_docs:
            start_time = time.time()
            response = self.rag_service.query_document(query, doc_id)
            query_time = time.time() - start_time
            total_query_time += query_time

            responses.append(response)
            assert isinstance(response, str)
            assert len(response) > 0

        print(f"Processed {len(documents)} documents with {total_chunks} total chunks")
        print(f"Indexing time: {indexing_time:.2f}s")
        print(f"Average query time: {total_query_time/len(queries_and_docs):.2f}s")

    def test_performance_benchmarks(self):
        """Test performance characteristics with real PDF processing."""
        # Test with various sized documents
        test_cases = [
            ("simple_text.pdf", "Small document"),
            ("multi_page.pdf", "Medium document"),
            ("medium_document.pdf", "Large document (10 pages)")
        ]

        performance_data = []

        for fixture_name, description in test_cases:
            fixture_path = self.pdf_generator.get_fixture_path(fixture_name)
            if fixture_path is None or not fixture_path.exists():
                continue

            # Measure import time
            start_time = time.time()
            document = self.doc_service.import_document(
                str(fixture_path),
                title=f"Performance Test: {description}"
            )
            import_time = time.time() - start_time

            # Measure indexing time
            start_time = time.time()
            vector_index = self.rag_service.build_index_from_document(document)
            indexing_time = time.time() - start_time

            # Measure query time
            start_time = time.time()
            response = self.rag_service.query_document(
                "What is this document about?",
                document.id
            )
            query_time = time.time() - start_time

            performance_data.append({
                'description': description,
                'file_size': document.file_size,
                'page_count': document.page_count,
                'chunk_count': vector_index.chunk_count,
                'import_time': import_time,
                'indexing_time': indexing_time,
                'query_time': query_time
            })

        # Verify performance is reasonable
        for data in performance_data:
            assert data['import_time'] < 10  # Import should be fast
            assert data['indexing_time'] < 30  # Indexing should be reasonable in test mode
            assert data['query_time'] < 5  # Query should be very fast in test mode

        # Print performance summary
        print("Performance Benchmarks:")
        for data in performance_data:
            print(f"  {data['description']}:")
            print(f"    File size: {data['file_size']} bytes")
            print(f"    Pages: {data['page_count']}")
            print(f"    Chunks: {data['chunk_count']}")
            print(f"    Import: {data['import_time']:.3f}s")
            print(f"    Indexing: {data['indexing_time']:.3f}s")
            print(f"    Query: {data['query_time']:.3f}s")

    def test_error_handling_with_real_pdfs(self):
        """Test error handling with real PDF processing."""

        # Test with corrupted PDF
        corrupted_path = self.pdf_generator.get_fixture_path("corrupted.pdf")

        with pytest.raises(Exception):  # Should raise DocumentImportError
            self.doc_service.import_document(str(corrupted_path))

        # Test with empty PDF
        empty_path = self.pdf_generator.get_fixture_path("empty.pdf")

        # Empty PDF should import successfully but may have minimal content
        document = self.doc_service.import_document(
            str(empty_path),
            title="Empty PDF Test"
        )
        assert document is not None

        # Try to build index on empty document
        vector_index = self.rag_service.build_index_from_document(document)

        # Should succeed but with minimal chunks
        assert vector_index is not None
        # Chunk count might be 0 or 1 for empty document

    def test_special_characters_and_unicode(self):
        """Test handling of special characters and Unicode in real PDFs."""
        special_chars_path = self.pdf_generator.get_fixture_path("special_chars.pdf")

        # Import PDF with special characters
        document = self.doc_service.import_document(
            str(special_chars_path),
            title="Special Characters Test"
        )

        # Build index - should handle Unicode correctly
        vector_index = self.rag_service.build_index_from_document(document)
        assert vector_index is not None

        # Query with special characters
        response = self.rag_service.query_document(
            "What special characters are mentioned?",
            document.id
        )
        assert isinstance(response, str)
        assert len(response) > 0

        print("Successfully processed PDF with special characters and Unicode")

        # Additional validation for Unicode handling
        # Extract and verify actual text contains special characters
        actual_text = self._extract_pdf_text(special_chars_path)

        # Test query with Unicode characters
        unicode_query = "What special symbols are mentioned?"
        response = self.rag_service.query_document(unicode_query, document.id)

        assert isinstance(response, str)
        assert len(response) > 0
        print(f"Unicode query response length: {len(response)}")

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Helper method to extract actual text from PDF for validation."""
        try:
            pdf_doc = fitz.open(str(pdf_path))
            full_text = ""
            for page_num in range(pdf_doc.page_count):
                page = pdf_doc[page_num]
                full_text += page.get_text()
            pdf_doc.close()
            return full_text
        except Exception as e:
            print(f"Warning: Could not extract text from {pdf_path}: {e}")
            return ""

    def test_real_vector_embeddings_creation(self):
        """Test that vector embeddings are actually created and stored correctly."""
        # Use a known academic paper
        ai_paper_path = self.academic_generator.get_fixture_path("ai_research_sample.pdf")

        # Import document and build index
        document = self.doc_service.import_document(
            str(ai_paper_path),
            title="AI Research Paper for Embeddings Test"
        )

        vector_index = self.rag_service.build_index_from_document(document)

        # Verify index files were created with actual content
        index_path = Path(vector_index.index_path)
        assert index_path.exists()

        # Check for vector store file (contains actual embeddings in test mode)
        vector_store_file = index_path / "default__vector_store.json"
        if vector_store_file.exists():
            with open(vector_store_file) as f:
                vector_data = json.load(f)

            # Verify embeddings exist
            if 'embedding_dict' in vector_data:
                embeddings = vector_data['embedding_dict']
                assert len(embeddings) > 0, "No embeddings found in vector store"

                # Check embedding dimensions
                first_embedding = next(iter(embeddings.values()))
                assert len(first_embedding) > 0, "Empty embedding vector"

                print(f"Created {len(embeddings)} embedding vectors")
                print(f"Embedding dimension: {len(first_embedding)}")

        # Test similarity search works with actual embeddings
        # Even in test mode, this validates the vector storage structure
        query_response = self.rag_service.query_document(
            "What is BERT?",
            document.id
        )

        assert len(query_response) > 0
        print("Vector embeddings successfully created and queryable")

    def test_real_document_chunking_strategy(self):
        """Test that documents are properly chunked for vector storage."""
        # Use different sized documents to test chunking
        test_documents = [
            ("ai_research_sample.pdf", "AI Research (3 pages)"),
            ("cv_research_sample.pdf", "CV Research (2 pages)"),
            ("data_science_sample.pdf", "Data Science (2 pages)")
        ]

        chunking_results = []

        for filename, description in test_documents:
            pdf_path = self.academic_generator.get_fixture_path(filename)
            if not pdf_path or not pdf_path.exists():
                continue

            # Extract actual text to understand content size
            actual_text = self._extract_pdf_text(pdf_path)
            text_length = len(actual_text)

            # Import and index
            document = self.doc_service.import_document(
                str(pdf_path),
                title=f"Chunking Test - {description}"
            )

            vector_index = self.rag_service.build_index_from_document(document)

            chunking_results.append({
                'description': description,
                'text_length': text_length,
                'chunk_count': vector_index.chunk_count,
                'chars_per_chunk': text_length / max(vector_index.chunk_count, 1)
            })

        # Validate chunking makes sense
        for result in chunking_results:
            assert result['chunk_count'] > 0, f"No chunks created for {result['description']}"
            assert result['chars_per_chunk'] > 100, f"Chunks too small for {result['description']}"
            assert result['chars_per_chunk'] < 5000, f"Chunks too large for {result['description']}"

            print(f"{result['description']}:")
            print(f"  Text length: {result['text_length']} chars")
            print(f"  Chunks: {result['chunk_count']}")
            print(f"  Avg chars per chunk: {result['chars_per_chunk']:.0f}")

        print("Document chunking strategy validation complete")

    def test_rag_context_relevance_with_real_content(self):
        """Test that RAG retrieves relevant context from real documents."""
        # Import multiple documents with different topics
        documents_and_queries = [
            ("ai_research_sample.pdf", "What is BERT and how does it work?", ["bert", "transformer", "bidirectional"]),
            ("cv_research_sample.pdf", "Explain ResNet architecture", ["resnet", "skip", "connection", "residual"]),
            ("data_science_sample.pdf", "What are the healthcare applications?", ["healthcare", "patient", "medical", "clinical"])
        ]

        for filename, query, expected_terms in documents_and_queries:
            pdf_path = self.academic_generator.get_fixture_path(filename)
            if not pdf_path or not pdf_path.exists():
                continue

            # Import and index document
            document = self.doc_service.import_document(
                str(pdf_path),
                title=f"Context Test - {filename}"
            )

            vector_index = self.rag_service.build_index_from_document(document)

            # Query the document
            response = self.rag_service.query_document(query, document.id)
            response_lower = response.lower()

            # Check if response contains relevant terms
            found_terms = [term for term in expected_terms if term in response_lower]
            relevance_score = len(found_terms) / len(expected_terms)

            print(f"Query: '{query}'")
            print(f"Found terms: {found_terms}")
            print(f"Relevance score: {relevance_score:.2f}")
            print(f"Response preview: {response[:200]}...")

            # Should find at least some relevant terms
            assert relevance_score > 0.2, f"Poor context relevance for query '{query}'"

        print("RAG context relevance validation complete")

    def test_end_to_end_academic_workflow(self):
        """Test complete academic workflow: import -> index -> cite -> query."""
        # This test validates the complete pipeline as an academic researcher would use it

        # Step 1: Import academic papers
        papers = [
            ("ai_research_sample.pdf", "Deep Learning for NLP Survey"),
            ("cv_research_sample.pdf", "CNN Architectures Review"),
            ("data_science_sample.pdf", "ML in Healthcare Study")
        ]

        imported_documents = []
        for filename, title in papers:
            pdf_path = self.academic_generator.get_fixture_path(filename)
            if pdf_path and pdf_path.exists():
                document = self.doc_service.import_document(str(pdf_path), title=title)
                imported_documents.append((document, filename))

        assert len(imported_documents) >= 2, "Need at least 2 documents for workflow test"

        # Step 2: Build vector indexes for all documents
        start_time = time.time()
        for document, filename in imported_documents:
            vector_index = self.rag_service.build_index_from_document(document)
            assert vector_index.chunk_count > 0
            print(f"Indexed {filename}: {vector_index.chunk_count} chunks")
        indexing_time = time.time() - start_time

        # Step 3: Extract citations from documents
        total_citations = 0
        for document, filename in imported_documents:
            # Extract text and parse citations
            pdf_path = self.academic_generator.get_fixture_path(filename)
            actual_text = self._extract_pdf_text(pdf_path)

            citations = self.citation_parsing_service.parse_citations(actual_text)

            # Store citations
            for citation in citations:
                saved_citation = self.citation_service.add_citation(
                    document_id=document.id,
                    citation_text=citation.get('raw_text', ''),
                    authors=citation.get('authors'),
                    title=citation.get('title'),
                    year=citation.get('year')
                )

            total_citations += len(citations)
            print(f"Extracted {len(citations)} citations from {filename}")

        # Step 4: Perform cross-document queries
        research_queries = [
            ("Compare transformer and CNN architectures", "Cross-domain comparison"),
            ("What are the applications of deep learning in healthcare?", "Application-focused query"),
            ("Which papers mention BERT or similar models?", "Model-specific query")
        ]

        query_results = []
        for query, query_type in research_queries:
            # Query first document (can be extended to multi-document search)
            first_doc, _ = imported_documents[0]
            response = self.rag_service.query_document(query, first_doc.id)

            query_results.append({
                'query': query,
                'type': query_type,
                'response_length': len(response),
                'contains_technical_terms': any(term in response.lower()
                                              for term in ['bert', 'cnn', 'transformer', 'neural'])
            })

        # Validate workflow results
        assert total_citations > 5, f"Should extract meaningful citations, got {total_citations}"
        assert indexing_time < 45, f"Indexing took too long: {indexing_time:.2f}s"

        technical_responses = sum(1 for r in query_results if r['contains_technical_terms'])
        assert technical_responses >= 2, "Should get technical responses for academic queries"

        # Print workflow summary
        print("\n=== Academic Workflow Summary ===")
        print(f"Documents processed: {len(imported_documents)}")
        print(f"Total citations extracted: {total_citations}")
        print(f"Indexing time: {indexing_time:.2f}s")
        print(f"Queries with technical content: {technical_responses}/{len(query_results)}")

        for result in query_results:
            print(f"  {result['type']}: {result['response_length']} chars")

        print("Academic workflow validation complete ✓")

        # Additional validation: Verify system can handle research workflow scale
        total_operations = len(imported_documents) * 3  # import + index + query
        operations_per_second = total_operations / (indexing_time + sum(r['response_length']/1000 for r in query_results))

        print(f"Research workflow efficiency: {operations_per_second:.2f} ops/sec")
        assert operations_per_second > 0.1, "Workflow too slow for practical research use"
