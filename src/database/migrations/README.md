# Modular Database Migration System

This document provides a comprehensive guide to the modular database migration system that replaces the monolithic `migrations.py` file.

## Overview

The modular migration system provides:
- **Individual migration files** organized by version number
- **Comprehensive rollback support** for migrations that support it
- **Version tracking and audit trails** for all migration operations
- **Dependency management** to ensure migrations run in correct order
- **Safety checks and validation** to prevent data loss
- **Backward compatibility** with the existing system

## Architecture

### Core Components

```
src/database/migrations/
├── __init__.py           # Package initialization and registry
├── base.py              # BaseMigration class - common functionality
├── manager.py           # MigrationManager - discovery and validation
├── runner.py            # MigrationRunner - execution engine
├── version_tracker.py   # VersionTracker - version and audit tracking
└── versions/            # Individual migration files
    ├── __init__.py
    ├── 001_initial_schema.py
    ├── 002_add_content_hash.py
    ├── 003_add_citation_tables.py
    └── ...
```

### Migration Flow

1. **Discovery**: MigrationManager scans `versions/` directory for migration files
2. **Validation**: Checks migration sequence, dependencies, and integrity
3. **Planning**: Determines which migrations need to run
4. **Execution**: MigrationRunner applies migrations in correct order
5. **Tracking**: VersionTracker records success/failure and maintains audit trail

## Creating New Migrations

### 1. Migration File Naming

Migration files must follow this naming convention:
```
XXX_description.py
```

Where:
- `XXX` is a 3-digit zero-padded version number (e.g., `001`, `015`, `103`)
- `description` is a snake_case description of what the migration does

Examples:
- `008_add_user_preferences_table.py`
- `009_create_indexes_for_performance.py`
- `010_migrate_legacy_data_format.py`

### 2. Migration Class Structure

Each migration file must contain a class that inherits from `BaseMigration`:

```python
"""
Migration XXX: Brief Description

Detailed description of what this migration does,
why it's needed, and any important considerations.
"""

import logging
from typing import Any
from ..base import BaseMigration

logger = logging.getLogger(__name__)

class MyMigrationName(BaseMigration):
    \"\"\"
    Brief description of the migration.
    
    Detailed explanation of changes made.
    \"\"\"
    
    @property
    def version(self) -> int:
        return XXX  # Must match filename
        
    @property
    def description(self) -> str:
        return "Brief description of changes"
        
    @property
    def dependencies(self) -> list[int]:
        return [1, 5]  # List of required prior migrations
        
    @property
    def rollback_supported(self) -> bool:
        return True  # Set to False if rollback is not possible
        
    def up(self) -> None:
        \"\"\"Apply the migration (required).\"\"\"
        logger.info("Applying migration XXX")
        
        # Your migration code here
        self.execute_sql("CREATE TABLE new_table (id INTEGER PRIMARY KEY)")
        
        logger.info("Migration XXX completed")
        
    def down(self) -> None:
        \"\"\"Rollback the migration (optional).\"\"\"
        logger.info("Rolling back migration XXX")
        
        # Your rollback code here
        self.execute_sql("DROP TABLE IF EXISTS new_table")
        
        logger.info("Migration XXX rollback completed")
        
    def pre_migrate_checks(self) -> bool:
        \"\"\"Optional: Custom pre-migration validation.\"\"\"
        if not super().pre_migrate_checks():
            return False
            
        # Custom validation logic
        # Return False to skip migration, True to proceed
        return True
        
    def post_migrate_checks(self) -> bool:
        \"\"\"Optional: Custom post-migration validation.\"\"\"
        # Validate that migration worked correctly
        # Return False if validation fails
        return True
```

### 3. Helper Methods

The `BaseMigration` class provides several helper methods:

