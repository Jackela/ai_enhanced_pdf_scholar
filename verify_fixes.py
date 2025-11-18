from typing import Any

#!/usr/bin/env python3
"""
Verify the core fixes applied to the UAT issues.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def verify_fixes() -> Any:
    """Verify all fixes have been applied."""
    print("=" * 60)
    print("VERIFYING UAT FIXES")
    print("=" * 60)

    issues_fixed = []
    issues_remaining = []

    # 1. Check DocumentService has create_document method
    print("\n1. Checking DocumentService.create_document...")
    try:
        from src.database.connection import DatabaseConnection
        from src.services.document_service import DocumentService

        db = DatabaseConnection(":memory:")
        service = DocumentService(db)

        if hasattr(service, 'create_document'):
            print("   ✅ DocumentService has create_document method")
            issues_fixed.append("DocumentService.create_document")
        else:
            print("   ❌ DocumentService missing create_document method")
            issues_remaining.append("DocumentService.create_document")
    except Exception as e:
        print(f"   ❌ Error checking DocumentService: {e}")
        issues_remaining.append("DocumentService check failed")

    # 2. Check multi_document_indexes table creation
    print("\n2. Checking multi_document_indexes table creation...")
    try:
        from src.database.connection import DatabaseConnection
        from src.repositories.multi_document_repositories import (
            MultiDocumentIndexRepository,
        )

        db = DatabaseConnection(":memory:")
        repo = MultiDocumentIndexRepository(db)

        # Check if table was created
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='multi_document_indexes'")
            if cursor.fetchone():
                print("   ✅ multi_document_indexes table is created automatically")
                issues_fixed.append("multi_document_indexes table")
            else:
                print("   ❌ multi_document_indexes table not created")
                issues_remaining.append("multi_document_indexes table")
    except Exception as e:
        print(f"   ❌ Error checking table creation: {e}")
        issues_remaining.append("Table creation check failed")

    # 3. Check API server startup script forces uvicorn on Windows
    print("\n3. Checking server startup forces uvicorn on Windows...")
    start_script = project_root / "start_api_server.py"
    if start_script.exists():
        with open(start_script) as f:
            content = f.read()

        if 'sys.platform == "win32" or "--uvicorn"' in content:
            print("   ✅ Server startup forces uvicorn on Windows")
            issues_fixed.append("Windows uvicorn forcing")
        else:
            print("   ⚠️  Server startup may not force uvicorn on Windows")
            issues_remaining.append("Windows uvicorn forcing")
    else:
        print("   ❌ start_api_server.py not found")
        issues_remaining.append("start_api_server.py missing")

    # 4. Check health endpoints exist
    print("\n4. Checking health endpoints...")
    try:
        # Check main.py
        main_path = project_root / "backend" / "api" / "main.py"
        if main_path.exists():
            with open(main_path) as f:
                content = f.read()

            endpoints_found = []
            if '@app.get("/ping")' in content:
                endpoints_found.append("/ping")
            if '@app.get("/health")' in content:
                endpoints_found.append("/health")

            if endpoints_found:
                print(f"   ✅ Health endpoints found: {', '.join(endpoints_found)}")
                issues_fixed.append("Health endpoints")
            else:
                print("   ⚠️  Some health endpoints may be missing")

        # Check main_simple.py
        simple_path = project_root / "backend" / "api" / "main_simple.py"
        if simple_path.exists():
            with open(simple_path) as f:
                content = f.read()

            if '@app.get("/ping")' in content and '@app.get("/health")' in content:
                print("   ✅ Simple server has health endpoints")
                issues_fixed.append("Simple server health endpoints")
            else:
                print("   ⚠️  Simple server missing some health endpoints")
                issues_remaining.append("Simple server health endpoints")
    except Exception as e:
        print(f"   ❌ Error checking health endpoints: {e}")
        issues_remaining.append("Health endpoint check failed")

    # 5. Check simple server startup script exists
    print("\n5. Checking simplified server startup...")
    simple_start = project_root / "start_api_server_simple.py"
    if simple_start.exists():
        print("   ✅ Simplified server startup script exists")
        issues_fixed.append("Simplified server startup")
    else:
        print("   ❌ start_api_server_simple.py not found")
        issues_remaining.append("Simplified server startup")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n✅ Issues Fixed ({len(issues_fixed)}):")
    for issue in issues_fixed:
        print(f"   - {issue}")

    if issues_remaining:
        print(f"\n❌ Issues Remaining ({len(issues_remaining)}):")
        for issue in issues_remaining:
            print(f"   - {issue}")
    else:
        print("\n🎉 All identified issues have been fixed!")

    print("\n" + "=" * 60)

    return len(issues_remaining) == 0


if __name__ == "__main__":
    success = verify_fixes()
    sys.exit(0 if success else 1)
