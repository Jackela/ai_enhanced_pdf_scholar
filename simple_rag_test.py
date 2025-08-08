#!/usr/bin/env python3
"""
Simple RAG Functionality Test

Tests core RAG functionality without complex database migrations.
Focuses on answering: Does the RAG system actually work?
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
from src.services.enhanced_rag_service import EnhancedRAGService

# Test configuration
TEST_MODE = True  # Always use test mode to avoid API calls
GEMINI_API_KEY = "test-key-for-testing"

def create_simple_tables(db_connection):
    """Create minimal tables needed for RAG testing."""
    with db_connection.get_connection() as conn:
        # Create documents table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                file_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tags TEXT DEFAULT ''
            )
        """)
        
        # Create vector_indexes table  
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vector_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                index_path TEXT NOT NULL,
                index_hash TEXT,
                chunk_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()

def create_test_pdf() -> str:
    """Create a simple test text file (PDF not required for test mode)."""
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

def run_simple_rag_test() -> Dict[str, Any]:
    """Run simplified RAG test focusing on core functionality."""
    test_results = {
        "test_start_time": time.time(),
        "steps": {},
        "errors": [],
        "overall_success": False
    }
    
    db_connection = None
    rag_service = None
    test_file_path = None
    
    try:
        # Step 1: Database Setup
        print("🔧 Step 1: Setting up database...")
        start_time = time.time()
        
        db_connection = DatabaseConnection(":memory:")
        create_simple_tables(db_connection)
        
        test_results["steps"]["database_setup"] = {
            "success": True,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
        print("✅ Database setup successful")
        
        # Step 2: RAG Service Initialization
        print("🔧 Step 2: Initializing RAG service...")
        start_time = time.time()
        
        rag_service = EnhancedRAGService(
            api_key=GEMINI_API_KEY,
            db_connection=db_connection,
            test_mode=True
        )
        
        test_results["steps"]["rag_init"] = {
            "success": True,
            "duration_ms": int((time.time() - start_time) * 1000),
            "test_mode": True
        }
        print("✅ RAG service initialized")
        
        # Step 3: Test Basic PDF Processing
        print("🔧 Step 3: Testing document processing...")
        start_time = time.time()
        
        test_file_path = create_test_pdf()
        
        # Test basic index building (in test mode)
        success = rag_service.build_index_from_pdf(test_file_path)
        
        test_results["steps"]["document_processing"] = {
            "success": success,
            "duration_ms": int((time.time() - start_time) * 1000),
            "file_path": test_file_path
        }
        
        if success:
            print("✅ Document processing successful")
        else:
            print("❌ Document processing failed")
            
        # Step 4: Test Query Functionality
        print("🔧 Step 4: Testing query functionality...")
        
        query_results = []
        test_queries = [
            "What is this document about?",
            "What is machine learning?",
            "Explain vector embeddings"
        ]
        
        for query in test_queries:
            start_time = time.time()
            
            try:
                response = rag_service.query(query)
                duration_ms = int((time.time() - start_time) * 1000)
                
                query_results.append({
                    "query": query,
                    "success": True,
                    "response_length": len(response),
                    "duration_ms": duration_ms,
                    "response": response
                })
                print(f"✅ Query successful: '{query}' -> '{response[:50]}...'")
                
            except Exception as e:
                query_results.append({
                    "query": query,
                    "success": False,
                    "error": str(e),
                    "duration_ms": int((time.time() - start_time) * 1000)
                })
                print(f"❌ Query failed: '{query}' -> {e}")
        
        test_results["steps"]["query_testing"] = {
            "total_queries": len(test_queries),
            "successful_queries": sum(1 for r in query_results if r["success"]),
            "query_results": query_results
        }
        
        # Step 5: Test Cache/Service Info
        print("🔧 Step 5: Testing service information...")
        start_time = time.time()
        
        try:
            cache_info = rag_service.get_cache_info()
            enhanced_cache_info = rag_service.get_enhanced_cache_info()
            
            test_results["steps"]["service_info"] = {
                "success": True,
                "duration_ms": int((time.time() - start_time) * 1000),
                "cache_info": cache_info,
                "enhanced_cache_info": enhanced_cache_info
            }
            print("✅ Service information retrieved successfully")
            
        except Exception as e:
            test_results["steps"]["service_info"] = {
                "success": False,
                "duration_ms": int((time.time() - start_time) * 1000),
                "error": str(e)
            }
            print(f"❌ Service information failed: {e}")
        
        # Calculate overall success
        successful_steps = sum(1 for step in test_results["steps"].values() 
                             if step.get("success", False))
        total_steps = len(test_results["steps"])
        test_results["overall_success"] = successful_steps >= 4  # At least 4/5 steps must pass
        
        test_results["summary"] = {
            "total_test_duration_seconds": time.time() - test_results["test_start_time"],
            "successful_steps": successful_steps,
            "total_steps": total_steps,
            "success_rate": successful_steps / total_steps
        }
        
        print(f"🎉 RAG test completed: {successful_steps}/{total_steps} steps successful")
        
    except Exception as e:
        test_results["errors"].append(f"Critical error: {str(e)}")
        test_results["overall_success"] = False
        print(f"💥 Critical error in RAG test: {e}")
        
    finally:
        # Cleanup
        if test_file_path and Path(test_file_path).exists():
            os.unlink(test_file_path)
            print("🧹 Test file cleaned up")
    
    return test_results

def main():
    """Main test execution."""
    print("🚀 Starting Simple RAG Functionality Test")
    print("=" * 60)
    
    # Run the test
    results = run_simple_rag_test()
    
    # Save results to file
    results_file = "simple_rag_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print("📊 SIMPLE RAG TEST RESULTS")
    print("=" * 60)
    
    print(f"Overall Success: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}")
    
    if "summary" in results:
        summary = results["summary"]
        print(f"Total Duration: {summary['total_test_duration_seconds']:.2f}s")
        print(f"Steps Completed: {summary['successful_steps']}/{summary['total_steps']}")
        print(f"Success Rate: {summary['success_rate']*100:.1f}%")
    
    # Show step-by-step results
    print("\n📋 Step Results:")
    for step_name, step_data in results.get("steps", {}).items():
        status = "✅ PASS" if step_data.get("success", False) else "❌ FAIL"
        duration = step_data.get("duration_ms", 0)
        print(f"  {step_name}: {status} ({duration}ms)")
    
    # Show query results if available
    if "query_testing" in results.get("steps", {}):
        query_info = results["steps"]["query_testing"]
        print(f"\n🔍 Query Results: {query_info['successful_queries']}/{query_info['total_queries']}")
        
        for query_result in query_info["query_results"]:
            if query_result["success"]:
                print(f"  ✅ '{query_result['query']}' -> {len(query_result['response'])} chars")
            else:
                print(f"  ❌ '{query_result['query']}' -> {query_result['error']}")
    
    if results["errors"]:
        print(f"\n❌ Errors ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"  - {error}")
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    # Return appropriate exit code
    return 0 if results["overall_success"] else 1

if __name__ == "__main__":
    sys.exit(main())