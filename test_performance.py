#!/usr/bin/env python3
"""
Performance test script for CI/CD pipeline
"""
import os
import sys
import tempfile
import time

# Add src to path
sys.path.insert(0, '.')

from src.database.connection import DatabaseConnection
from src.database.models import DocumentModel
from src.database.modular_migrator import ModularDatabaseMigrator as DatabaseMigrator
from src.repositories.document_repository import DocumentRepository


def run_performance_test():
    """Run performance tests and print results"""
    # Setup test database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.create_tables_if_not_exist()

        repo = DocumentRepository(db)

        # Performance test: Create 100 documents
        print("🚀 Starting performance test...")
        start = time.time()
        docs = []
        for i in range(100):
            doc = DocumentModel(
                title=f'Perf Test Doc {i}',
                file_path=f'/test/doc_{i}.pdf',
                file_hash=f'hash_{i}',
                file_size=1024,
                page_count=10
            )
            docs.append(repo.create(doc))

        create_time = time.time() - start
        print(f'✅ CREATE Performance: {100/create_time:.1f} docs/sec')

        # Performance test: Read documents
        start = time.time()
        for doc in docs[:50]:
            repo.find_by_id(doc.id)
        read_time = time.time() - start
        print(f'✅ READ Performance: {50/read_time:.1f} docs/sec')

        # Cleanup
        db.close_all_connections()

    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

    return True


if __name__ == "__main__":
    success = run_performance_test()
    sys.exit(0 if success else 1)