#### Database Operations
```python
# Execute SQL with error handling
self.execute_sql("CREATE TABLE ...", (param1, param2))

# Execute SQL from file
self.execute_sql_file("path/to/schema.sql")

# Create table if not exists
self.create_table_if_not_exists("table_name", "CREATE TABLE ...")

# Create index if not exists  
self.create_index_if_not_exists("index_name", "CREATE INDEX ...")
```

#### Version Management
```python
# Get current database version
current_version = self._get_current_version()

# Set database version (usually done automatically)
self._set_version(new_version)
```

## Migration Types and Examples

### 1. Schema Changes

**Adding a table:**
```python
def up(self):
    schema = """
    CREATE TABLE user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        preference_key VARCHAR(100) NOT NULL,
        preference_value TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """
    self.create_table_if_not_exists("user_preferences", schema)
    
    # Add indexes
    self.create_index_if_not_exists(
        "idx_user_preferences_user_id",
        "CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id)"
    )
```

**Adding a column:**
```python
def up(self):
    # Check if column exists first
    columns = self.db.fetch_all("PRAGMA table_info(documents)")
    column_names = [col["name"] for col in columns]
    
    if "new_column" not in column_names:
        self.execute_sql("ALTER TABLE documents ADD COLUMN new_column TEXT")
        logger.info("Added new_column to documents table")
```

### 2. Data Migrations

**Migrating data format:**
```python
def up(self):
    # Get all records that need migration
    records = self.db.fetch_all(
        "SELECT id, old_format_data FROM table_name WHERE migrated = 0"
    )
    
    for record in records:
        # Transform data
        new_data = transform_data(record["old_format_data"])
        
        # Update record
        self.execute_sql(
            "UPDATE table_name SET new_format_data = ?, migrated = 1 WHERE id = ?",
            (new_data, record["id"])
        )
    
    logger.info(f"Migrated {len(records)} records to new format")
```

### 3. Performance Optimizations

**Adding indexes:**
```python
def up(self):
    indexes = [
        ("idx_documents_created_desc", "CREATE INDEX idx_documents_created_desc ON documents(created_at DESC)"),
        ("idx_citations_author_year", "CREATE INDEX idx_citations_author_year ON citations(authors, publication_year)"),
    ]
    
    for index_name, index_sql in indexes:
        self.create_index_if_not_exists(index_name, index_sql)
```

## Best Practices

### 1. Migration Safety

- **Always test migrations on a copy of production data**
- **Write rollback methods for any migration that can be safely reversed**
- **Use transactions** - the migration system automatically wraps migrations in transactions
- **Check for existing state** before making changes
- **Validate results** in `post_migrate_checks()`

### 2. Performance Considerations

- **For large data migrations**, consider batching operations:
```python
def up(self):
    batch_size = 1000
    offset = 0
    
    while True:
        records = self.db.fetch_all(
            "SELECT * FROM large_table LIMIT ? OFFSET ?",
            (batch_size, offset)
        )
        
        if not records:
            break
            
        # Process batch
        for record in records:
            # ... process record
            pass
            
        offset += batch_size
        logger.info(f"Processed {offset} records")
```

### 3. Rollback Design

Not all migrations can be safely rolled back:

**Rollback-safe migrations:**
- Adding tables, columns, indexes
- Inserting reference data
- Most schema additions

**Rollback-unsafe migrations:**
- Dropping tables or columns (data loss)
- Data transformations that lose information
- Complex data migrations

**For unsafe rollbacks:**
```python
@property
def rollback_supported(self) -> bool:
    return False
    
def down(self) -> None:
    raise NotImplementedError(
        "This migration cannot be safely rolled back due to potential data loss"
    )
```

### 4. Dependencies

Specify dependencies when your migration requires other migrations:

```python
@property
def dependencies(self) -> list[int]:
    return [1, 3, 7]  # This migration requires migrations 1, 3, and 7
```

### 5. Error Handling

Use proper error handling and logging:

```python
def up(self):
    try:
        # Migration logic
        self.execute_sql("CREATE TABLE ...")
        logger.info("Table created successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        # Let the error bubble up - the framework will handle rollback
        raise
```

