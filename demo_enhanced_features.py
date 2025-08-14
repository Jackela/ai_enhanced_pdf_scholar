#!/usr/bin/env python3
"""
Demo script showing the enhanced DocumentLibraryService features.
This script demonstrates the newly implemented TODO items:
1. Enhanced database-level sorting
2. Content-based duplicate detection
3. Advanced cleanup operations
"""

import logging
import tempfile
from pathlib import Path

from src.database.connection import DatabaseConnection
from src.services.document_library_service import DocumentLibraryService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_demo_database():
    """Create a temporary database with demo schema."""
    temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_file.close()

    db = DatabaseConnection(temp_db_file.name)

    # Create documents table
    db.execute("""
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

    # Create vector_indexes table
    db.execute("""
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

    return db, temp_db_file.name


def create_demo_documents(service):
    """Create demo documents for testing."""
    logger.info("Creating demo documents...")

    # Create temporary document files
    temp_dir = Path(tempfile.mkdtemp())

    # Create demo PDF files
    demo_files = []
    for i in range(5):
        demo_file = temp_dir / f"demo_document_{i}.pdf"
        demo_file.write_text(f"Demo PDF content for document {i}")
        demo_files.append(demo_file)

    # Import documents with mock data
    documents = []
    titles = [
        "Python Programming Guide",
        "Python Programming Tutorial",  # Similar to first
        "Java Development Manual",
        "JavaScript Reference",
        "Data Science Handbook"
    ]

    content_hashes = [
        "hash_python_guide",
        "hash_python_guide",  # Duplicate content
        "hash_java_manual",
        "hash_js_reference",
        "hash_data_science"
    ]

    for i, (demo_file, title, content_hash) in enumerate(zip(demo_files, titles, content_hashes)):
        # Manually create document records since we don't have real PDFs
        from src.database.models import DocumentModel

        doc = DocumentModel(
            title=title,
            file_path=str(demo_file),
            file_hash=f"file_hash_{i}",
            content_hash=content_hash,
            file_size=1000 + i * 100,
            page_count=5 + i,
            _from_database=False
        )

        created_doc = service.document_repo.create(doc)
        documents.append(created_doc)
        logger.info(f"Created document: {title}")

    return documents, temp_dir


def demo_enhanced_sorting(service):
    """Demonstrate enhanced sorting functionality."""
    logger.info("\n" + "="*50)
    logger.info("DEMO: Enhanced Sorting Functionality")
    logger.info("="*50)

    # Test different sorting options
    sort_options = [
        ("title", "asc"),
        ("title", "desc"),
        ("file_size", "asc"),
        ("created_at", "desc")
    ]

    for sort_by, sort_order in sort_options:
        logger.info(f"\nSorting by {sort_by} ({sort_order}):")
        docs = service.get_documents(sort_by=sort_by, sort_order=sort_order)

        for i, doc in enumerate(docs, 1):
            if sort_by == "title":
                logger.info(f"  {i}. {doc.title}")
            elif sort_by == "file_size":
                logger.info(f"  {i}. {doc.title} (size: {doc.file_size} bytes)")
            else:
                logger.info(f"  {i}. {doc.title} (created: {doc.created_at})")


def demo_duplicate_detection(service):
    """Demonstrate content-based duplicate detection."""
    logger.info("\n" + "="*50)
    logger.info("DEMO: Content-based Duplicate Detection")
    logger.info("="*50)

    # Find duplicates with different methods
    duplicates = service.find_duplicate_documents(
        include_content_hash=True,
        include_title_similarity=True,
        title_similarity_threshold=0.6
    )

    logger.info(f"Found {len(duplicates)} groups of potential duplicates:")

    for i, (criteria, docs) in enumerate(duplicates, 1):
        logger.info(f"\nGroup {i}: {criteria}")
        logger.info(f"  Documents ({len(docs)}):")
        for doc in docs:
            logger.info(f"    - ID {doc.id}: {doc.title}")

        # Demonstrate duplicate resolution for content duplicates
        if "Exact content match" in criteria and len(docs) > 1:
            logger.info(f"  Resolving duplicates (keeping first document)...")
            resolution_result = service.resolve_duplicate_documents(
                docs, docs[0].id, remove_files=False
            )
            logger.info(f"  Kept document ID: {resolution_result['kept_document_id']}")
            logger.info(f"  Removed {len(resolution_result['removed_documents'])} documents")


def demo_advanced_cleanup(service):
    """Demonstrate advanced cleanup operations."""
    logger.info("\n" + "="*50)
    logger.info("DEMO: Advanced Cleanup Operations")
    logger.info("="*50)

    # Create some orphaned files and temp files for cleanup demo
    docs_dir = service.documents_dir

    # Create orphaned file
    orphaned_file = docs_dir / "orphaned_test.pdf"
    orphaned_file.write_text("orphaned file content")
    logger.info("Created orphaned file for demo")

    # Create temp files
    temp_file1 = docs_dir / "temp.tmp"
    temp_file2 = docs_dir / "backup.bak"
    temp_file1.write_text("temp content")
    temp_file2.write_text("backup content")
    logger.info("Created temporary files for demo")

    # Run comprehensive cleanup
    logger.info("\nRunning comprehensive cleanup...")
    cleanup_results = service.cleanup_library(
        remove_missing_files=True,
        remove_orphaned_files=True,
        optimize_database=True,
        cleanup_temp_files=True,
        verify_integrity=True
    )

    logger.info("Cleanup Results:")
    for key, value in cleanup_results.items():
        if key != "errors":
            logger.info(f"  {key}: {value}")

    if cleanup_results.get("errors"):
        logger.info("  Errors:")
        for error in cleanup_results["errors"]:
            logger.info(f"    - {error}")


def demo_library_statistics(service):
    """Demonstrate library statistics."""
    logger.info("\n" + "="*50)
    logger.info("DEMO: Enhanced Library Statistics")
    logger.info("="*50)

    stats = service.get_library_statistics()

    logger.info("Library Statistics:")
    if "documents" in stats:
        doc_stats = stats["documents"]
        logger.info(f"  Total Documents: {doc_stats.get('total_documents', 0)}")
        logger.info(f"  Total Size: {doc_stats.get('total_size_bytes', 0)} bytes")
        logger.info(f"  Average Size: {doc_stats.get('average_size_bytes', 0):.1f} bytes")
        logger.info(f"  Total Pages: {doc_stats.get('total_pages', 0)}")

    if "health" in stats:
        health_stats = stats["health"]
        logger.info("Library Health:")
        logger.info(f"  Orphaned Indexes: {health_stats.get('orphaned_indexes', 0)}")
        logger.info(f"  Invalid Indexes: {health_stats.get('invalid_indexes', 0)}")


def main():
    """Main demo function."""
    logger.info("Starting DocumentLibraryService Enhanced Features Demo")
    logger.info("="*60)

    # Set up demo environment
    db, db_path = create_demo_database()
    temp_docs_dir = tempfile.mkdtemp()

    try:
        # Create service
        service = DocumentLibraryService(db_connection=db, documents_dir=temp_docs_dir)

        # Create demo documents
        documents, demo_files_dir = create_demo_documents(service)

        # Run demos
        demo_enhanced_sorting(service)
        demo_duplicate_detection(service)
        demo_advanced_cleanup(service)
        demo_library_statistics(service)

        logger.info("\n" + "="*60)
        logger.info("Demo completed successfully!")
        logger.info("All enhanced features are working correctly.")

    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise

    finally:
        # Cleanup
        db.close_all_connections()
        Path(db_path).unlink(missing_ok=True)

        # Clean up temp directories
        import shutil
        if Path(temp_docs_dir).exists():
            shutil.rmtree(temp_docs_dir)
        if 'demo_files_dir' in locals() and demo_files_dir.exists():
            shutil.rmtree(demo_files_dir)


if __name__ == "__main__":
    main()