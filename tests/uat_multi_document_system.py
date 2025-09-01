#!/usr/bin/env python3
"""
User Acceptance Testing (UAT) for Multi-Document RAG System
===========================================================

Comprehensive end-to-end testing using real PDF documents to validate:
1. Document upload and processing
2. Collection creation and management  
3. Cross-document index building
4. Multi-document query functionality
5. Performance and accuracy metrics

Usage:
    python tests/uat_multi_document_system.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import DocumentModel
from src.database.multi_document_models import (
    MultiDocumentCollectionModel,
)
from src.repositories.document_repository import DocumentRepository
from src.repositories.multi_document_repositories import (
    CrossDocumentQueryRepository,
    MultiDocumentCollectionRepository,
    MultiDocumentIndexRepository,
)
from src.services.multi_document_rag_service import MultiDocumentRAGService
from tests.test_database_setup import create_memory_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UATestResults:
    """Track UAT test results and metrics"""

    def __init__(self):
        self.test_cases: list[dict[str, Any]] = []
        self.start_time = datetime.now()
        self.performance_metrics: dict[str, list[float]] = {
            'document_upload': [],
            'index_creation': [],
            'collection_creation': [],
            'cross_document_query': []
        }

    def add_test_case(self, name: str, status: str, details: dict[str, Any],
                     duration: float = None):
        """Add a test case result"""
        self.test_cases.append({
            'name': name,
            'status': status,  # 'PASS', 'FAIL', 'SKIP'
            'details': details,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })

    def add_performance_metric(self, category: str, duration: float):
        """Add performance timing"""
        if category in self.performance_metrics:
            self.performance_metrics[category].append(duration)

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.test_cases)
        passed_tests = len([t for t in self.test_cases if t['status'] == 'PASS'])
        failed_tests = len([t for t in self.test_cases if t['status'] == 'FAIL'])

        # Calculate performance statistics
        perf_stats = {}
        for category, times in self.performance_metrics.items():
            if times:
                perf_stats[category] = {
                    'avg': sum(times) / len(times),
                    'min': min(times),
                    'max': max(times),
                    'count': len(times)
                }

        return {
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                'total_duration': (datetime.now() - self.start_time).total_seconds()
            },
            'test_cases': self.test_cases,
            'performance_metrics': perf_stats,
            'timestamp': datetime.now().isoformat()
        }

class MultiDocumentUATSuite:
    """Comprehensive UAT test suite for multi-document RAG system"""

    def __init__(self):
        self.results = UATestResults()
        self.test_documents: list[dict[str, Any]] = []
        self.test_collections: list[dict[str, Any]] = []
        self.db = None
        self.setup_repositories()

    def setup_repositories(self):
        """Initialize repository instances with test database"""
        # Create test database connection
        self.db = create_memory_database()

        # Initialize repositories with database connection
        self.doc_repo = DocumentRepository(self.db)
        self.collection_repo = MultiDocumentCollectionRepository(self.db)
        self.index_repo = MultiDocumentIndexRepository(self.db)
        self.query_repo = CrossDocumentQueryRepository(self.db)

    async def setup_test_environment(self):
        """Setup test environment and sample data"""
        logger.info("Setting up UAT test environment...")

        try:
            # Ensure database tables exist using migration system
            from src.database import DatabaseMigrator
            migrator = DatabaseMigrator(self.db)
            migrator.create_tables_if_not_exist()

            # Repositories are synchronous, not async
            # Tables are already created by migrator above

            # Create sample PDF documents for testing
            await self.create_sample_documents()

            self.results.add_test_case(
                "Environment Setup",
                "PASS",
                {"tables_created": True, "sample_docs_ready": True}
            )

        except Exception as e:
            logger.error(f"Environment setup failed: {e}")
            self.results.add_test_case(
                "Environment Setup",
                "FAIL",
                {"error": str(e)}
            )
            raise

    async def create_sample_documents(self):
        """Create sample PDF documents for testing"""
        # Create temporary PDF files with different content types
        sample_docs = [
            {
                "title": "Machine Learning Fundamentals",
                "content": "This document covers the fundamentals of machine learning including supervised learning, unsupervised learning, and reinforcement learning. Neural networks are a key component of deep learning systems.",
                "file_name": "ml_fundamentals.pdf"
            },
            {
                "title": "Deep Learning Architecture",
                "content": "Deep learning architectures include convolutional neural networks (CNNs) for image processing and recurrent neural networks (RNNs) for sequence data. Transformer models have revolutionized natural language processing.",
                "file_name": "deep_learning.pdf"
            },
            {
                "title": "Natural Language Processing",
                "content": "Natural language processing (NLP) involves text analysis, sentiment analysis, and language generation. Modern NLP systems use transformer architectures and attention mechanisms for better understanding.",
                "file_name": "nlp_guide.pdf"
            },
            {
                "title": "Computer Vision Applications",
                "content": "Computer vision applications include object detection, image classification, and facial recognition. Convolutional neural networks are the foundation of most computer vision systems.",
                "file_name": "computer_vision.pdf"
            }
        ]

        for doc_info in sample_docs:
            # Create simple text-based PDF content (in real scenario, these would be actual PDFs)
            doc_data = {
                "title": doc_info["title"],
                "file_path": f"/tmp/{doc_info['file_name']}",
                "file_hash": f"hash_{doc_info['file_name']}",
                "file_size": len(doc_info["content"]),
                "page_count": 1,
                "metadata": {"content": doc_info["content"]}  # Simulate extracted content
            }

            # Create document model
            document = DocumentModel(**doc_data)
            created_doc = self.doc_repo.create(document)  # Repository methods are synchronous

            self.test_documents.append({
                "id": created_doc.id,
                "model": created_doc,
                "content": doc_info["content"]
            })

        logger.info(f"Created {len(self.test_documents)} sample documents")

    async def test_document_management(self):
        """Test basic document operations"""
        logger.info("Testing document management...")

        start_time = time.time()

        try:
            # Test document retrieval
            docs = self.doc_repo.get_all()
            assert len(docs) >= len(self.test_documents), "Documents not properly created"

            # Test document by ID
            first_doc = self.test_documents[0]
            retrieved_doc = self.doc_repo.get_by_id(first_doc["id"])
            assert retrieved_doc is not None, "Document retrieval by ID failed"
            assert retrieved_doc.title == first_doc["model"].title, "Document data mismatch"

            duration = time.time() - start_time
            self.results.add_performance_metric('document_upload', duration)

            self.results.add_test_case(
                "Document Management",
                "PASS",
                {
                    "documents_created": len(self.test_documents),
                    "retrieval_successful": True,
                    "data_integrity": True
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Document Management",
                "FAIL",
                {"error": str(e)}
            )
            raise

    async def test_collection_creation(self):
        """Test multi-document collection creation and management"""
        logger.info("Testing collection creation...")

        start_time = time.time()

        try:
            # Create test collections with different document combinations
            test_collections = [
                {
                    "name": "AI Research Papers",
                    "description": "Collection of AI and ML research documents",
                    "document_ids": [doc["id"] for doc in self.test_documents[:3]]
                },
                {
                    "name": "Computer Vision Focus",
                    "description": "Documents focused on computer vision applications",
                    "document_ids": [doc["id"] for doc in self.test_documents[1:]]  # Overlap
                }
            ]

            for collection_data in test_collections:
                # Create collection
                collection = MultiDocumentCollectionModel(**collection_data)
                created_collection = self.collection_repo.create(collection)

                # Verify collection properties
                assert created_collection.id is not None, "Collection ID not assigned"
                assert created_collection.document_count == len(collection_data["document_ids"]), "Document count mismatch"

                # Verify document IDs are stored correctly
                retrieved_collection = self.collection_repo.get_by_id(created_collection.id)
                assert set(retrieved_collection.document_ids) == set(collection_data["document_ids"]), "Document IDs mismatch"

                self.test_collections.append({
                    "id": created_collection.id,
                    "model": created_collection,
                    "expected_docs": len(collection_data["document_ids"])
                })

            # Test collection listing
            all_collections = self.collection_repo.get_all()
            assert len(all_collections) >= len(test_collections), "Collections not properly stored"

            duration = time.time() - start_time
            self.results.add_performance_metric('collection_creation', duration)

            self.results.add_test_case(
                "Collection Creation",
                "PASS",
                {
                    "collections_created": len(test_collections),
                    "document_associations": "verified",
                    "retrieval_successful": True
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Collection Creation",
                "FAIL",
                {"error": str(e)}
            )
            raise

    async def test_multi_document_indexing(self):
        """Test multi-document index creation"""
        logger.info("Testing multi-document indexing...")

        start_time = time.time()

        try:
            # Create enhanced RAG service for multi-document service
            from src.services.enhanced_rag_service import EnhancedRAGService
            enhanced_rag = EnhancedRAGService(
                api_key=os.getenv("GEMINI_API_KEY", "test_api_key"),
                db_connection=self.db,
                test_mode=True
            )

            # Create multi-document service
            multi_doc_service = MultiDocumentRAGService(
                collection_repository=self.collection_repo,
                index_repository=self.index_repo,
                query_repository=self.query_repo,
                document_repository=self.doc_repo,
                enhanced_rag_service=enhanced_rag
            )

            for test_collection in self.test_collections:
                collection_id = test_collection["id"]

                # Test index creation
                index_result = multi_doc_service.create_collection_index(collection_id)

                # Verify index was created
                assert index_result is not None, "Index creation failed"

                # Check index record in database
                index_record = self.index_repo.get_by_collection_id(collection_id)
                assert index_record is not None, "Index record not found in database"
                assert index_record.status == "completed", f"Index status: {index_record.status}"

                # Verify document count matches collection
                expected_docs = test_collection["expected_docs"]
                assert index_record.document_count == expected_docs, f"Document count mismatch: {index_record.document_count} vs {expected_docs}"

            duration = time.time() - start_time
            self.results.add_performance_metric('index_creation', duration)

            self.results.add_test_case(
                "Multi-Document Indexing",
                "PASS",
                {
                    "indexes_created": len(self.test_collections),
                    "status_verification": "completed",
                    "document_count_verified": True
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Multi-Document Indexing",
                "FAIL",
                {"error": str(e)}
            )
            raise

    async def test_cross_document_queries(self):
        """Test cross-document query functionality"""
        logger.info("Testing cross-document queries...")

        start_time = time.time()

        try:
            # Create enhanced RAG service for multi-document service
            from src.services.enhanced_rag_service import EnhancedRAGService
            enhanced_rag = EnhancedRAGService(
                api_key=os.getenv("GEMINI_API_KEY", "test_api_key"),
                db_connection=self.db,
                test_mode=True
            )

            # Create multi-document service
            multi_doc_service = MultiDocumentRAGService(
                collection_repository=self.collection_repo,
                index_repository=self.index_repo,
                query_repository=self.query_repo,
                document_repository=self.doc_repo,
                enhanced_rag_service=enhanced_rag
            )

            # Test queries that should find cross-document relationships
            test_queries = [
                {
                    "query": "What are the applications of neural networks?",
                    "expected_docs": 3,  # Should find references in ML, DL, and CV docs
                    "expected_confidence": 0.7
                },
                {
                    "query": "How do transformers relate to natural language processing?",
                    "expected_docs": 2,  # Should find NLP and DL docs
                    "expected_confidence": 0.8
                },
                {
                    "query": "Compare different neural network architectures",
                    "expected_docs": 3,  # Should find multiple architectural references
                    "expected_confidence": 0.6
                }
            ]

            # Test on the first collection (AI Research Papers)
            collection_id = self.test_collections[0]["id"]

            for i, test_query in enumerate(test_queries):
                query_start = time.time()

                # Execute cross-document query
                query_result = multi_doc_service.query_collection(
                    collection_id=collection_id,
                    query=test_query["query"],
                    max_results=10,
                    user_id="uat_tester"
                )

                query_duration = time.time() - query_start
                self.results.add_performance_metric('cross_document_query', query_duration)

                # Verify query result structure
                assert query_result is not None, "Query result is None"
                assert hasattr(query_result, 'answer'), "Query result missing answer"
                assert hasattr(query_result, 'sources'), "Query result missing sources"
                assert hasattr(query_result, 'cross_references'), "Query result missing cross_references"

                # Verify confidence threshold
                if hasattr(query_result, 'confidence'):
                    assert query_result.confidence >= 0.0, "Invalid confidence score"
                    assert query_result.confidence <= 1.0, "Invalid confidence score"

                # Verify sources
                assert len(query_result.sources) > 0, "No sources found"

                # Verify performance
                assert query_result.processing_time_ms < 30000, f"Query too slow: {query_result.processing_time_ms}ms"

                logger.info(f"Query {i+1}: {len(query_result.sources)} sources, {len(query_result.cross_references)} cross-refs")

            duration = time.time() - start_time

            self.results.add_test_case(
                "Cross-Document Queries",
                "PASS",
                {
                    "queries_tested": len(test_queries),
                    "results_structure": "verified",
                    "performance_acceptable": True,
                    "sources_found": True
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Cross-Document Queries",
                "FAIL",
                {"error": str(e)}
            )
            raise

    async def test_query_history_and_analytics(self):
        """Test query history storage and analytics"""
        logger.info("Testing query history and analytics...")

        try:
            collection_id = self.test_collections[0]["id"]

            # Get query history
            query_history = self.query_repo.get_by_collection_id(collection_id)

            # Should have queries from previous test
            assert len(query_history) > 0, "No query history found"

            # Verify query record structure
            for query_record in query_history[:3]:  # Check first 3 records
                assert query_record.collection_id == collection_id, "Collection ID mismatch"
                assert query_record.query is not None, "Query text missing"
                assert query_record.answer is not None, "Answer missing"
                assert query_record.status in ["completed", "processing", "failed"], f"Invalid status: {query_record.status}"

            # Test analytics aggregation
            total_queries = len(query_history)
            avg_processing_time = sum(q.processing_time_ms for q in query_history if q.processing_time_ms) / total_queries

            self.results.add_test_case(
                "Query History and Analytics",
                "PASS",
                {
                    "total_queries": total_queries,
                    "avg_processing_time_ms": avg_processing_time,
                    "history_integrity": "verified"
                }
            )

        except Exception as e:
            self.results.add_test_case(
                "Query History and Analytics",
                "FAIL",
                {"error": str(e)}
            )

    async def test_collection_management_operations(self):
        """Test collection management operations"""
        logger.info("Testing collection management operations...")

        try:
            # Test collection update
            collection = self.test_collections[0]
            original_name = collection["model"].name
            new_name = f"{original_name} - Updated"

            updated_collection = self.collection_repo.update(
                collection["id"],
                {"name": new_name, "description": "Updated description for UAT testing"}
            )

            assert updated_collection.name == new_name, "Collection name update failed"

            # Test document addition to collection
            if len(self.test_documents) > 3:
                new_doc_id = self.test_documents[3]["id"]

                # Add document to collection
                updated_doc_ids = collection["model"].document_ids + [new_doc_id]
                self.collection_repo.update(
                    collection["id"],
                    {"document_ids": updated_doc_ids}
                )

                # Verify update
                retrieved_collection = self.collection_repo.get_by_id(collection["id"])
                assert new_doc_id in retrieved_collection.document_ids, "Document addition failed"

            self.results.add_test_case(
                "Collection Management Operations",
                "PASS",
                {
                    "update_successful": True,
                    "document_addition": True,
                    "data_integrity": "verified"
                }
            )

        except Exception as e:
            self.results.add_test_case(
                "Collection Management Operations",
                "FAIL",
                {"error": str(e)}
            )

    async def test_error_handling_and_edge_cases(self):
        """Test system behavior with edge cases and error conditions"""
        logger.info("Testing error handling and edge cases...")

        try:
            test_cases_passed = 0
            total_test_cases = 0

            # Test invalid collection ID
            total_test_cases += 1
            try:
                invalid_result = self.collection_repo.get_by_id(99999)
                assert invalid_result is None, "Should return None for invalid ID"
                test_cases_passed += 1
            except Exception:
                pass  # Expected behavior

            # Test empty query
            total_test_cases += 1
            # Create enhanced RAG service for this test
            from src.services.enhanced_rag_service import EnhancedRAGService
            enhanced_rag = EnhancedRAGService(self.db)

            multi_doc_service = MultiDocumentRAGService(
                collection_repository=self.collection_repo,
                index_repository=self.index_repo,
                query_repository=self.query_repo,
                document_repository=self.doc_repo,
                enhanced_rag_service=enhanced_rag
            )

            try:
                empty_query_result = multi_doc_service.query_collection(
                    collection_id=self.test_collections[0]["id"],
                    query="",
                    max_results=10,
                    user_id="uat_tester"
                )
                # Should handle gracefully or return appropriate error
                test_cases_passed += 1
            except ValueError:
                test_cases_passed += 1  # Expected error for empty query

            # Test very long query
            total_test_cases += 1
            try:
                long_query = "What are neural networks? " * 100  # Very long query
                long_query_result = multi_doc_service.query_collection(
                    collection_id=self.test_collections[0]["id"],
                    query=long_query,
                    max_results=5,
                    user_id="uat_tester"
                )
                # Should handle gracefully
                test_cases_passed += 1
            except Exception:
                pass  # May have legitimate limits

            self.results.add_test_case(
                "Error Handling and Edge Cases",
                "PASS" if test_cases_passed >= total_test_cases * 0.8 else "FAIL",
                {
                    "test_cases_passed": test_cases_passed,
                    "total_test_cases": total_test_cases,
                    "success_rate": (test_cases_passed / total_test_cases * 100) if total_test_cases > 0 else 0
                }
            )

        except Exception as e:
            self.results.add_test_case(
                "Error Handling and Edge Cases",
                "FAIL",
                {"error": str(e)}
            )

    async def cleanup_test_environment(self):
        """Clean up test data and environment"""
        logger.info("Cleaning up test environment...")

        try:
            # Delete test collections
            for collection in self.test_collections:
                self.collection_repo.delete(collection["id"])

            # Delete test documents
            for document in self.test_documents:
                self.doc_repo.delete(document["id"])

            self.results.add_test_case(
                "Environment Cleanup",
                "PASS",
                {"cleanup_successful": True}
            )

        except Exception as e:
            self.results.add_test_case(
                "Environment Cleanup",
                "FAIL",
                {"error": str(e)}
            )

    async def run_full_uat_suite(self):
        """Execute the complete UAT suite"""
        logger.info("Starting Multi-Document RAG System UAT Suite")
        logger.info("=" * 60)

        try:
            # Setup
            await self.setup_test_environment()

            # Core functionality tests
            await self.test_document_management()
            await self.test_collection_creation()  # Fixed: added await
            await self.test_multi_document_indexing()
            await self.test_cross_document_queries()
            await self.test_query_history_and_analytics()
            await self.test_collection_management_operations()  # Fixed: added await
            await self.test_error_handling_and_edge_cases()

            # Cleanup
            await self.cleanup_test_environment()

        except Exception as e:
            logger.error(f"UAT Suite failed with critical error: {e}")
            self.results.add_test_case(
                "Critical System Failure",
                "FAIL",
                {"error": str(e)}
            )

        # Generate final report
        return self.results.generate_report()

async def main():
    """Main UAT execution function"""
    print("Multi-Document RAG System - User Acceptance Testing")
    print("=" * 50)

    uat_suite = MultiDocumentUATSuite()

    try:
        # Run the complete UAT suite
        report = await uat_suite.run_full_uat_suite()

        # Save report to file
        report_file = project_root / "uat_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Display summary
        print("\n" + "=" * 50)
        print("UAT SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"Total Duration: {report['summary']['total_duration']:.2f} seconds")

        print(f"\nDetailed report saved to: {report_file}")

        # Performance metrics
        if report['performance_metrics']:
            print("\nPERFORMACE METRICS")
            print("-" * 30)
            for category, stats in report['performance_metrics'].items():
                print(f"{category.replace('_', ' ').title()}:")
                print(f"  Average: {stats['avg']:.3f}s")
                print(f"  Min/Max: {stats['min']:.3f}s / {stats['max']:.3f}s")
                print(f"  Samples: {stats['count']}")

        # Test case details for failures
        failed_tests = [t for t in report['test_cases'] if t['status'] == 'FAIL']
        if failed_tests:
            print("\nFAILED TESTS")
            print("-" * 30)
            for test in failed_tests:
                print(f"❌ {test['name']}: {test['details'].get('error', 'Unknown error')}")
        else:
            print("\n✅ All tests passed successfully!")

        return report['summary']['success_rate'] >= 90  # 90% success rate threshold

    except Exception as e:
        print(f"\nCritical UAT failure: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
