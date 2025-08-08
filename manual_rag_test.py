#!/usr/bin/env python3
"""
Manual RAG Workflow Test

Tests the actual RAG functionality end-to-end using the working EnhancedRAGService.
This bypasses the blocked test suite to validate core functionality.
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, Any

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.database.connection import DatabaseConnection
from src.database.migrations import MigrationManager, MigrationRunner
from src.services.enhanced_rag_service import EnhancedRAGService
from src.database.models import DocumentModel
from src.repositories.document_repository import DocumentRepository

# Test configuration
TEST_MODE = True  # Set to False to test with real API
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "test-key-for-testing")

def create_test_pdf() -> str:
    """Create a simple test PDF file for testing."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        c = canvas.Canvas(temp_file.name, pagesize=letter)
        
        # Add test content
        c.drawString(100, 750, "Test Document for RAG Validation")
        c.drawString(100, 700, "This is a test PDF document created for RAG workflow testing.")
        c.drawString(100, 650, "It contains sample content about artificial intelligence.")
        c.drawString(100, 600, "Machine learning is a subset of AI that focuses on algorithms.")
        c.drawString(100, 550, "Natural language processing helps computers understand human language.")
        c.drawString(100, 500, "Vector embeddings represent text as numerical vectors.")
        c.drawString(100, 450, "Retrieval-Augmented Generation combines retrieval with generation.")
        c.drawString(100, 400, "Large Language Models can process and generate human-like text.")
        
        c.save()
        temp_file.close()
        
        return temp_file.name
    except ImportError:
        # Fallback: create a simple text file if reportlab is not available
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w')
        temp_file.write("""Test Document for RAG Validation

This is a test document created for RAG workflow testing.
It contains sample content about artificial intelligence.
Machine learning is a subset of AI that focuses on algorithms.
Natural language processing helps computers understand human language.
Vector embeddings represent text as numerical vectors.
Retrieval-Augmented Generation combines retrieval with generation.
Large Language Models can process and generate human-like text.
""")
        temp_file.close()
        return temp_file.name

