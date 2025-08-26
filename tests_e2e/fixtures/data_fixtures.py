"""
Data Fixtures for E2E Testing

Provides test data including PDFs, users, and documents for comprehensive testing.
"""

import random
import string
from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


class TestDataGenerator:
    """Generate various types of test data."""

    @staticmethod
    def random_string(length: int = 10) -> str:
        """Generate a random string."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    @staticmethod
    def random_email() -> str:
        """Generate a random email address."""
        return f"test_{TestDataGenerator.random_string(8)}@example.com"

    @staticmethod
    def random_phone() -> str:
        """Generate a random phone number."""
        return f"+1{random.randint(2000000000, 9999999999)}"

    @staticmethod
    def create_pdf_content(
        title: str = "Test Document",
        content: str = "This is test content",
        pages: int = 1,
        with_citations: bool = False
    ) -> bytes:
        """
        Create PDF content with configurable properties.
        """
        pdf_header = b"%PDF-1.4\n"

        # Simple PDF structure
        objects = []

        # Catalog
        objects.append(b"1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n")

        # Pages
        page_refs = ' '.join([f"{i+3} 0 R" for i in range(pages)])
        objects.append(f"2 0 obj\n<</Type/Pages/Kids[{page_refs}]/Count {pages}>>\nendobj\n".encode())

        # Individual pages
        for i in range(pages):
            page_num = i + 3
            content_num = pages + i + 3

            # Page object
            objects.append(
                f"{page_num} 0 obj\n"
                f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents {content_num} 0 R/Resources<</Font<</F1 {pages*2+3} 0 R>>>>>> \n"
                f"endobj\n".encode()
            )

            # Content stream
            page_content = f"BT /F1 12 Tf 72 720 Td ({title} - Page {i+1}) Tj ET\n"
            if with_citations and i == 0:
                page_content += "BT /F1 10 Tf 72 680 Td ([1] Smith et al., 2024) Tj ET\n"
                page_content += "BT /F1 10 Tf 72 660 Td ([2] Johnson, 2023) Tj ET\n"
            page_content += f"BT /F1 10 Tf 72 640 Td ({content}) Tj ET\n"

            stream = page_content.encode()
            objects.append(
                f"{content_num} 0 obj\n"
                f"<</Length {len(stream)}>>\n"
                f"stream\n".encode() +
                stream +
                b"\nendstream\nendobj\n"
            )

        # Font object
        font_obj_num = pages * 2 + 3
        objects.append(
            f"{font_obj_num} 0 obj\n"
            f"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>\n"
            f"endobj\n".encode()
        )

        # Build complete PDF
        pdf_content = pdf_header
        for obj in objects:
            pdf_content += obj

        # Cross-reference table
        xref = b"xref\n"
        xref += f"0 {len(objects) + 1}\n".encode()
        xref += b"0000000000 65535 f \n"

        offset = len(pdf_header)
        for obj in objects:
            xref += f"{offset:010d} 00000 n \n".encode()
            offset += len(obj)

        # Trailer
        trailer = f"trailer\n<</Size {len(objects) + 1}/Root 1 0 R>>\n".encode()
        trailer += b"startxref\n"
        trailer += f"{len(pdf_content)}\n".encode()
        trailer += b"%%EOF"

        return pdf_content + xref + trailer


@pytest.fixture
def test_pdf_files() -> Generator[dict[str, Path], None, None]:
    """
    Create various test PDF files for different scenarios.
    """
    generator = TestDataGenerator()
    test_files = {}

    # Create test directory
    test_dir = Path("tests_e2e/test_data/pdfs")
    test_dir.mkdir(parents=True, exist_ok=True)

    # Standard test PDF
    standard_pdf = test_dir / "standard_test.pdf"
    standard_pdf.write_bytes(generator.create_pdf_content(
        title="Standard Test Document",
        content="This is a standard test document for E2E testing.",
        pages=3
    ))
    test_files["standard"] = standard_pdf

    # PDF with citations
    citations_pdf = test_dir / "citations_test.pdf"
    citations_pdf.write_bytes(generator.create_pdf_content(
        title="Document with Citations",
        content="This document contains academic citations.",
        pages=2,
        with_citations=True
    ))
    test_files["with_citations"] = citations_pdf

    # Large PDF
    large_pdf = test_dir / "large_test.pdf"
    large_pdf.write_bytes(generator.create_pdf_content(
        title="Large Document",
        content="This is a large document for performance testing.",
        pages=50
    ))
    test_files["large"] = large_pdf

    # Empty PDF (minimal valid PDF)
    empty_pdf = test_dir / "empty_test.pdf"
    empty_pdf.write_bytes(generator.create_pdf_content(
        title="",
        content="",
        pages=1
    ))
    test_files["empty"] = empty_pdf

    # Special characters PDF
    special_pdf = test_dir / "special_chars.pdf"
    special_pdf.write_bytes(generator.create_pdf_content(
        title="Special Characters Test",
        content="Testing with émojis 🚀 and spëcial çharacters",
        pages=1
    ))
    test_files["special_chars"] = special_pdf

    yield test_files

    # Cleanup
    for file in test_files.values():
        if file.exists():
            file.unlink()


@pytest.fixture
def test_user_data() -> dict[str, Any]:
    """
    Generate test user data.
    """
    generator = TestDataGenerator()

    return {
        "admin": {
            "username": "admin_test",
            "email": "admin@test.com",
            "password": "Admin123!@#",
            "role": "admin",
            "full_name": "Test Admin User"
        },
        "regular": {
            "username": f"user_{generator.random_string(6)}",
            "email": generator.random_email(),
            "password": "User123!@#",
            "role": "user",
            "full_name": "Test Regular User"
        },
        "guest": {
            "username": f"guest_{generator.random_string(6)}",
            "email": generator.random_email(),
            "password": "Guest123!@#",
            "role": "guest",
            "full_name": "Test Guest User"
        }
    }


@pytest.fixture
def test_documents_data() -> list[dict[str, Any]]:
    """
    Generate test document metadata.
    """
    documents = []
    categories = ["Research", "Tutorial", "Reference", "Report", "Article"]
    statuses = ["pending", "processing", "completed", "failed"]

    for i in range(10):
        doc_date = datetime.now() - timedelta(days=random.randint(0, 365))
        documents.append({
            "id": i + 1,
            "title": f"Test Document {i + 1}",
            "filename": f"test_doc_{i + 1}.pdf",
            "description": f"This is test document number {i + 1}",
            "category": random.choice(categories),
            "tags": [f"tag{j}" for j in range(random.randint(1, 5))],
            "status": random.choice(statuses),
            "upload_date": doc_date.isoformat(),
            "file_size": random.randint(100000, 10000000),
            "page_count": random.randint(1, 100),
            "author": f"Author {random.randint(1, 5)}",
            "citations_count": random.randint(0, 50),
            "metadata": {
                "version": "1.0",
                "language": "en",
                "keywords": [f"keyword{j}" for j in range(random.randint(3, 8))]
            }
        })

    return documents


@pytest.fixture
def mock_rag_responses() -> dict[str, dict[str, Any]]:
    """
    Generate mock RAG query responses for testing.
    """
    return {
        "simple_query": {
            "query": "What is machine learning?",
            "response": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
            "confidence": 0.95,
            "sources": [
                {"document": "ML_Basics.pdf", "page": 1, "relevance": 0.98},
                {"document": "AI_Introduction.pdf", "page": 15, "relevance": 0.87}
            ],
            "processing_time": 1.23
        },
        "complex_query": {
            "query": "Compare supervised and unsupervised learning with examples",
            "response": "Supervised learning uses labeled data to train models (e.g., email spam detection), while unsupervised learning finds patterns in unlabeled data (e.g., customer segmentation).",
            "confidence": 0.89,
            "sources": [
                {"document": "ML_Algorithms.pdf", "page": 23, "relevance": 0.92},
                {"document": "Data_Science_Guide.pdf", "page": 45, "relevance": 0.85},
                {"document": "ML_Basics.pdf", "page": 8, "relevance": 0.79}
            ],
            "processing_time": 2.56
        },
        "no_results_query": {
            "query": "Random nonsense query xyzabc123",
            "response": "I couldn't find relevant information to answer your query.",
            "confidence": 0.0,
            "sources": [],
            "processing_time": 0.45
        },
        "error_query": {
            "query": "Trigger error for testing",
            "error": "An error occurred during processing",
            "error_code": "RAG_PROCESSING_ERROR",
            "processing_time": 0.12
        }
    }


@pytest.fixture
def invalid_files() -> Generator[dict[str, Path], None, None]:
    """
    Create invalid files for negative testing.
    """
    test_dir = Path("tests_e2e/test_data/invalid")
    test_dir.mkdir(parents=True, exist_ok=True)

    invalid_files = {}

    # Not a PDF file
    txt_file = test_dir / "not_a_pdf.txt"
    txt_file.write_text("This is not a PDF file")
    invalid_files["not_pdf"] = txt_file

    # Corrupted PDF
    corrupted_pdf = test_dir / "corrupted.pdf"
    corrupted_pdf.write_bytes(b"%PDF-1.4\nCorrupted content that is not valid PDF")
    invalid_files["corrupted"] = corrupted_pdf

    # Empty file
    empty_file = test_dir / "empty.pdf"
    empty_file.write_bytes(b"")
    invalid_files["empty"] = empty_file

    # File too large (create a reference, not actual file)
    large_file_ref = test_dir / "too_large.pdf"
    large_file_ref.write_text("Reference to a file that would be too large")
    invalid_files["too_large"] = large_file_ref

    # File with malicious name
    malicious_name = test_dir / "../../etc/passwd.pdf"
    safe_malicious = test_dir / "malicious_name.pdf"
    safe_malicious.write_bytes(b"%PDF-1.4\nTest")
    invalid_files["malicious_name"] = safe_malicious

    yield invalid_files

    # Cleanup
    for file in invalid_files.values():
        if file.exists():
            file.unlink()


@pytest.fixture
def performance_test_data() -> dict[str, Any]:
    """
    Generate data for performance testing.
    """
    return {
        "concurrent_users": [1, 5, 10, 25, 50],
        "file_sizes": [
            {"name": "small", "size": 100 * 1024, "pages": 1},      # 100KB
            {"name": "medium", "size": 1 * 1024 * 1024, "pages": 10},   # 1MB
            {"name": "large", "size": 10 * 1024 * 1024, "pages": 100},  # 10MB
            {"name": "xlarge", "size": 50 * 1024 * 1024, "pages": 500}, # 50MB
        ],
        "query_complexity": [
            {"type": "simple", "tokens": 10, "expected_time": 1.0},
            {"type": "moderate", "tokens": 50, "expected_time": 2.0},
            {"type": "complex", "tokens": 200, "expected_time": 5.0},
        ],
        "batch_sizes": [1, 10, 25, 50, 100],
        "response_time_thresholds": {
            "api_response": 100,  # ms
            "page_load": 1000,    # ms
            "file_upload": 5000,  # ms
            "rag_query": 3000,    # ms
        }
    }


@pytest.fixture
def security_test_payloads() -> dict[str, list[str]]:
    """
    Generate security testing payloads.
    """
    return {
        "xss": [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            '"><script>alert("XSS")</script>',
        ],
        "sql_injection": [
            "' OR '1'='1",
            "1; DROP TABLE users--",
            "admin'--",
            "1' UNION SELECT NULL--",
            "' OR 1=1--",
            "'; DROP TABLE documents;--",
        ],
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..;/etc/passwd",
        ],
        "command_injection": [
            "; ls -la",
            "| whoami",
            "& net user",
            "`cat /etc/passwd`",
            "$(whoami)",
            "; rm -rf /",
        ],
        "ldap_injection": [
            "*",
            "*)(uid=*",
            "*)(|(uid=*))",
            "admin*",
            "*)(objectClass=*",
        ],
        "xml_injection": [
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
            '<![CDATA[<script>alert("XSS")</script>]]>',
        ],
        "header_injection": [
            "test\r\nX-Injected: header",
            "test\nSet-Cookie: session=hijacked",
            "test\r\n\r\n<html>injected</html>",
        ]
    }
