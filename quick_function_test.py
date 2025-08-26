#!/usr/bin/env python3
"""
Quick Function Test for AI Enhanced PDF Scholar
Tests actual functionality without starting full test suite
"""

import tempfile
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000/api"

def test_system_health():
    """Test system health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/system/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "PASS",
                "api_available": True,
                "database_connected": data.get("database_connected", False),
                "rag_service_available": data.get("rag_service_available", False),
                "api_key_configured": data.get("api_key_configured", False),
                "details": data
            }
        else:
            return {"status": "FAIL", "error": f"Status: {response.status_code}"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}

def test_library_stats():
    """Test library statistics endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/library/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "PASS",
                "endpoint_available": True,
                "documents_count": data.get("documents", {}).get("total", 0),
                "details": data
            }
        else:
            return {"status": "FAIL", "error": f"Status: {response.status_code}"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}

def test_documents_list():
    """Test documents list endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/documents", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "PASS",
                "endpoint_available": True,
                "documents_count": len(data.get("documents", [])),
                "total": data.get("total", 0),
                "details": data
            }
        else:
            return {"status": "FAIL", "error": f"Status: {response.status_code}"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}

def test_settings():
    """Test settings endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/settings", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "PASS",
                "endpoint_available": True,
                "has_gemini_api_key": "gemini_api_key" in data.get("data", {}),
                "details": data
            }
        else:
            return {"status": "FAIL", "error": f"Status: {response.status_code}"}
    except Exception as e:
        return {"status": "FAIL", "error": str(e)}

def create_test_pdf():
    """Create a simple test PDF for upload testing"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        # Create temporary PDF
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')

        # Create PDF content
        c = canvas.Canvas(temp_file.name, pagesize=letter)
        width, height = letter

        c.drawString(100, height - 100, "Test Document for AI Enhanced PDF Scholar")
        c.drawString(100, height - 130, "This is a test document created for functionality testing.")
        c.drawString(100, height - 160, "It contains some sample text to test PDF processing capabilities.")
        c.drawString(100, height - 190, "The system should be able to extract this text.")
        c.drawString(100, height - 220, "Citation example: Smith, J. (2023). Test Article. Test Journal, 1(1), 1-10.")

        c.save()
        return temp_file.name

    except ImportError:
        # Create a simple text file if reportlab not available
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w')
        temp_file.write("""Test Document for AI Enhanced PDF Scholar