## Using the Migration System

### Command Line Usage

```python
from database.connection import DatabaseConnection
from database.modular_migrator import ModularDatabaseMigrator

# Initialize
db = DatabaseConnection("database.db")
migrator = ModularDatabaseMigrator(db)

# Check status
print(f"Current version: {migrator.get_current_version()}")
print(f"Needs migration: {migrator.needs_migration()}")

# Run migrations
if migrator.needs_migration():
    result = migrator.migrate()
    if result:
        print("Migration completed successfully")
    else:
        print("Migration failed")

# Get detailed plan
plan = migrator.get_migration_plan()
print(f"Migration plan: {plan}")
```

### Rollback Operations

```python
# Rollback to specific version
success = migrator.rollback_to_version(5)

# Check if rollback is possible
can_rollback, issues = migrator.manager.can_rollback_to(3)
if not can_rollback:
    print(f"Cannot rollback: {issues}")
```

### Migration History

```python
# Get migration history
history = migrator.get_migration_history()
for entry in history:
    print(f"{entry['version']}: {entry['description']} ({entry['operation']})")
```

## Testing Migrations

Always test migrations thoroughly:

```python
def test_my_migration():
    # Create test database
    db = DatabaseConnection(":memory:")
    
    # Apply base migrations
    migrator = ModularDatabaseMigrator(db)
    migrator.migrate_to_version(5)  # Apply prerequisites
    
    # Test your migration
    migration = MyMigration(db)
    assert migration.run() == True
    
    # Validate results
    tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
    assert "new_table" in [t["name"] for t in tables]
    
    # Test rollback if supported
    if migration.rollback_supported:
        assert migration.rollback() == True
        # Validate rollback worked
```

## Troubleshooting

### Common Issues

**Migration not discovered:**
- Check filename follows `XXX_description.py` format
- Ensure migration class inherits from `BaseMigration`
- Verify `version` property matches filename number

**Version mismatch error:**
- Ensure `version` property in class matches filename
- Check for duplicate version numbers

**Dependency errors:**
- Verify all dependency migrations exist
- Check dependency version numbers are correct
- Ensure dependencies don't create circular references

**Rollback failures:**
- Check if migration supports rollback
- Verify rollback logic is correct
- Consider if rollback is safe for your use case

### Debugging

Enable debug logging to see detailed migration execution:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check migration system status:

```python
status = migrator.manager.get_migration_status()
print(f"Status: {status}")

# Validate migration sequence
issues = migrator.manager.validate_migration_sequence()
if issues:
    print(f"Validation issues: {issues}")
```

## Backward Compatibility

The modular system maintains full backward compatibility with the original `DatabaseMigrator` class. Existing code will continue to work without changes:

```python
# This works exactly the same as before
from database.migrations import DatabaseMigrator  # Actually ModularDatabaseMigrator
from database.connection import DatabaseConnection

db = DatabaseConnection("database.db")
migrator = DatabaseMigrator(db)  # Uses modular system internally

# All original methods work the same
migrator.get_current_version()
migrator.migrate()
migrator.get_schema_info()
```

## Migration from Monolithic System

The modular system automatically handles migration from the existing monolithic system:

1. **Version compatibility**: Maintains PRAGMA user_version for backward compatibility
2. **Audit trail**: Existing migrations are tracked in the new version system
3. **Seamless transition**: No manual intervention required for existing databases

## Performance and Monitoring

### Migration Performance

- Migrations are wrapped in transactions for safety
- Large migrations can be batched to reduce memory usage
- Execution time is tracked and logged
- Performance statistics are available via `get_performance_statistics()`

### Monitoring

```python
# Get comprehensive status
status = migrator.manager.get_migration_status()

# Get performance metrics
stats = migrator.get_performance_statistics()

# Get migration history with timing
history = migrator.get_migration_history()
```

This modular migration system provides a robust, maintainable, and safe way to manage database schema evolution while maintaining full backward compatibility with existing code.