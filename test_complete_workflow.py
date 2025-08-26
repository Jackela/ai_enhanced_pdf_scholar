#!/usr/bin/env python3
"""
Complete Workflow Test for AI Enhanced PDF Scholar

Tests the entire pipeline from document upload to RAG queries.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

import aiohttp


class WorkflowTester:
    """Test the complete AI Enhanced PDF Scholar workflow."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_system_health(self) -> bool:
        """Test if the system is healthy."""
        try:
            async with self.session.get(f"{self.base_url}/api/system/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ System Health: {data.get('status', 'unknown')}")
                    print(f"   Database: {'✅' if data.get('database_connected') else '❌'}")
                    print(f"   RAG Service: {'✅' if data.get('rag_service_available') else '❌'}")
                    print(f"   API Key: {'✅' if data.get('api_key_configured') else '❌'}")
                    return data.get('status') == 'healthy'
                else:
                    print(f"❌ Health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False

    async def test_settings_api(self) -> bool:
        """Test settings API endpoints."""
        try:
            # Test GET settings
            async with self.session.get(f"{self.base_url}/api/system/settings") as response:
                if response.status == 200:
                    settings = await response.json()
                    print(f"✅ Settings loaded: RAG enabled = {settings.get('rag_enabled')}")
                    return True
                else:
                    print(f"❌ Settings load failed: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Settings test error: {e}")
            return False

    async def test_library_operations(self) -> int | None:
        """Test document library operations."""
        try:
            # Test list documents
            async with self.session.get(f"{self.base_url}/api/documents/") as response:
                if response.status == 200:
                    data = await response.json()
                    documents = data.get('documents', [])
                    print(f"✅ Library loaded: {len(documents)} documents found")

                    # Return first document ID if available
                    if documents:
                        doc_id = documents[0].get('id')
                        print(f"   First document: '{documents[0].get('title')}' (ID: {doc_id})")
                        return doc_id
                    else:
                        print("   No documents found in library")
                        return None
                else:
                    print(f"❌ Library load failed: {response.status}")
                    return None
        except Exception as e:
            print(f"❌ Library test error: {e}")
            return None

    async def test_document_upload(self) -> int | None:
        """Test document upload functionality."""
        try:
            # Check if we have a sample PDF to upload
            sample_pdf = None
            possible_pdfs = [
                Path("sample.pdf"),
                Path("test.pdf"),
                Path("docs/sample.pdf")
            ]

            for pdf_path in possible_pdfs:
                if pdf_path.exists():
                    sample_pdf = pdf_path
                    break

            if not sample_pdf:
                print("⚠️  No sample PDF found for upload test, skipping...")
                return None

            # Upload the file
            data = aiohttp.FormData()
            data.add_field('file',
                          open(sample_pdf, 'rb'),
                          filename=sample_pdf.name,
                          content_type='application/pdf')

            async with self.session.post(f"{self.base_url}/api/documents/upload",
                                       data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    doc_id = result.get('document', {}).get('id')
                    print(f"✅ Document uploaded successfully (ID: {doc_id})")
                    return doc_id
                else:
                    error_text = await response.text()
                    print(f"❌ Upload failed: {response.status} - {error_text}")
                    return None

        except Exception as e:
            print(f"❌ Upload test error: {e}")
            return None

    async def test_rag_query(self, document_id: int) -> bool:
        """Test RAG query functionality."""
        try:
            query_data = {
                "query": "What are the key features of the AI Enhanced PDF Scholar?",
                "document_id": document_id
            }

            async with self.session.post(f"{self.base_url}/api/rag/query",
                                       json=query_data) as response:
                if response.status == 200:
                    result = await response.json()
                    answer = result.get('answer', '')
                    print("✅ RAG Query successful")
                    print(f"   Query: {query_data['query']}")
                    print(f"   Answer: {answer[:200]}{'...' if len(answer) > 200 else ''}")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ RAG query failed: {response.status} - {error_text}")
                    return False

        except Exception as e:
            print(f"❌ RAG query error: {e}")
            return False

    async def test_vector_operations(self, document_id: int) -> bool:
        """Test vector indexing operations."""
        try:
            # Test vector index status
            async with self.session.get(f"{self.base_url}/api/documents/{document_id}/integrity") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Vector index status: {'healthy' if result.get('is_healthy') else 'unhealthy'}")
                    return True
                else:
                    print(f"❌ Vector status check failed: {response.status}")
                    return False

        except Exception as e:
            print(f"❌ Vector operations error: {e}")
            return False

    async def run_complete_test(self) -> dict[str, Any]:
        """Run the complete workflow test."""
        print("🚀 Starting AI Enhanced PDF Scholar Complete Workflow Test")
        print("=" * 60)

        results = {
            "system_health": False,
            "settings_api": False,
            "library_operations": False,
            "document_upload": False,
            "vector_operations": False,
            "rag_query": False,
            "overall_success": False
        }

        # Test 1: System Health
        print("\n1️⃣ Testing System Health...")
        results["system_health"] = await self.test_system_health()

        # Test 2: Settings API
        print("\n2️⃣ Testing Settings API...")
        results["settings_api"] = await self.test_settings_api()

        # Test 3: Library Operations
        print("\n3️⃣ Testing Library Operations...")
        existing_doc_id = await self.test_library_operations()
        results["library_operations"] = existing_doc_id is not None or existing_doc_id == 0

        # Test 4: Document Upload
        print("\n4️⃣ Testing Document Upload...")
        uploaded_doc_id = await self.test_document_upload()
        results["document_upload"] = uploaded_doc_id is not None

        # Use uploaded document or existing document for further tests
        test_doc_id = uploaded_doc_id or existing_doc_id

        if test_doc_id is not None:
            # Wait a moment for processing
            print("   Waiting for document processing...")
            await asyncio.sleep(2)

            # Test 5: Vector Operations
            print("\n5️⃣ Testing Vector Operations...")
            results["vector_operations"] = await self.test_vector_operations(test_doc_id)

            # Test 6: RAG Query
            print("\n6️⃣ Testing RAG Query...")
            results["rag_query"] = await self.test_rag_query(test_doc_id)
        else:
            print("\n⚠️  Skipping vector and RAG tests (no document available)")

        # Calculate overall success
        core_tests = ["system_health", "settings_api", "library_operations"]
        advanced_tests = ["document_upload", "vector_operations", "rag_query"]

        core_success = all(results[test] for test in core_tests)
        advanced_success = any(results[test] for test in advanced_tests)

        results["overall_success"] = core_success and advanced_success

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Test Results Summary:")
        print("=" * 60)

        for test_name, success in results.items():
            if test_name != "overall_success":
                status = "✅ PASS" if success else "❌ FAIL"
                print(f"{test_name.replace('_', ' ').title():.<25} {status}")

        print("-" * 60)
        overall_status = "✅ SUCCESS" if results["overall_success"] else "❌ FAILURE"
        print(f"Overall Result{'':<15} {overall_status}")

        if results["overall_success"]:
            print("\n🎉 All core systems are working correctly!")
            print("💡 The AI Enhanced PDF Scholar is ready for use.")
        else:
            print("\n⚠️  Some tests failed. Check the system configuration.")

        return results

async def main():
    """Main test entry point."""
    print("AI Enhanced PDF Scholar - Complete Workflow Test")

    # Check if server is running
    try:
        async with WorkflowTester() as tester:
            results = await tester.run_complete_test()

            # Exit with appropriate code
            sys.exit(0 if results["overall_success"] else 1)

    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