This is a test document created for functionality testing.
It contains some sample text to test text processing capabilities.
The system should be able to process this text.
Citation example: Smith, J. (2023). Test Article. Test Journal, 1(1), 1-10.
""")
        temp_file.close()
        return temp_file.name

def test_document_upload():
    """Test document upload functionality"""
    test_file = None
    try:
        test_file = create_test_pdf()

        with open(test_file, 'rb') as f:
            files = {'file': f}
            data = {
                'title': 'Test Document Upload',
                'auto_build_index': 'true',
                'check_duplicates': 'true'
            }

            response = requests.post(f"{BASE_URL}/documents/upload",
                                   files=files, data=data, timeout=30)

        if response.status_code == 200:
            result_data = response.json()
            return {
                "status": "PASS",
                "upload_successful": True,
                "document_id": result_data.get("document_id"),
                "details": result_data
            }
        else:
            return {"status": "FAIL", "error": f"Status: {response.status_code}, Response: {response.text[:200]}"}

    except Exception as e:
        return {"status": "FAIL", "error": str(e)}

    finally:
        if test_file and Path(test_file).exists():
            Path(test_file).unlink()

def test_rag_query(document_id=None):
    """Test RAG query functionality"""
    if not document_id:
        # Try to get any document ID from the documents list
        try:
            response = requests.get(f"{BASE_URL}/documents", timeout=5)
            if response.status_code == 200:
                docs = response.json().get("documents", [])
                if docs:
                    document_id = docs[0].get("id")
        except:
            pass

    if not document_id:
        return {"status": "SKIP", "error": "No document available for RAG testing"}

    try:
        payload = {
            "document_id": document_id,
            "query": "What is this document about?",
            "max_tokens": 100
        }

        response = requests.post(f"{BASE_URL}/rag/query",
                               json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "PASS",
                "rag_functional": True,
                "response": data.get("response", "")[:100] + "..." if len(data.get("response", "")) > 100 else data.get("response", ""),
                "details": data
            }
        else:
            return {"status": "FAIL", "error": f"Status: {response.status_code}, Response: {response.text[:200]}"}

    except Exception as e:
        return {"status": "FAIL", "error": str(e)}

def run_comprehensive_test():
    """Run comprehensive functionality test"""
    print("🚀 AI Enhanced PDF Scholar - Comprehensive Function Test")
    print("=" * 60)

    results = {}

    # Test 1: System Health
    print("\n1️⃣ Testing System Health...")
    results["system_health"] = test_system_health()
    print(f"   Status: {results['system_health']['status']}")
    if results['system_health']['status'] == 'PASS':
        health = results['system_health']
        print(f"   ✅ API Available: {health['api_available']}")
        print(f"   📊 Database Connected: {health['database_connected']}")
        print(f"   🤖 RAG Service: {health['rag_service_available']}")
        print(f"   🔑 API Key Configured: {health['api_key_configured']}")
    else:
        print(f"   ❌ Error: {results['system_health'].get('error')}")

    # Test 2: Library Stats
    print("\n2️⃣ Testing Library Statistics...")
    results["library_stats"] = test_library_stats()
    print(f"   Status: {results['library_stats']['status']}")
    if results['library_stats']['status'] == 'PASS':
        stats = results['library_stats']
        print(f"   📁 Documents Count: {stats['documents_count']}")
    else:
        print(f"   ❌ Error: {results['library_stats'].get('error')}")

    # Test 3: Documents List
    print("\n3️⃣ Testing Documents List...")
    results["documents_list"] = test_documents_list()
    print(f"   Status: {results['documents_list']['status']}")
    if results['documents_list']['status'] == 'PASS':
        docs = results['documents_list']
        print(f"   📄 Documents Found: {docs['documents_count']}")
        print(f"   📊 Total Count: {docs['total']}")
    else:
        print(f"   ❌ Error: {results['documents_list'].get('error')}")

    # Test 4: Settings
    print("\n4️⃣ Testing Settings Configuration...")
    results["settings"] = test_settings()
    print(f"   Status: {results['settings']['status']}")
    if results['settings']['status'] == 'PASS':
        settings = results['settings']
        print(f"   🔑 Gemini API Key: {'✅ Configured' if settings['has_gemini_api_key'] else '❌ Missing'}")
    else:
        print(f"   ❌ Error: {results['settings'].get('error')}")

    # Test 5: Document Upload
    print("\n5️⃣ Testing Document Upload...")
    results["document_upload"] = test_document_upload()
    print(f"   Status: {results['document_upload']['status']}")
    if results['document_upload']['status'] == 'PASS':
        upload = results['document_upload']
        print(f"   📤 Upload Successful: {upload['upload_successful']}")
        print(f"   🆔 Document ID: {upload.get('document_id')}")
        uploaded_doc_id = upload.get('document_id')
    else:
        print(f"   ❌ Error: {results['document_upload'].get('error')}")
        uploaded_doc_id = None

    # Test 6: RAG Query
    print("\n6️⃣ Testing RAG Query...")
    results["rag_query"] = test_rag_query(uploaded_doc_id)
    print(f"   Status: {results['rag_query']['status']}")
    if results['rag_query']['status'] == 'PASS':
        rag = results['rag_query']
        print(f"   🤖 RAG Functional: {rag['rag_functional']}")
        print(f"   💬 Sample Response: {rag['response']}")
    elif results['rag_query']['status'] == 'SKIP':
        print(f"   ⏭️  Skipped: {results['rag_query'].get('error')}")
    else:
        print(f"   ❌ Error: {results['rag_query'].get('error')}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print("=" * 60)

    passed = sum(1 for r in results.values() if r.get('status') == 'PASS')
    failed = sum(1 for r in results.values() if r.get('status') == 'FAIL')
    skipped = sum(1 for r in results.values() if r.get('status') == 'SKIP')
    total = len(results)

    for test_name, result in results.items():
        status_icon = "✅" if result['status'] == 'PASS' else "❌" if result['status'] == 'FAIL' else "⏭️"
        print(f"{test_name.replace('_', ' ').title():<25} {status_icon} {result['status']}")

    print("-" * 60)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Skipped: {skipped} ⏭️")

    if failed == 0:
        print("\n🎉 All critical tests passed!")
    else:
        print(f"\n⚠️  {failed} tests failed. Review the results above.")

    return results

if __name__ == "__main__":
    results = run_comprehensive_test()
