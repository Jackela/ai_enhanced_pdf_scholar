"""
Comprehensive Test Suite for Modular Migration System

Tests all components of the modular migration system including:
- Base migration functionality
- Version tracking
- Migration manager
- Migration runner
- Backward compatibility
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add the source directory to the Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from database.connection import DatabaseConnection
from database.migrations.base import BaseMigration, MigrationError
from database.migrations.version_tracker import VersionTracker
from database.migrations.manager import MigrationManager
from database.migrations.runner import MigrationRunner
from database.modular_migrator import ModularDatabaseMigrator


class TestBaseMigration:
    """Test base migration functionality."""
    
    @pytest.fixture
    def db_connection(self):
        """Create a temporary database connection for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
            
        conn = DatabaseConnection(db_path)
        yield conn
        conn.close_all_connections()
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
            
    @pytest.fixture
    def test_migration_class(self):
        """Create a test migration class."""
        class TestMigration(BaseMigration):
            @property
            def version(self):
                return 1
                
            @property
            def description(self):
                return "Test migration"
                
            @property
            def rollback_supported(self):
                return True
                
            def up(self):
                self.execute_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
                
            def down(self):
                self.execute_sql("DROP TABLE IF EXISTS test_table")
                
        return TestMigration
        
    def test_migration_basic_functionality(self, db_connection, test_migration_class):
        """Test basic migration functionality."""
        migration = test_migration_class(db_connection)
        
        # Test properties
        assert migration.version == 1
        assert migration.description == "Test migration"
        assert migration.rollback_supported == True
        
        # Test migration execution
        assert migration.run() == True
        
        # Verify table was created
        tables = db_connection.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(tables) == 1
        
    def test_migration_rollback(self, db_connection, test_migration_class):
        """Test migration rollback functionality."""
        migration = test_migration_class(db_connection)
        
        # Apply migration
        migration.run()
        
        # Verify table exists
        tables = db_connection.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(tables) == 1
        
        # Rollback migration
        assert migration.rollback() == True
        
        # Verify table was dropped
        tables = db_connection.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(tables) == 0
        
    def test_migration_error_handling(self, db_connection):
        """Test migration error handling."""
        class FailingMigration(BaseMigration):
            @property
            def version(self):
                return 1
                
            @property
            def description(self):
                return "Failing migration"
                
            def up(self):
                raise Exception("Intentional test failure")
                
        migration = FailingMigration(db_connection)
        
        with pytest.raises(MigrationError):
            migration.run()