def run_rag_workflow_test() -> Dict[str, Any]:
    """Run comprehensive RAG workflow test."""
    test_results = {
        "test_start_time": time.time(),
        "workflow_steps": {},
        "performance_metrics": {},
        "functionality_verified": {},
        "errors": [],
        "overall_success": False
    }
    
    db_connection = None
    rag_service = None
    test_pdf_path = None
    document = None
    
    try:
        # Step 1: Initialize Database Connection
        print("🔧 Step 1: Initializing database connection...")
        start_time = time.time()
        
        # Use in-memory database for testing
        db_connection = DatabaseConnection(":memory:")
        
        # Initialize database schema
        migration_manager = MigrationManager(db_connection)
        migration_runner = MigrationRunner(migration_manager)
        migration_runner.migrate_to_latest()
        
        test_results["workflow_steps"]["database_init"] = {
            "success": True,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
        print("✅ Database connection and schema initialized")
        
        # Step 2: Initialize RAG Service
        print("🔧 Step 2: Initializing RAG service...")
        start_time = time.time()
        
        rag_service = EnhancedRAGService(
            api_key=GEMINI_API_KEY,
            db_connection=db_connection,
            test_mode=TEST_MODE
        )
        
        test_results["workflow_steps"]["rag_service_init"] = {
            "success": True,
            "duration_ms": int((time.time() - start_time) * 1000),
            "test_mode": TEST_MODE
        }
        print("✅ RAG service initialized")
        
        # Step 3: Create Test Document
        print("🔧 Step 3: Creating test document...")
        start_time = time.time()
        
        test_pdf_path = create_test_pdf()
        
        # Add document to database
        doc_repo = DocumentRepository(db_connection)
        document = DocumentModel(
            title="RAG Test Document",
            file_path=test_pdf_path,
            file_size=Path(test_pdf_path).stat().st_size,
            file_hash="test-hash-" + str(int(time.time()))
        )
        document = doc_repo.create(document)
        
        test_results["workflow_steps"]["document_creation"] = {
            "success": True,
            "duration_ms": int((time.time() - start_time) * 1000),
            "document_id": document.id,
            "file_size_bytes": document.file_size
        }
        print(f"✅ Test document created: ID {document.id}")
        
        # Step 4: Build Vector Index
        print("🔧 Step 4: Building vector index...")
        start_time = time.time()
        
        vector_index = rag_service.build_index_from_document(document)
        
        test_results["workflow_steps"]["index_building"] = {
            "success": True,
            "duration_ms": int((time.time() - start_time) * 1000),
            "index_id": vector_index.id,
            "chunk_count": vector_index.chunk_count,
            "index_path": vector_index.index_path
        }
        print(f"✅ Vector index built: {vector_index.chunk_count} chunks")
        
        # Step 5: Load Index for Query
        print("🔧 Step 5: Loading index for query...")
        start_time = time.time()
        
        load_success = rag_service.load_index_for_document(document.id)
        
        test_results["workflow_steps"]["index_loading"] = {
            "success": load_success,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
        print(f"✅ Index loaded successfully: {load_success}")
        
        # Step 6: Execute RAG Queries
        print("🔧 Step 6: Executing RAG queries...")
        
        test_queries = [
            "What is this document about?",
            "What is machine learning?",
            "Explain vector embeddings",
            "How does RAG work?"
        ]
        
        query_results = []
        for i, query in enumerate(test_queries):
            start_time = time.time()
            
            try:
                response = rag_service.query_document(query, document.id)
                duration_ms = int((time.time() - start_time) * 1000)
                
                query_result = {
                    "query": query,
                    "success": True,
                    "response_length": len(response),
                    "duration_ms": duration_ms,
                    "response_preview": response[:100] + "..." if len(response) > 100 else response
                }
                query_results.append(query_result)
                print(f"✅ Query {i+1} successful ({duration_ms}ms): {response[:50]}...")
                
            except Exception as e:
                query_result = {
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "duration_ms": int((time.time() - start_time) * 1000)
                }
                query_results.append(query_result)
                print(f"❌ Query {i+1} failed: {e}")
        
        test_results["workflow_steps"]["query_execution"] = {
            "total_queries": len(test_queries),
            "successful_queries": sum(1 for r in query_results if r["success"]),
            "query_results": query_results,
            "average_response_time_ms": sum(r["duration_ms"] for r in query_results) / len(query_results)
        }
        
        # Step 7: Test Index Status and Recovery
        print("🔧 Step 7: Testing index status and recovery...")
        start_time = time.time()
        
        index_status = rag_service.get_document_index_status(document.id)
        cache_info = rag_service.get_enhanced_cache_info()
        
        test_results["workflow_steps"]["status_check"] = {
            "success": True,
            "duration_ms": int((time.time() - start_time) * 1000),
            "index_status": index_status,
            "has_index": index_status.get("has_index", False),
            "index_valid": index_status.get("index_valid", False),
            "can_query": index_status.get("can_query", False)
        }
        print(f"✅ Index status check: valid={index_status.get('index_valid')}")
        
        # Calculate overall success
        successful_steps = sum(1 for step in test_results["workflow_steps"].values() 
                             if step.get("success", False))
        total_steps = len(test_results["workflow_steps"])
        test_results["overall_success"] = successful_steps == total_steps
        
        # Performance metrics
        total_duration = time.time() - test_results["test_start_time"]
        test_results["performance_metrics"] = {
            "total_test_duration_seconds": total_duration,
            "successful_steps": successful_steps,
            "total_steps": total_steps,
            "success_rate": successful_steps / total_steps,
            "average_query_time_ms": test_results["workflow_steps"]["query_execution"]["average_response_time_ms"],
            "index_build_time_ms": test_results["workflow_steps"]["index_building"]["duration_ms"]
        }
        
        # Functionality verification
        test_results["functionality_verified"] = {
            "database_integration": test_results["workflow_steps"]["database_init"]["success"],
            "document_processing": test_results["workflow_steps"]["document_creation"]["success"],
            "vector_indexing": test_results["workflow_steps"]["index_building"]["success"],
            "index_loading": test_results["workflow_steps"]["index_loading"]["success"],
            "query_processing": test_results["workflow_steps"]["query_execution"]["successful_queries"] > 0,
            "status_monitoring": test_results["workflow_steps"]["status_check"]["success"]
        }
        
        print(f"🎉 RAG workflow test completed: {successful_steps}/{total_steps} steps successful")
        
    except Exception as e:
        test_results["errors"].append(f"Critical error: {str(e)}")
        test_results["overall_success"] = False
        print(f"💥 Critical error in RAG workflow: {e}")
        
    finally:
        # Cleanup
        try:
            if test_pdf_path and Path(test_pdf_path).exists():
                os.unlink(test_pdf_path)
                print("🧹 Test file cleaned up")
                
            if document and db_connection:
                # Cleanup database record
                doc_repo = DocumentRepository(db_connection)
                doc_repo.delete(document.id)
                print("🧹 Test document record cleaned up")
                
        except Exception as e:
            test_results["errors"].append(f"Cleanup error: {str(e)}")
            print(f"⚠️ Cleanup warning: {e}")
    
    return test_results

def main():
    """Main test execution."""
    print("🚀 Starting RAG Workflow Validation Test")
    print("=" * 60)
    
    # Run the comprehensive test
    results = run_rag_workflow_test()
    
    # Save results to file
    results_file = "rag_workflow_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"Overall Success: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
    print(f"Total Duration: {results['performance_metrics'].get('total_test_duration_seconds', 0):.2f}s")
    print(f"Steps Completed: {results['performance_metrics'].get('successful_steps', 0)}/{results['performance_metrics'].get('total_steps', 0)}")
    print(f"Success Rate: {results['performance_metrics'].get('success_rate', 0)*100:.1f}%")
    
    if results['workflow_steps'].get('query_execution'):
        query_info = results['workflow_steps']['query_execution']
        print(f"Query Success: {query_info['successful_queries']}/{query_info['total_queries']}")
        print(f"Avg Query Time: {query_info['average_response_time_ms']:.1f}ms")
    
    if results['errors']:
        print(f"\n❌ Errors ({len(results['errors'])}):")
        for error in results['errors']:
            print(f"  - {error}")
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    # Return appropriate exit code
    return 0 if results['overall_success'] else 1

if __name__ == "__main__":
    sys.exit(main())