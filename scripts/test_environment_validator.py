#!/usr/bin/env python3
"""
Test Environment Validator for AI Enhanced PDF Scholar

Comprehensive validation script that checks all test environment dependencies,
database migration system, mock framework, and overall testing infrastructure.

Usage:
    python scripts/test_environment_validator.py
"""

import importlib
import logging
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class TestEnvironmentValidator:
    """Comprehensive test environment validator."""

    def __init__(self):
        self.results = {
            "python_environment": {"status": "unknown", "details": {}},
            "test_dependencies": {"status": "unknown", "details": {}},
            "database_system": {"status": "unknown", "details": {}},
            "mock_framework": {"status": "unknown", "details": {}},
            "migration_system": {"status": "unknown", "details": {}},
            "import_system": {"status": "unknown", "details": {}},
        }
        self.overall_health = 0
        self.issues = []

    def validate_all(self) -> dict[str, Any]:
        """Run all validation checks."""
        print("🔍 AI Enhanced PDF Scholar - Test Environment Validator")
        print("=" * 60)

        try:
            self._validate_python_environment()
            self._validate_test_dependencies()
            self._validate_import_system()
            self._validate_database_system()
            self._validate_migration_system()
            self._validate_mock_framework()

            self._calculate_overall_health()
            self._print_summary()

            return {
                "overall_health": self.overall_health,
                "results": self.results,
                "issues": self.issues,
                "ready_for_testing": self.overall_health >= 95,
            }

        except Exception as e:
            print(f"❌ Validation failed with error: {e}")
            traceback.print_exc()
            return {
                "overall_health": 0,
                "results": self.results,
                "issues": [f"Critical validation error: {e}"],
                "ready_for_testing": False,
            }

    def _validate_python_environment(self):
        """Validate Python environment and version."""
        print("🐍 Checking Python environment...")

        try:
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

            # Check minimum Python version (3.8+)
            if sys.version_info < (3, 8):
                self.results["python_environment"]["status"] = "error"
                self.results["python_environment"]["details"] = {
                    "version": python_version,
                    "error": "Python 3.8+ required",
                }
                self.issues.append(
                    f"Python version {python_version} too old (3.8+ required)"
                )
                print(f"❌ Python version: {python_version} (too old)")
                return

            # Check virtual environment
            in_venv = hasattr(sys, "real_prefix") or (
                hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
            )

            self.results["python_environment"]["status"] = "ok"
            self.results["python_environment"]["details"] = {
                "version": python_version,
                "in_virtual_env": in_venv,
                "executable": sys.executable,
                "platform": sys.platform,
            }

            print(f"✅ Python version: {python_version}")
            print(f"✅ Virtual environment: {'Yes' if in_venv else 'No'}")

        except Exception as e:
            self.results["python_environment"]["status"] = "error"
            self.results["python_environment"]["details"] = {"error": str(e)}
            self.issues.append(f"Python environment check failed: {e}")
            print(f"❌ Python environment check failed: {e}")

    def _validate_test_dependencies(self):
        """Validate test framework dependencies."""
        print("\n📦 Checking test dependencies...")

        required_packages = [
            ("pytest", "pytest"),
            ("httpx", "httpx"),
            ("prometheus_client", "prometheus_client"),
            ("unittest.mock", None),  # Standard library
        ]

        missing_packages = []
        installed_packages = {}

        for package_name, import_name in required_packages:
            try:
                if import_name:
                    module = importlib.import_module(import_name)
                    version = getattr(module, "__version__", "unknown")
                else:
                    # For standard library modules
                    importlib.import_module(package_name)
                    version = "stdlib"

                installed_packages[package_name] = version
                print(f"✅ {package_name}: {version}")

            except ImportError:
                missing_packages.append(package_name)
                print(f"❌ {package_name}: Not installed")

        if missing_packages:
            self.results["test_dependencies"]["status"] = "error"
            self.results["test_dependencies"]["details"] = {
                "missing": missing_packages,
                "installed": installed_packages,
            }
            self.issues.append(f"Missing test dependencies: {missing_packages}")
        else:
            self.results["test_dependencies"]["status"] = "ok"
            self.results["test_dependencies"]["details"] = {
                "installed": installed_packages
            }

    def _validate_import_system(self):
        """Validate project import system."""
        print("\n🔗 Checking import system...")

        critical_imports = [
            "src.database.connection",
            "src.database.migrations.manager",
            "src.database.migrations.runner",
            "src.database.migrations.base",
        ]

        import_status = {}
        failed_imports = []

        for module_name in critical_imports:
            try:
                importlib.import_module(module_name)
                import_status[module_name] = "ok"
                print(f"✅ {module_name}")
            except Exception as e:
                import_status[module_name] = f"error: {e}"
                failed_imports.append(module_name)
                print(f"❌ {module_name}: {e}")

        if failed_imports:
            self.results["import_system"]["status"] = "error"
            self.results["import_system"]["details"] = {
                "failed": failed_imports,
                "status": import_status,
            }
            self.issues.append(f"Failed imports: {failed_imports}")
        else:
            self.results["import_system"]["status"] = "ok"
            self.results["import_system"]["details"] = {"status": import_status}

    def _validate_database_system(self):
        """Validate database connection and basic operations."""
        print("\n🗄️  Checking database system...")

        try:
            from src.database.connection import DatabaseConnection

            # Test with temporary database
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
                temp_path = temp_db.name

            try:
                # Test database connection
                db = DatabaseConnection(temp_path)

                # Test basic operations
                db.execute(
                    "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
                )
                db.execute("INSERT INTO test_table (name) VALUES (?)", ("test",))
                result = db.fetch_one(
                    "SELECT name FROM test_table WHERE name = ?", ("test",)
                )

                if result and result["name"] == "test":
                    print("✅ Database connection: Working")
                    print("✅ Basic operations: Working")

                    self.results["database_system"]["status"] = "ok"
                    self.results["database_system"]["details"] = {
                        "connection": "ok",
                        "basic_operations": "ok",
                        "temp_db_path": temp_path,
                    }
                else:
                    raise Exception("Database query failed")

                # Cleanup
                db.close_all_connections()

            finally:
                # Clean up temp file
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except:
                    pass

        except Exception as e:
            self.results["database_system"]["status"] = "error"
            self.results["database_system"]["details"] = {"error": str(e)}
            self.issues.append(f"Database system error: {e}")
            print(f"❌ Database system: {e}")

    def _validate_migration_system(self):
        """Validate database migration system."""
        print("\n🔄 Checking migration system...")

        try:
            from src.database.connection import DatabaseConnection
            from src.database.migrations.manager import MigrationManager
            from src.database.migrations.runner import MigrationRunner

            # Test with temporary database
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
                temp_path = temp_db.name

            try:
                db = DatabaseConnection(temp_path)

                # Test migration discovery
                migration_manager = MigrationManager(db)
                available_versions = migration_manager.get_available_versions()

                if len(available_versions) < 7:
                    raise Exception(
                        f"Expected 7+ migrations, found {len(available_versions)}"
                    )

                print(
                    f"✅ Migration discovery: {len(available_versions)} migrations found"
                )

                # Test migration execution
                migration_runner = MigrationRunner(migration_manager)
                result = migration_runner.migrate_to_latest()

                if not result.get("success", False):
                    raise Exception(
                        f"Migration failed: {result.get('error', 'Unknown error')}"
                    )

                print("✅ Migration execution: Working")

                # Test schema validation
                schema_validation = migration_runner.validate_schema()
                if not schema_validation.get("valid", False):
                    print(
                        f"⚠️  Schema validation issues: {schema_validation.get('issues', [])}"
                    )
                else:
                    print("✅ Schema validation: Passed")

                self.results["migration_system"]["status"] = "ok"
                self.results["migration_system"]["details"] = {
                    "migrations_found": len(available_versions),
                    "execution": "ok",
                    "validation": schema_validation.get("valid", False),
                }

                # Cleanup
                db.close_all_connections()

            finally:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except:
                    pass

        except Exception as e:
            self.results["migration_system"]["status"] = "error"
            self.results["migration_system"]["details"] = {"error": str(e)}
            self.issues.append(f"Migration system error: {e}")
            print(f"❌ Migration system: {e}")

    def _validate_mock_framework(self):
        """Validate mock framework configuration."""
        print("\n🎭 Checking mock framework...")

        try:
            from unittest.mock import Mock

            from tests.test_utils import MockFactory

            # Test basic mock creation
            mock = Mock()
            mock.test_method = Mock(return_value="test_response")
            result = mock.test_method("test_input")

            if result != "test_response":
                raise Exception("Basic mock functionality failed")

            mock.test_method.assert_called_once_with("test_input")
            print("✅ Basic mock functionality: Working")

            # Test MockFactory
            llama_mock = MockFactory.create_mock_llama_index()
            llama_mock.query.return_value.response = "mock_response"

            response = llama_mock.query("test")
            if response.response != "mock_response":
                raise Exception("MockFactory functionality failed")

            print("✅ MockFactory: Working")

            # Test document mock
            doc_data = MockFactory.create_mock_document_data()
            if not isinstance(doc_data, dict) or "title" not in doc_data:
                raise Exception("Document mock creation failed")

            print("✅ Document mocks: Working")

            self.results["mock_framework"]["status"] = "ok"
            self.results["mock_framework"]["details"] = {
                "basic_mocks": "ok",
                "mock_factory": "ok",
                "document_mocks": "ok",
            }

        except Exception as e:
            self.results["mock_framework"]["status"] = "error"
            self.results["mock_framework"]["details"] = {"error": str(e)}
            self.issues.append(f"Mock framework error: {e}")
            print(f"❌ Mock framework: {e}")

    def _calculate_overall_health(self):
        """Calculate overall health percentage."""
        total_checks = len(self.results)
        passed_checks = sum(
            1 for result in self.results.values() if result["status"] == "ok"
        )

        self.overall_health = int((passed_checks / total_checks) * 100)

    def _print_summary(self):
        """Print comprehensive summary."""
        print("\n" + "=" * 60)
        print("📊 TEST ENVIRONMENT HEALTH REPORT")
        print("=" * 60)

        for check_name, result in self.results.items():
            status_icon = "✅" if result["status"] == "ok" else "❌"
            check_display = check_name.replace("_", " ").title()
            print(f"{status_icon} {check_display}: {result['status'].upper()}")

        print(f"\n📊 Overall Health: {self.overall_health}%")

        if self.issues:
            print("\n⚠️  Issues Found:")
            for issue in self.issues:
                print(f"  • {issue}")

        if self.overall_health >= 95:
            print("\n🎉 Test environment is ready for testing!")
        elif self.overall_health >= 80:
            print("\n⚠️  Test environment has minor issues but should work")
        else:
            print("\n🚨 Test environment has critical issues that need attention")

        print("\n" + "=" * 60)


def main():
    """Main entry point."""
    validator = TestEnvironmentValidator()
    results = validator.validate_all()

    # Exit with appropriate code
    exit_code = 0 if results["ready_for_testing"] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