class TestVersionTracker:
    """Test version tracking functionality."""
    
    @pytest.fixture
    def db_connection(self):
        """Create a temporary database connection for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
            
        conn = DatabaseConnection(db_path)
        yield conn
        conn.close_all_connections()
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
            
    @pytest.fixture
    def version_tracker(self, db_connection):
        """Create a version tracker instance."""
        return VersionTracker(db_connection)
        
    def test_version_tracker_initialization(self, version_tracker):
        """Test version tracker initialization."""
        # Should create version tracking tables
        tables = version_tracker.db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('migration_versions', 'migration_history')"
        )
        assert len(tables) == 2
        
    def test_current_version_tracking(self, version_tracker):
        """Test current version tracking."""
        # Initially should be 0
        assert version_tracker.get_current_version() == 0
        
        # Set version
        version_tracker.set_version(5)
        assert version_tracker.get_current_version() == 5
        
    def test_migration_recording(self, version_tracker):
        """Test migration application recording."""
        # Record migration
        version_tracker.record_migration_applied(
            version=1,
            description="Test migration",
            execution_time_ms=100.5,
            rollback_supported=True
        )
        
        # Check if recorded
        assert version_tracker.is_migration_applied(1) == True
        assert version_tracker.is_migration_applied(2) == False
        
        # Check applied versions
        applied = version_tracker.get_applied_versions()
        assert applied == [1]
        
    def test_migration_history(self, version_tracker):
        """Test migration history tracking."""
        # Record a migration
        version_tracker.record_migration_applied(
            version=1,
            description="Test migration",
            execution_time_ms=100.5
        )
        
        # Get history
        history = version_tracker.get_migration_history()
        assert len(history) == 1
        assert history[0]["version"] == 1
        assert history[0]["operation"] == "apply"
        
    def test_version_consistency_validation(self, version_tracker):
        """Test version consistency validation."""
        result = version_tracker.validate_consistency()
        assert result["consistent"] == True
        assert len(result["issues"]) == 0


class TestMigrationManager:
    """Test migration manager functionality."""
    
    @pytest.fixture
    def db_connection(self):
        """Create a temporary database connection for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
            
        conn = DatabaseConnection(db_path)
        yield conn
        conn.close_all_connections()
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
            
    @pytest.fixture
    def temp_migrations_dir(self):
        """Create a temporary migrations directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            migrations_dir = Path(temp_dir) / "migrations"
            migrations_dir.mkdir()
            
            # Create a test migration file
            migration_file = migrations_dir / "001_test_migration.py"
            migration_content = '''
from database.migrations.base import BaseMigration

class TestMigration(BaseMigration):
    @property
    def version(self):
        return 1
        
    @property
    def description(self):
        return "Test migration"
        
    def up(self):
        self.execute_sql("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
'''
            migration_file.write_text(migration_content)
            
            yield str(migrations_dir)
            
    def test_migration_manager_initialization(self, db_connection):
        """Test migration manager initialization."""
        manager = MigrationManager(db_connection)
        assert manager.db == db_connection
        assert manager.version_tracker is not None
        
    def test_migration_discovery(self, db_connection, temp_migrations_dir):
        """Test migration discovery functionality."""
        manager = MigrationManager(db_connection, temp_migrations_dir)
        
        # Discover migrations
        manager.discover_migrations()
        
        # Should find the test migration
        versions = manager.get_available_versions()
        assert 1 in versions
        
    def test_migration_validation(self, db_connection):
        """Test migration sequence validation."""
        manager = MigrationManager(db_connection)
        
        # Empty system should have issues
        issues = manager.validate_migration_sequence()
        assert "No migrations available" in issues[0]
        
    def test_migration_status(self, db_connection):
        """Test migration status reporting."""
        manager = MigrationManager(db_connection)
        status = manager.get_migration_status()
        
        assert "current_version" in status
        assert "target_version" in status
        assert "needs_migration" in status


class TestMigrationRunner:
    """Test migration runner functionality."""
    
    @pytest.fixture
    def db_connection(self):
        """Create a temporary database connection for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
            
        conn = DatabaseConnection(db_path)
        yield conn
        conn.close_all_connections()
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
            
    @pytest.fixture
    def migration_runner(self, db_connection):
        """Create a migration runner instance."""
        manager = MigrationManager(db_connection)
        return MigrationRunner(manager)
        
    def test_migration_runner_initialization(self, migration_runner):
        """Test migration runner initialization."""
        assert migration_runner.manager is not None
        assert migration_runner.version_tracker is not None
        
    def test_schema_validation(self, migration_runner):
        """Test schema validation."""
        result = migration_runner.validate_schema()
        
        assert "valid" in result
        assert "current_version" in result
        assert "issues" in result
        
    def test_migration_plan_summary(self, migration_runner):
        """Test migration plan summary generation."""
        summary = migration_runner.get_migration_plan_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestModularDatabaseMigrator:
    """Test the backward-compatible modular database migrator."""
    
    @pytest.fixture
    def db_connection(self):
        """Create a temporary database connection for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
            
        conn = DatabaseConnection(db_path)
        yield conn
        conn.close_all_connections()
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
            
    @pytest.fixture
    def modular_migrator(self, db_connection):
        """Create a modular database migrator instance."""
        return ModularDatabaseMigrator(db_connection)
        
    def test_modular_migrator_initialization(self, modular_migrator):
        """Test modular migrator initialization."""
        assert modular_migrator.db is not None
        assert modular_migrator.manager is not None
        assert modular_migrator.runner is not None
        assert modular_migrator.version_tracker is not None
        
    def test_version_management(self, modular_migrator):
        """Test version management functionality."""
        # Initially should be 0
        assert modular_migrator.get_current_version() == 0
        
        # Set version
        modular_migrator.set_version(3)
        assert modular_migrator.get_current_version() == 3
        
    def test_migration_need_detection(self, modular_migrator):
        """Test migration need detection."""
        # With no migrations available, should not need migration
        needs_migration = modular_migrator.needs_migration()
        assert isinstance(needs_migration, bool)
        
    def test_schema_info_generation(self, modular_migrator):
        """Test schema information generation."""
        schema_info = modular_migrator.get_schema_info()
        
        assert "current_version" in schema_info
        assert "target_version" in schema_info
        assert "needs_migration" in schema_info
        assert "tables" in schema_info
        
    def test_performance_statistics(self, modular_migrator):
        """Test performance statistics generation."""
        stats = modular_migrator.get_performance_statistics()
        
        assert "migration_system" in stats
        assert "database_info" in stats
        assert "table_statistics" in stats
        
    def test_database_optimization(self, modular_migrator):
        """Test database optimization functionality."""
        result = modular_migrator.optimize_database_performance()
        
        assert "success" in result
        assert "operations_performed" in result
        
    def test_validation_functionality(self, modular_migrator):
        """Test schema validation functionality."""
        # Should be able to validate without errors
        is_valid = modular_migrator.validate_schema()
        assert isinstance(is_valid, bool)


class TestIntegration:
    """Integration tests for the complete migration system."""
    
    @pytest.fixture
    def db_connection(self):
        """Create a temporary database connection for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
            
        conn = DatabaseConnection(db_path)
        yield conn
        conn.close_all_connections()
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
            
    def test_full_migration_workflow(self, db_connection):
        """Test complete migration workflow."""
        # Initialize migrator
        migrator = ModularDatabaseMigrator(db_connection)
        
        # Check initial state
        assert migrator.get_current_version() == 0
        
        # Get migration plan
        plan = migrator.get_migration_plan()
        assert "current_version" in plan
        assert "target_version" in plan
        
        # Get schema info
        schema_info = migrator.get_schema_info()
        assert "current_version" in schema_info
        
        # Validate schema
        is_valid = migrator.validate_schema()
        assert isinstance(is_valid, bool)
        
        # Get performance stats
        stats = migrator.get_performance_statistics()
        assert "migration_system" in stats
        
    def test_backward_compatibility(self, db_connection):
        """Test that the modular system maintains backward compatibility."""
        # The modular migrator should provide all the same methods as the original
        migrator = ModularDatabaseMigrator(db_connection)
        
        # Test all the original DatabaseMigrator methods
        assert hasattr(migrator, 'get_current_version')
        assert hasattr(migrator, 'set_version')
        assert hasattr(migrator, 'needs_migration')
        assert hasattr(migrator, 'migrate')
        assert hasattr(migrator, 'create_tables_if_not_exist')
        assert hasattr(migrator, 'get_schema_info')
        assert hasattr(migrator, 'validate_schema')
        assert hasattr(migrator, 'get_performance_statistics')
        assert hasattr(migrator, 'optimize_database_performance')
        
        # Test that all methods return appropriate types
        assert isinstance(migrator.get_current_version(), int)
        assert isinstance(migrator.needs_migration(), bool)
        assert isinstance(migrator.get_schema_info(), dict)
        assert isinstance(migrator.validate_schema(), bool)
        assert isinstance(migrator.get_performance_statistics(), dict)
        assert isinstance(migrator.optimize_database_performance(), dict)


if __name__ == "__main__":
    pytest.main([__file__])