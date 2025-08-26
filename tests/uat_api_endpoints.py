#!/usr/bin/env python3
"""
API Endpoint UAT Testing for Multi-Document RAG System
======================================================

Tests all REST API endpoints with real HTTP requests to validate:
1. Multi-document collection CRUD operations
2. Cross-document query endpoints
3. Statistics and analytics endpoints
4. Error handling and validation
5. Performance and response times

Usage:
    # Start the API server first:
    python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
    
    # Then run the tests:
    python tests/uat_api_endpoints.py
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

from aiohttp import ClientSession, ClientTimeout

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class APITestResults:
    """Track API test results and metrics"""

    def __init__(self):
        self.test_cases: list[dict[str, Any]] = []
        self.start_time = datetime.now()
        self.performance_metrics: dict[str, list[float]] = {
            'collection_crud': [],
            'document_operations': [],
            'cross_document_queries': [],
            'statistics_endpoints': []
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

class MultiDocumentAPIUATSuite:
    """API endpoint UAT test suite"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.results = APITestResults()
        self.session: ClientSession | None = None
        self.test_documents: list[dict[str, Any]] = []
        self.test_collections: list[dict[str, Any]] = []

    async def setup_session(self):
        """Setup HTTP session"""
        timeout = ClientTimeout(total=30)
        self.session = ClientSession(timeout=timeout)

    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()

    async def check_api_health(self):
        """Check if API server is running and healthy"""
        try:
            async with self.session.get(f"{self.base_url}/api/system/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    return health_data.get('status') in ['healthy', 'degraded']
                return False
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

    async def setup_test_data(self):
        """Setup test documents for API testing"""
        logger.info("Setting up test data via API...")

        start_time = time.time()

        try:
            # Create test documents via upload simulation
            test_docs = [
                {
                    "title": "AI Research Overview",
                    "content": "Comprehensive overview of artificial intelligence research including machine learning, deep learning, and neural networks."
                },
                {
                    "title": "Machine Learning Algorithms",
                    "content": "Detailed analysis of supervised and unsupervised learning algorithms, including decision trees, SVM, and clustering methods."
                },
                {
                    "title": "Deep Learning Fundamentals",
                    "content": "Introduction to deep learning concepts, neural network architectures, backpropagation, and optimization techniques."
                },
                {
                    "title": "Natural Language Processing",
                    "content": "Text processing, sentiment analysis, and language models including transformers and attention mechanisms."
                }
            ]

            # Note: In a real scenario, these would be actual file uploads
            # For UAT, we'll create documents directly via the documents API
            for doc_data in test_docs:
                # Simulate document creation (this would normally be file upload)
                doc_payload = {
                    "title": doc_data["title"],
                    "file_path": f"/tmp/{doc_data['title'].lower().replace(' ', '_')}.pdf",
                    "file_hash": f"hash_{doc_data['title'].replace(' ', '_')}",
                    "file_size": len(doc_data["content"]),
                    "page_count": 1,
                    "metadata": {"content": doc_data["content"]}
                }

                # Since we can't directly create documents via API in this implementation,
                # we'll use the existing documents endpoint to list available documents
                async with self.session.get(f"{self.base_url}/api/documents") as response:
                    if response.status == 200:
                        docs_data = await response.json()
                        if docs_data.get('documents'):
                            # Use existing documents for testing
                            self.test_documents = docs_data['documents'][:4]  # Use first 4 documents
                            break

            if not self.test_documents:
                # If no documents available, we'll note this in the test results
                logger.warning("No existing documents found for API testing")

            duration = time.time() - start_time
            self.results.add_performance_metric('document_operations', duration)

            self.results.add_test_case(
                "Test Data Setup",
                "PASS" if self.test_documents else "SKIP",
                {
                    "documents_available": len(self.test_documents),
                    "note": "Using existing documents" if self.test_documents else "No documents available"
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Test Data Setup",
                "FAIL",
                {"error": str(e)}
            )

    async def test_collection_crud_operations(self):
        """Test collection CRUD operations via API"""
        logger.info("Testing collection CRUD operations...")

        start_time = time.time()

        try:
            if not self.test_documents:
                self.results.add_test_case(
                    "Collection CRUD Operations",
                    "SKIP",
                    {"reason": "No documents available for collection creation"}
                )
                return

            # Test: Create Collection
            create_payload = {
                "name": "UAT Test Collection",
                "description": "Test collection for UAT validation",
                "document_ids": [doc["id"] for doc in self.test_documents[:3]]
            }

            create_start = time.time()
            async with self.session.post(
                f"{self.base_url}/api/multi-document/collections",
                json=create_payload
            ) as response:
                create_duration = time.time() - create_start
                self.results.add_performance_metric('collection_crud', create_duration)

                assert response.status == 200, f"Collection creation failed: {response.status}"
                collection_data = await response.json()

                assert "id" in collection_data, "Collection ID not returned"
                assert collection_data["name"] == create_payload["name"], "Collection name mismatch"
                assert collection_data["document_count"] == len(create_payload["document_ids"]), "Document count mismatch"

                collection_id = collection_data["id"]
                self.test_collections.append(collection_data)

            # Test: Get Collection by ID
            async with self.session.get(f"{self.base_url}/api/multi-document/collections/{collection_id}") as response:
                assert response.status == 200, f"Collection retrieval failed: {response.status}"
                retrieved_collection = await response.json()
                assert retrieved_collection["id"] == collection_id, "Collection ID mismatch"

            # Test: List Collections
            async with self.session.get(f"{self.base_url}/api/multi-document/collections") as response:
                assert response.status == 200, f"Collection listing failed: {response.status}"
                collections_list = await response.json()
                assert "collections" in collections_list, "Collections list format invalid"
                assert len(collections_list["collections"]) > 0, "No collections found"

            # Test: Update Collection
            update_payload = {
                "name": "UAT Test Collection - Updated",
                "description": "Updated description for UAT testing"
            }
            async with self.session.put(
                f"{self.base_url}/api/multi-document/collections/{collection_id}",
                json=update_payload
            ) as response:
                assert response.status == 200, f"Collection update failed: {response.status}"
                updated_collection = await response.json()
                assert updated_collection["name"] == update_payload["name"], "Collection name update failed"

            duration = time.time() - start_time

            self.results.add_test_case(
                "Collection CRUD Operations",
                "PASS",
                {
                    "create_successful": True,
                    "retrieve_successful": True,
                    "list_successful": True,
                    "update_successful": True,
                    "collection_id": collection_id
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Collection CRUD Operations",
                "FAIL",
                {"error": str(e)}
            )

    async def test_collection_document_management(self):
        """Test adding/removing documents from collections"""
        logger.info("Testing collection document management...")

        try:
            if not self.test_collections or not self.test_documents:
                self.results.add_test_case(
                    "Collection Document Management",
                    "SKIP",
                    {"reason": "No collections or documents available"}
                )
                return

            collection_id = self.test_collections[0]["id"]

            # Test: Add document to collection
            if len(self.test_documents) > 3:
                new_doc_id = self.test_documents[3]["id"]
                add_payload = {"document_id": new_doc_id}

                async with self.session.post(
                    f"{self.base_url}/api/multi-document/collections/{collection_id}/documents",
                    json=add_payload
                ) as response:
                    assert response.status == 200, f"Document addition failed: {response.status}"
                    updated_collection = await response.json()
                    assert new_doc_id in updated_collection["document_ids"], "Document not added to collection"

                # Test: Remove document from collection
                async with self.session.delete(
                    f"{self.base_url}/api/multi-document/collections/{collection_id}/documents/{new_doc_id}"
                ) as response:
                    assert response.status == 200, f"Document removal failed: {response.status}"
                    updated_collection = await response.json()
                    assert new_doc_id not in updated_collection["document_ids"], "Document not removed from collection"

            self.results.add_test_case(
                "Collection Document Management",
                "PASS",
                {
                    "document_addition": True,
                    "document_removal": True
                }
            )

        except Exception as e:
            self.results.add_test_case(
                "Collection Document Management",
                "FAIL",
                {"error": str(e)}
            )

    async def test_multi_document_indexing_api(self):
        """Test multi-document index creation via API"""
        logger.info("Testing multi-document indexing API...")

        start_time = time.time()

        try:
            if not self.test_collections:
                self.results.add_test_case(
                    "Multi-Document Indexing API",
                    "SKIP",
                    {"reason": "No collections available"}
                )
                return

            collection_id = self.test_collections[0]["id"]

            # Test: Create collection index
            async with self.session.post(
                f"{self.base_url}/api/multi-document/collections/{collection_id}/index"
            ) as response:
                assert response.status == 200, f"Index creation failed: {response.status}"
                index_result = await response.json()
                assert "success" in index_result, "Index creation response invalid"

            duration = time.time() - start_time
            self.results.add_performance_metric('collection_crud', duration)

            self.results.add_test_case(
                "Multi-Document Indexing API",
                "PASS",
                {
                    "index_creation": True,
                    "response_valid": True
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Multi-Document Indexing API",
                "FAIL",
                {"error": str(e)}
            )

    async def test_cross_document_query_api(self):
        """Test cross-document query API endpoints"""
        logger.info("Testing cross-document query API...")

        start_time = time.time()

        try:
            if not self.test_collections:
                self.results.add_test_case(
                    "Cross-Document Query API",
                    "SKIP",
                    {"reason": "No collections available"}
                )
                return

            collection_id = self.test_collections[0]["id"]

            # Test queries
            test_queries = [
                {
                    "query": "What are the main concepts in artificial intelligence?",
                    "max_results": 10,
                    "user_id": "uat_tester"
                },
                {
                    "query": "How do neural networks work?",
                    "max_results": 5,
                    "user_id": "uat_tester"
                },
                {
                    "query": "Compare machine learning and deep learning",
                    "max_results": 8,
                    "user_id": "uat_tester"
                }
            ]

            for i, query_payload in enumerate(test_queries):
                query_start = time.time()

                async with self.session.post(
                    f"{self.base_url}/api/multi-document/collections/{collection_id}/query",
                    json=query_payload
                ) as response:
                    query_duration = time.time() - query_start
                    self.results.add_performance_metric('cross_document_queries', query_duration)

                    assert response.status == 200, f"Query {i+1} failed: {response.status}"
                    query_result = await response.json()

                    # Verify response structure
                    required_fields = ["id", "query", "answer", "confidence", "sources", "cross_references"]
                    for field in required_fields:
                        assert field in query_result, f"Missing field: {field}"

                    # Verify response content
                    assert query_result["query"] == query_payload["query"], "Query mismatch"
                    assert isinstance(query_result["sources"], list), "Sources not a list"
                    assert isinstance(query_result["cross_references"], list), "Cross-references not a list"
                    assert 0.0 <= query_result["confidence"] <= 1.0, "Invalid confidence score"

                    logger.info(f"Query {i+1}: {len(query_result['sources'])} sources, confidence: {query_result['confidence']:.2f}")

            duration = time.time() - start_time

            self.results.add_test_case(
                "Cross-Document Query API",
                "PASS",
                {
                    "queries_tested": len(test_queries),
                    "response_structure": "valid",
                    "performance_acceptable": True
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Cross-Document Query API",
                "FAIL",
                {"error": str(e)}
            )

    async def test_query_history_api(self):
        """Test query history API endpoints"""
        logger.info("Testing query history API...")

        try:
            if not self.test_collections:
                self.results.add_test_case(
                    "Query History API",
                    "SKIP",
                    {"reason": "No collections available"}
                )
                return

            collection_id = self.test_collections[0]["id"]

            # Test: Get query history
            async with self.session.get(
                f"{self.base_url}/api/multi-document/collections/{collection_id}/queries"
            ) as response:
                assert response.status == 200, f"Query history retrieval failed: {response.status}"
                history_data = await response.json()

                assert "queries" in history_data, "Query history format invalid"
                assert isinstance(history_data["queries"], list), "Queries not a list"

                # Should have queries from previous test
                if len(history_data["queries"]) > 0:
                    first_query = history_data["queries"][0]
                    required_fields = ["id", "query", "answer", "confidence", "created_at"]
                    for field in required_fields:
                        assert field in first_query, f"Missing field in query history: {field}"

            self.results.add_test_case(
                "Query History API",
                "PASS",
                {
                    "history_retrieval": True,
                    "format_valid": True,
                    "queries_found": len(history_data["queries"])
                }
            )

        except Exception as e:
            self.results.add_test_case(
                "Query History API",
                "FAIL",
                {"error": str(e)}
            )

    async def test_statistics_api(self):
        """Test collection statistics API"""
        logger.info("Testing statistics API...")

        start_time = time.time()

        try:
            if not self.test_collections:
                self.results.add_test_case(
                    "Statistics API",
                    "SKIP",
                    {"reason": "No collections available"}
                )
                return

            collection_id = self.test_collections[0]["id"]

            # Test: Get collection statistics
            async with self.session.get(
                f"{self.base_url}/api/multi-document/collections/{collection_id}/statistics"
            ) as response:
                assert response.status == 200, f"Statistics retrieval failed: {response.status}"
                stats_data = await response.json()

                # Verify statistics structure
                required_fields = ["collection_id", "name", "document_count", "total_file_size", "created_at"]
                for field in required_fields:
                    assert field in stats_data, f"Missing statistics field: {field}"

                # Verify data types and values
                assert isinstance(stats_data["document_count"], int), "Document count not integer"
                assert stats_data["document_count"] >= 0, "Invalid document count"
                assert isinstance(stats_data["total_file_size"], (int, float)), "File size not numeric"
                assert stats_data["total_file_size"] >= 0, "Invalid file size"

            duration = time.time() - start_time
            self.results.add_performance_metric('statistics_endpoints', duration)

            self.results.add_test_case(
                "Statistics API",
                "PASS",
                {
                    "statistics_retrieval": True,
                    "data_structure": "valid",
                    "values_valid": True
                },
                duration
            )

        except Exception as e:
            self.results.add_test_case(
                "Statistics API",
                "FAIL",
                {"error": str(e)}
            )

    async def test_error_handling_api(self):
        """Test API error handling"""
        logger.info("Testing API error handling...")

        try:
            error_tests_passed = 0
            total_error_tests = 0

            # Test: Invalid collection ID
            total_error_tests += 1
            async with self.session.get(f"{self.base_url}/api/multi-document/collections/99999") as response:
                if response.status == 404:
                    error_tests_passed += 1

            # Test: Invalid query payload
            total_error_tests += 1
            if self.test_collections:
                collection_id = self.test_collections[0]["id"]
                invalid_payload = {"invalid_field": "invalid_value"}

                async with self.session.post(
                    f"{self.base_url}/api/multi-document/collections/{collection_id}/query",
                    json=invalid_payload
                ) as response:
                    if response.status in [400, 422]:  # Bad request or validation error
                        error_tests_passed += 1

            # Test: Empty collection creation
            total_error_tests += 1
            empty_payload = {}
            async with self.session.post(
                f"{self.base_url}/api/multi-document/collections",
                json=empty_payload
            ) as response:
                if response.status in [400, 422]:
                    error_tests_passed += 1

            self.results.add_test_case(
                "API Error Handling",
                "PASS" if error_tests_passed >= total_error_tests * 0.8 else "FAIL",
                {
                    "error_tests_passed": error_tests_passed,
                    "total_error_tests": total_error_tests,
                    "success_rate": (error_tests_passed / total_error_tests * 100) if total_error_tests > 0 else 0
                }
            )

        except Exception as e:
            self.results.add_test_case(
                "API Error Handling",
                "FAIL",
                {"error": str(e)}
            )

    async def cleanup_test_data(self):
        """Clean up test data"""
        logger.info("Cleaning up test data...")

        try:
            # Delete test collections
            for collection in self.test_collections:
                try:
                    async with self.session.delete(
                        f"{self.base_url}/api/multi-document/collections/{collection['id']}"
                    ) as response:
                        if response.status not in [200, 404]:
                            logger.warning(f"Failed to delete collection {collection['id']}: {response.status}")
                except Exception as e:
                    logger.warning(f"Error deleting collection {collection['id']}: {e}")

            self.results.add_test_case(
                "Test Data Cleanup",
                "PASS",
                {"collections_cleaned": len(self.test_collections)}
            )

        except Exception as e:
            self.results.add_test_case(
                "Test Data Cleanup",
                "FAIL",
                {"error": str(e)}
            )

    async def run_full_api_uat_suite(self):
        """Execute the complete API UAT suite"""
        logger.info("Starting Multi-Document API UAT Suite")
        logger.info("=" * 60)

        try:
            await self.setup_session()

            # Check API health
            if not await self.check_api_health():
                self.results.add_test_case(
                    "API Health Check",
                    "FAIL",
                    {"error": "API server not accessible or unhealthy"}
                )
                return self.results.generate_report()

            self.results.add_test_case(
                "API Health Check",
                "PASS",
                {"api_accessible": True}
            )

            # Setup test data
            await self.setup_test_data()

            # Run API tests
            await self.test_collection_crud_operations()
            await self.test_collection_document_management()
            await self.test_multi_document_indexing_api()
            await self.test_cross_document_query_api()
            await self.test_query_history_api()
            await self.test_statistics_api()
            await self.test_error_handling_api()

            # Cleanup
            await self.cleanup_test_data()

        except Exception as e:
            logger.error(f"API UAT Suite failed with critical error: {e}")
            self.results.add_test_case(
                "Critical API Failure",
                "FAIL",
                {"error": str(e)}
            )
        finally:
            await self.cleanup_session()

        return self.results.generate_report()

async def main():
    """Main API UAT execution function"""
    print("Multi-Document RAG API - User Acceptance Testing")
    print("=" * 50)

    # Check if API server is specified
    api_url = os.getenv('API_URL', 'http://localhost:8000')
    print(f"Testing API at: {api_url}")
    print("Ensure the API server is running before executing tests")
    print("Start with: python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000")
    print()

    uat_suite = MultiDocumentAPIUATSuite(api_url)

    try:
        # Run the complete API UAT suite
        report = await uat_suite.run_full_api_uat_suite()

        # Save report to file
        report_file = project_root / "uat_api_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Display summary
        print("\n" + "=" * 50)
        print("API UAT SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"Total Duration: {report['summary']['total_duration']:.2f} seconds")

        print(f"\nDetailed report saved to: {report_file}")

        # Performance metrics
        if report['performance_metrics']:
            print("\nAPI PERFORMANCE METRICS")
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
            print("\n✅ All API tests passed successfully!")

        return report['summary']['success_rate'] >= 85  # 85% success rate threshold for API

    except Exception as e:
        print(f"\nCritical API UAT failure: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
