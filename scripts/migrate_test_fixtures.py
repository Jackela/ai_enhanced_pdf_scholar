#!/usr/bin/env python3
"""
Test Infrastructure Migration Script
Helps migrate existing tests to use the optimized infrastructure.
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple


class TestMigrationHelper:
    """Helper for migrating existing tests to optimized infrastructure."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / "tests"
        
        # Common patterns to replace
        self.fixture_migrations = {
            # Database fixtures
            r'@pytest\.fixture\s*\ndef db_connection.*?yield db.*?db\.close.*?connection.*?\n': 
                'def db_connection(request):\n    """Use optimized database fixture."""\n    from tests.test_utils import db_manager\n    test_name = request.node.name\n    db = db_manager.get_test_db(test_name)\n    db_manager.clean_test_db(test_name)\n    yield db\n',
                
            # Mock fixtures
            r'mock_.*=.*Mock\(\)':
                '# Use mock_factory from test_utils instead',
                
            # Temp directory fixtures  
            r'@pytest\.fixture\s*\ndef temp_.*?tempfile\..*?yield.*?\n':
                '# Use test_data_directory fixture instead\n',
        }
    
    def scan_test_files(self) -> List[Path]:
        """Scan for test files that might need migration."""
        test_files = list(self.test_dir.rglob("test_*.py"))
        conftest_files = list(self.test_dir.rglob("conftest.py"))
        
        files_to_migrate = []
        
        for file_path in test_files + conftest_files:
            try:
                content = file_path.read_text()
                
                # Check for patterns that suggest migration needed
                migration_indicators = [
                    'DatabaseConnection(',
                    'tempfile.NamedTemporaryFile',
                    'Mock()',
                    'MagicMock()',
                    '@pytest.fixture.*db',
                    'yield db'
                ]
                
                if any(indicator in content for indicator in migration_indicators):
                    files_to_migrate.append(file_path)
                    
            except Exception as e:
                print(f"Warning: Could not scan {file_path}: {e}")
        
        return files_to_migrate
    
    def suggest_migrations(self, file_path: Path) -> List[Dict]:
        """Suggest specific migrations for a file."""
        suggestions = []
        
        try:
            content = file_path.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                line_num = i + 1
                
                # Database fixture suggestions
                if 'DatabaseConnection(' in line and '@pytest.fixture' in content:
                    suggestions.append({
                        'line': line_num,
                        'type': 'database_fixture',
                        'current': line.strip(),
                        'suggestion': 'Use optimized db_connection fixture from test_utils',
                        'replacement': 'def test_func(db_connection):  # from conftest.py'
                    })
                
                # Mock suggestions
                if 'Mock()' in line or 'MagicMock()' in line:
                    suggestions.append({
                        'line': line_num,
                        'type': 'mock_fixture',
                        'current': line.strip(),
                        'suggestion': 'Use MockFactory from test_utils',
                        'replacement': 'mock_factory.create_mock_...()'
                    })
                
                # Tempfile suggestions
                if 'tempfile' in line and 'fixture' in content:
                    suggestions.append({
                        'line': line_num,
                        'type': 'temp_directory',
                        'current': line.strip(),
                        'suggestion': 'Use test_data_directory fixture',
                        'replacement': 'def test_func(test_data_directory):'
                    })
        
        except Exception as e:
            print(f"Warning: Could not analyze {file_path}: {e}")
        
        return suggestions
    
    def generate_migration_report(self) -> str:
        """Generate a migration report for the team."""
        files_to_migrate = self.scan_test_files()
        
        report_lines = [
            "# Test Infrastructure Migration Report",
            "",
            f"Found {len(files_to_migrate)} files that could benefit from optimization:",
            ""
        ]
        
        for file_path in files_to_migrate:
            rel_path = file_path.relative_to(self.project_root)
            suggestions = self.suggest_migrations(file_path)
            
            if suggestions:
                report_lines.extend([
                    f"## {rel_path}",
                    f"**{len(suggestions)} optimization opportunities**",
                    ""
                ])
                
                for suggestion in suggestions:
                    report_lines.extend([
                        f"**Line {suggestion['line']}** ({suggestion['type']}):",
                        f"```python",
                        f"# Current:",
                        f"{suggestion['current']}",
                        f"",
                        f"# Suggested:",
                        f"{suggestion['replacement']}",
                        f"```",
                        f"*{suggestion['suggestion']}*",
                        ""
                    ])
        
        # Add quick start guide
        report_lines.extend([
            "",
            "## Quick Migration Guide",
            "",
            "### 1. Update imports in test files:",
            "```python",
            "# Add to test file imports:",
            "from tests.test_utils import db_manager, mock_factory",
            "```",
            "",
            "### 2. Replace database fixtures:",
            "```python", 
            "# Old:",
            "@pytest.fixture",
            "def db_connection():",
            "    db = DatabaseConnection(':memory:')",
            "    # ... setup ...",
            "    yield db",
            "    db.close_connection()",
            "",
            "# New:",
            "def test_my_function(db_connection):  # Use fixture from conftest.py",
            "    # db_connection is already set up and cleaned",
            "    pass",
            "```",
            "",
            "### 3. Replace manual mocks:",
            "```python",
            "# Old:",
            "mock_service = Mock()",
            "mock_service.method.return_value = 'result'",
            "",
            "# New:",
            "def test_my_function(mock_factory):",
            "    mock_service = mock_factory.create_mock_embedding_service()",
            "    # Pre-configured with sensible defaults",
            "```",
            "",
            "### 4. Use performance fixtures:",
            "```python",
            "def test_performance_sensitive(performance_tracker):",
            "    with performance_tracker.measure('operation'):",
            "        # Code being measured",
            "        pass",
            "    # Automatically logged if slow",
            "```",
        ])
        
        return "\n".join(report_lines)
    
    def create_example_test_file(self) -> str:
        """Create an example test file showing optimized patterns."""
        example = '''"""
Example Test File Using Optimized Infrastructure
Shows best practices for using the optimized test utilities.
"""

import pytest
from tests.test_utils import MockFactory


class TestOptimizedExample:
    """Example test class using optimized fixtures."""
    
    def test_database_operations(self, db_connection, mock_document_data):
        """Example database test with optimized fixtures."""
        # db_connection: Fast, shared database with automatic cleanup
        # mock_document_data: Cached mock data
        
        # Insert test data
        db_connection.execute(
            "INSERT INTO documents (title, content_hash) VALUES (?, ?)",
            (mock_document_data["title"], mock_document_data["content_hash"])
        )
        
        # Query data
        result = db_connection.fetch_one(
            "SELECT * FROM documents WHERE title = ?",
            (mock_document_data["title"],)
        )
        
        assert result is not None
        assert result["title"] == mock_document_data["title"]
    
    def test_with_mocks(self, mock_llama_index):
        """Example test using cached mock fixtures."""
        # mock_llama_index is pre-configured and cached
        
        mock_llama_index.query.return_value.response = "Test response"
        
        # Your service code here
        # result = my_service.search("query")
        # assert result == "Test response"
        
        mock_llama_index.query.assert_called_once()
    
    def test_performance_tracking(self, performance_tracker):
        """Example of performance monitoring."""
        import time
        
        with performance_tracker.measure("test_operation"):
            # Simulate some work
            time.sleep(0.1)
        
        # If this takes >500ms, it will be automatically flagged
    
    @pytest.mark.integration
    def test_integration_example(self, db_connection, test_data_directory):
        """Example integration test with proper marking."""
        # test_data_directory: Session-scoped temp directory
        
        test_file = test_data_directory / "test.txt"
        test_file.write_text("test content")
        
        # Test file operations with database
        assert test_file.exists()
    
    @pytest.mark.slow
    def test_complex_operation(self, isolated_db):
        """Example of test requiring complete isolation."""
        # Use isolated_db when you need complete database isolation
        # (Most tests should use db_connection for better performance)
        
        # Complex test that might affect other tests
        pass


# Example of custom fixture extending optimized infrastructure
@pytest.fixture
def specialized_mock():
    """Example of creating specialized fixture on top of optimized base."""
    mock = MockFactory.create_mock_llama_index()
    
    # Add specialized configuration
    mock.specialized_method = lambda x: f"specialized_{x}"
    
    return mock
'''
        return example
    
    def save_migration_files(self):
        """Save migration report and example files."""
        # Save migration report
        report_file = self.project_root / "TEST_MIGRATION_REPORT.md"
        report_file.write_text(self.generate_migration_report())
        print(f"📋 Migration report saved to {report_file}")
        
        # Save example test file
        example_file = self.test_dir / "example_optimized_test.py"
        example_file.write_text(self.create_example_test_file())
        print(f"📝 Example test file saved to {example_file}")


def main():
    """Main migration helper script."""
    print("🔧 Test Infrastructure Migration Helper")
    print("=" * 40)
    
    migrator = TestMigrationHelper()
    
    # Scan for files that need migration
    files_to_migrate = migrator.scan_test_files()
    print(f"📊 Found {len(files_to_migrate)} files that could benefit from optimization")
    
    # Generate and save migration materials
    migrator.save_migration_files()
    
    print("\n✅ Migration materials created!")
    print("\nNext steps:")
    print("1. Review TEST_MIGRATION_REPORT.md for specific suggestions")
    print("2. Check tests/example_optimized_test.py for usage patterns")
    print("3. Start migrating tests one file at a time")
    print("4. Run 'python scripts/optimize_tests.py' to track progress")


if __name__ == "__main__":
    main()