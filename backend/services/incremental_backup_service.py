"""
Enterprise Incremental Backup Service
Efficient incremental backups with delta tracking and change detection.
Supports database, file system, and vector index incremental backups.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Union

import aiofiles
from sqlalchemy import create_engine, text

from backend.core.secrets import get_secrets_manager
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of changes for incremental backup."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


class BackupLevel(str, Enum):
    """Incremental backup levels."""

    FULL = "full"  # Complete backup
    DIFFERENTIAL = "diff"  # Changes since last full
    INCREMENTAL = "inc"  # Changes since last backup
    LOG = "log"  # Transaction log only


@dataclass
class ChangeRecord:
    """Record of a detected change."""

    path: str
    change_type: ChangeType
    timestamp: datetime
    size: int = 0
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncrementalSnapshot:
    """Snapshot of incremental backup state."""

    snapshot_id: str
    source_id: str
    backup_level: BackupLevel
    created_at: datetime
    files_tracked: int
    total_size: int
    checksum_map: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class FileSystemTracker:
    """Tracks file system changes for incremental backup."""

    def __init__(
        self, base_path: str, exclude_patterns: list[str] | None = None
    ) -> None:
        """Initialize file system tracker."""
        self.base_path = Path(base_path)
        self.exclude_patterns = exclude_patterns or []
        self.snapshot_file = (
            self.base_path.parent / f".{self.base_path.name}_snapshot.json"
        )
        self.last_snapshot: IncrementalSnapshot | None = None

    async def create_snapshot(self, snapshot_id: str) -> IncrementalSnapshot:
        """Create a snapshot of the current file system state."""
        start_time = time.time()
        files_tracked = 0
        total_size = 0
        checksum_map = {}

        if not self.base_path.exists():
            raise FileNotFoundError(f"Base path does not exist: {self.base_path}")

        for file_path in self._scan_files():
            try:
                stat_info = file_path.stat()
                file_size = stat_info.st_size
                files_tracked += 1
                total_size += file_size

                # Calculate checksum for small files only for performance
                if file_size < 1024 * 1024:  # 1MB threshold
                    checksum = await self._calculate_checksum(file_path)
                else:
                    # For large files, use mtime + size as quick hash
                    checksum = hashlib.sha256(
                        f"{stat_info.st_mtime}:{file_size}".encode()
                    ).hexdigest()[:16]

                relative_path = str(file_path.relative_to(self.base_path))
                checksum_map[relative_path] = checksum

            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot access file {file_path}: {e}")
                continue

        snapshot = IncrementalSnapshot(
            snapshot_id=snapshot_id,
            source_id=str(self.base_path),
            backup_level=BackupLevel.FULL,
            created_at=datetime.utcnow(),
            files_tracked=files_tracked,
            total_size=total_size,
            checksum_map=checksum_map,
            metadata={
                "scan_duration": time.time() - start_time,
                "exclude_patterns": self.exclude_patterns,
            },
        )

        # Save snapshot to disk
        await self._save_snapshot(snapshot)
        self.last_snapshot = snapshot

        logger.info(
            f"Created filesystem snapshot: {files_tracked} files, {total_size} bytes"
        )
        return snapshot

    async def detect_changes(
        self, since_snapshot_id: str | None = None
    ) -> list[ChangeRecord]:
        """Detect changes since the specified snapshot."""
        if not self.last_snapshot and self.snapshot_file.exists():
            await self._load_snapshot()

        if not self.last_snapshot:
            logger.warning("No previous snapshot found, performing full scan")
            return []

        changes = []
        current_files = {}

        # Scan current state
        for file_path in self._scan_files():
            try:
                stat_info = file_path.stat()
                relative_path = str(file_path.relative_to(self.base_path))

                # Calculate checksum
                if stat_info.st_size < 1024 * 1024:
                    checksum = await self._calculate_checksum(file_path)
                else:
                    checksum = hashlib.sha256(
                        f"{stat_info.st_mtime}:{stat_info.st_size}".encode()
                    ).hexdigest()[:16]

                current_files[relative_path] = {
                    "checksum": checksum,
                    "size": stat_info.st_size,
                    "mtime": stat_info.st_mtime,
                }

                # Check for changes
                if relative_path not in self.last_snapshot.checksum_map:
                    # New file
                    changes.append(
                        ChangeRecord(
                            path=relative_path,
                            change_type=ChangeType.CREATED,
                            timestamp=datetime.fromtimestamp(stat_info.st_mtime),
                            size=stat_info.st_size,
                            checksum=checksum,
                        )
                    )
                elif self.last_snapshot.checksum_map[relative_path] != checksum:
                    # Modified file
                    changes.append(
                        ChangeRecord(
                            path=relative_path,
                            change_type=ChangeType.MODIFIED,
                            timestamp=datetime.fromtimestamp(stat_info.st_mtime),
                            size=stat_info.st_size,
                            checksum=checksum,
                        )
                    )

            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot access file {file_path}: {e}")
                continue

        # Check for deleted files
        for relative_path in self.last_snapshot.checksum_map:
            if relative_path not in current_files:
                changes.append(
                    ChangeRecord(
                        path=relative_path,
                        change_type=ChangeType.DELETED,
                        timestamp=datetime.utcnow(),
                        size=0,
                        checksum="",
                    )
                )

        logger.info(f"Detected {len(changes)} changes since last snapshot")
        return changes

    def _scan_files(self) -> list[Path]:
        """Scan files in base path, excluding patterns."""
        files = []

        for item in self.base_path.rglob("*"):
            if item.is_file():
                relative_path = str(item.relative_to(self.base_path))

                # Check exclude patterns
                excluded = False
                for pattern in self.exclude_patterns:
                    if pattern in relative_path or item.match(pattern):
                        excluded = True
                        break

                if not excluded:
                    files.append(item)

        return files

    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        hash_sha256 = hashlib.sha256()

        try:
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(8192):
                    hash_sha256.update(chunk)
        except Exception as e:
            logger.warning(f"Failed to calculate checksum for {file_path}: {e}")
            return ""

        return hash_sha256.hexdigest()

    async def _save_snapshot(self, snapshot: IncrementalSnapshot) -> None:
        """Save snapshot to disk."""
        snapshot_data = {
            "snapshot_id": snapshot.snapshot_id,
            "source_id": snapshot.source_id,
            "backup_level": snapshot.backup_level.value,
            "created_at": snapshot.created_at.isoformat(),
            "files_tracked": snapshot.files_tracked,
            "total_size": snapshot.total_size,
            "checksum_map": snapshot.checksum_map,
            "metadata": snapshot.metadata,
        }

        async with aiofiles.open(self.snapshot_file, "w") as f:
            await f.write(json.dumps(snapshot_data, indent=2))

    async def _load_snapshot(self) -> None:
        """Load snapshot from disk."""
        if not self.snapshot_file.exists():
            return

        try:
            async with aiofiles.open(self.snapshot_file) as f:
                content = await f.read()
                data = json.loads(content)

            self.last_snapshot = IncrementalSnapshot(
                snapshot_id=data["snapshot_id"],
                source_id=data["source_id"],
                backup_level=BackupLevel(data["backup_level"]),
                created_at=datetime.fromisoformat(data["created_at"]),
                files_tracked=data["files_tracked"],
                total_size=data["total_size"],
                checksum_map=data["checksum_map"],
                metadata=data.get("metadata", {}),
            )

        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            self.last_snapshot = None


class DatabaseTracker:
    """Tracks database changes for incremental backup."""

    def __init__(self, connection_url: str, tables: list[str] | None = None) -> None:
        """Initialize database tracker."""
        self.connection_url = connection_url
        self.tables = tables
        self.engine = create_engine(connection_url)
        self.snapshot_table = "_incremental_backup_snapshots"
        self.changes_table = "_incremental_backup_changes"

    def _validate_table_name(self, table_name: str) -> bool:
        """Validate table name to prevent SQL injection.

        Returns True if the table name is safe to use.
        Table names should only contain alphanumeric characters and underscores.
        """
        # Allow only alphanumeric characters, underscores, and dots (for schema.table)
        pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$"
        return bool(re.match(pattern, table_name))

    async def setup_tracking(self) -> None:
        """Set up database tracking infrastructure."""
        with self.engine.connect() as conn:
            # Create snapshot tracking table
            # SAFETY: Table names are hardcoded constants, not user input
            # DDL statements cannot be parameterized in standard SQL
            conn.execute(
                text(
                    f"""
                CREATE TABLE IF NOT EXISTS {self.snapshot_table} (
                    id SERIAL PRIMARY KEY,
                    snapshot_id VARCHAR(100) UNIQUE NOT NULL,
                    table_name VARCHAR(100) NOT NULL,
                    record_count BIGINT NOT NULL,
                    checksum VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    metadata JSON
                )
            """
                )
            )

            # Create changes tracking table
            # SAFETY: Table names are hardcoded constants, not user input
            # DDL statements cannot be parameterized in standard SQL
            conn.execute(
                text(
                    f"""
                CREATE TABLE IF NOT EXISTS {self.changes_table} (
                    id SERIAL PRIMARY KEY,
                    snapshot_id VARCHAR(100) NOT NULL,
                    table_name VARCHAR(100) NOT NULL,
                    operation VARCHAR(10) NOT NULL,
                    record_id VARCHAR(100),
                    old_values JSON,
                    new_values JSON,
                    changed_at TIMESTAMP DEFAULT NOW()
                )
            """
                )
            )

            conn.commit()

    async def create_snapshot(self, snapshot_id: str) -> IncrementalSnapshot:
        """Create a database snapshot."""
        tables_to_track = self.tables or await self._get_all_tables()

        total_records = 0
        table_checksums = {}

        with self.engine.connect() as conn:
            for table in tables_to_track:
                # Validate table name before using in query
                if not self._validate_table_name(table):
                    logger.error(f"Invalid table name detected: {table}")
                    continue

                try:
                    # Count records
                    # SAFETY: Table names come from self.tables (configured by admin) or _get_all_tables()
                    # which filters to only public schema tables. This is not user input.
                    # Additionally validated with _validate_table_name() above.
                    # COUNT queries cannot be parameterized for table names in standard SQL
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    total_records += count

                    # Calculate table checksum (simplified)
                    # SAFETY: Table names come from controlled sources and validated as noted above
                    # Aggregate queries cannot parameterize table names in standard SQL
                    result = conn.execute(
                        text(
                            f"""
                        SELECT MD5(ARRAY_AGG(ROW(t.*)::text ORDER BY (SELECT 1))::text)
                        FROM {table} t
                    """
                        )
                    )
                    checksum = result.scalar() or ""
                    table_checksums[table] = checksum

                    # Store snapshot - using parameterized query for data values
                    # SAFETY: Table name is a hardcoded constant, only data values are parameterized
                    conn.execute(
                        text(
                            f"""
                        INSERT INTO {self.snapshot_table}
                        (snapshot_id, table_name, record_count, checksum, metadata)
                        VALUES (:snapshot_id, :table_name, :record_count, :checksum, :metadata)
                    """
                        ),
                        {
                            "snapshot_id": snapshot_id,
                            "table_name": table,
                            "record_count": count,
                            "checksum": checksum,
                            "metadata": json.dumps({"full_snapshot": True}),
                        },
                    )

                except Exception as e:
                    logger.error(f"Error creating snapshot for table {table}: {e}")
                    continue

            conn.commit()

        snapshot = IncrementalSnapshot(
            snapshot_id=snapshot_id,
            source_id=self.connection_url,
            backup_level=BackupLevel.FULL,
            created_at=datetime.utcnow(),
            files_tracked=len(tables_to_track),
            total_size=total_records,
            checksum_map=table_checksums,
            metadata={"tables": tables_to_track},
        )

        logger.info(
            f"Created database snapshot: {len(tables_to_track)} tables, {total_records} records"
        )
        return snapshot

    async def detect_changes(self, since_snapshot_id: str) -> list[ChangeRecord]:
        """Detect database changes since snapshot."""
        changes = []

        with self.engine.connect() as conn:
            # Get previous snapshot data
            # SAFETY: Table name is a hardcoded constant, not user input
            result = conn.execute(
                text(
                    f"""
                SELECT table_name, checksum FROM {self.snapshot_table}
                WHERE snapshot_id = :snapshot_id
            """
                ),
                {"snapshot_id": since_snapshot_id},
            )

            previous_checksums: dict[str, Any] = dict(result.fetchall())

            # Check current state against previous
            for table, prev_checksum in previous_checksums.items():
                # Validate table name before using in query
                if not self._validate_table_name(table):
                    logger.error(f"Invalid table name detected in snapshot: {table}")
                    continue

                try:
                    # Calculate current checksum
                    # SAFETY: Table names come from database query results which were previously validated
                    # and stored during snapshot creation. Not direct user input.
                    # Additionally validated with _validate_table_name() above.
                    # Aggregate queries cannot parameterize table names in standard SQL
                    result = conn.execute(
                        text(
                            f"""
                        SELECT MD5(ARRAY_AGG(ROW(t.*)::text ORDER BY (SELECT 1))::text)
                        FROM {table} t
                    """
                        )
                    )
                    current_checksum = result.scalar() or ""

                    if current_checksum != prev_checksum:
                        # Table has changed
                        # SAFETY: Table names come from validated database results and validated above
                        # COUNT queries cannot parameterize table names in standard SQL
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()

                        changes.append(
                            ChangeRecord(
                                path=table,
                                change_type=ChangeType.MODIFIED,
                                timestamp=datetime.utcnow(),
                                size=count,
                                checksum=current_checksum,
                                metadata={"table": True},
                            )
                        )

                except Exception as e:
                    logger.error(f"Error checking changes for table {table}: {e}")
                    continue

        logger.info(f"Detected {len(changes)} database table changes")
        return changes

    async def _get_all_tables(self) -> list[str]:
        """Get all tables in the database."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                AND table_name NOT LIKE '_incremental_backup_%'
            """
                )
            )
            return [row[0] for row in result.fetchall()]


class IncrementalBackupService:
    """Main incremental backup service."""

    def __init__(self, metrics_service: MetricsService | None = None) -> None:
        """Initialize incremental backup service."""
        self.metrics_service = metrics_service or MetricsService()
        self.secrets_manager = get_secrets_manager()
        self.trackers: dict[str, FileSystemTracker | DatabaseTracker] = {}
        self.backup_history: dict[str, list[IncrementalSnapshot]] = {}

    def register_filesystem_source(
        self, source_id: str, path: str, exclude_patterns: list[str] | None = None
    ) -> None:
        """Register a file system source for tracking."""
        tracker = FileSystemTracker(path, exclude_patterns)
        self.trackers[source_id] = tracker
        logger.info(f"Registered filesystem source: {source_id} -> {path}")

    def register_database_source(
        self, source_id: str, connection_url: str, tables: list[str] | None = None
    ) -> None:
        """Register a database source for tracking."""
        tracker = DatabaseTracker(connection_url, tables)
        self.trackers[source_id] = tracker
        logger.info(f"Registered database source: {source_id}")

    async def initialize_tracking(self) -> None:
        """Initialize tracking for all registered sources."""
        for source_id, tracker in self.trackers.items():
            if isinstance(tracker, DatabaseTracker):
                await tracker.setup_tracking()
                logger.info(f"Initialized database tracking: {source_id}")

    async def create_full_snapshot(self, source_id: str) -> IncrementalSnapshot | None:
        """Create a full snapshot for a source."""
        if source_id not in self.trackers:
            logger.error(f"Source not registered: {source_id}")
            return None

        start_time = time.time()
        snapshot_id = f"{source_id}_full_{int(start_time)}"
        tracker = self.trackers[source_id]

        try:
            snapshot = await tracker.create_snapshot(snapshot_id)

            # Store in history
            if source_id not in self.backup_history:
                self.backup_history[source_id] = []
            self.backup_history[source_id].append(snapshot)

            # Update metrics
            await self.metrics_service.record_counter(
                "incremental_backup_snapshot_created",
                tags={"source_id": source_id, "level": "full"},
            )

            await self.metrics_service.record_histogram(
                "incremental_backup_snapshot_duration",
                time.time() - start_time,
                tags={"source_id": source_id, "level": "full"},
            )

            await self.metrics_service.record_gauge(
                "incremental_backup_snapshot_size",
                snapshot.total_size,
                tags={"source_id": source_id, "level": "full"},
            )

            logger.info(f"Created full snapshot: {snapshot_id}")
            return snapshot

        except Exception as e:
            logger.error(f"Failed to create snapshot for {source_id}: {e}")
            return None

    async def detect_changes(
        self, source_id: str, since_snapshot_id: str | None = None
    ) -> list[ChangeRecord]:
        """Detect changes for a source."""
        if source_id not in self.trackers:
            logger.error(f"Source not registered: {source_id}")
            return []

        tracker = self.trackers[source_id]

        try:
            changes = await tracker.detect_changes(since_snapshot_id)

            # Update metrics
            await self.metrics_service.record_counter(
                "incremental_backup_changes_detected",
                value=len(changes),
                tags={"source_id": source_id},
            )

            # Count changes by type
            change_counts: dict[str, Any] = {}
            for change in changes:
                change_counts[change.change_type.value] = (
                    change_counts.get(change.change_type.value, 0) + 1
                )

            for change_type, count in change_counts.items():
                await self.metrics_service.record_gauge(
                    f"incremental_backup_changes_{change_type}",
                    count,
                    tags={"source_id": source_id},
                )

            return changes

        except Exception as e:
            logger.error(f"Failed to detect changes for {source_id}: {e}")
            return []

    async def get_backup_plan(self, source_id: str) -> dict[str, Any]:
        """Get optimal backup plan based on change patterns."""
        changes = await self.detect_changes(source_id)

        if not changes:
            return {
                "recommended_level": BackupLevel.FULL,
                "reason": "No changes detected",
                "change_count": 0,
            }

        # Analyze change patterns
        change_size = sum(change.size for change in changes)

        # Get last full backup info
        last_full = None
        if source_id in self.backup_history:
            full_snapshots = [
                s
                for s in self.backup_history[source_id]
                if s.backup_level == BackupLevel.FULL
            ]
            if full_snapshots:
                last_full = max(full_snapshots, key=lambda s: s.created_at)

        # Decision logic
        if not last_full:
            return {
                "recommended_level": BackupLevel.FULL,
                "reason": "No previous full backup found",
                "change_count": len(changes),
                "change_size": change_size,
            }

        days_since_full = (datetime.utcnow() - last_full.created_at).days
        change_ratio = (
            change_size / last_full.total_size if last_full.total_size > 0 else 1
        )

        if days_since_full >= 7 or change_ratio > 0.3:
            return {
                "recommended_level": BackupLevel.FULL,
                "reason": f"Change ratio {change_ratio:.2%} or {days_since_full} days since full backup",
                "change_count": len(changes),
                "change_size": change_size,
            }
        elif change_ratio > 0.1:
            return {
                "recommended_level": BackupLevel.DIFFERENTIAL,
                "reason": f"Moderate change ratio {change_ratio:.2%}",
                "change_count": len(changes),
                "change_size": change_size,
            }
        else:
            return {
                "recommended_level": BackupLevel.INCREMENTAL,
                "reason": f"Low change ratio {change_ratio:.2%}",
                "change_count": len(changes),
                "change_size": change_size,
            }

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        return {
            "registered_sources": len(self.trackers),
            "source_types": {
                source_id: type(tracker).__name__
                for source_id, tracker in self.trackers.items()
            },
            "backup_history_count": {
                source_id: len(snapshots)
                for source_id, snapshots in self.backup_history.items()
            },
            "total_snapshots": sum(
                len(snapshots) for snapshots in self.backup_history.values()
            ),
        }


# Example usage and testing
async def main() -> None:
    """Example usage of the incremental backup service."""
    service = IncrementalBackupService()

    # Register sources
    service.register_filesystem_source(
        "documents", "/app/data/documents", exclude_patterns=["*.tmp", "*.lock"]
    )

    # Initialize tracking
    await service.initialize_tracking()

    # Create initial snapshot
    snapshot = await service.create_full_snapshot("documents")
    if snapshot:
        print(f"Created snapshot: {snapshot.snapshot_id}")

    # Detect changes
    changes = await service.detect_changes("documents")
    print(f"Detected {len(changes)} changes")

    # Get backup plan
    plan = await service.get_backup_plan("documents")
    print(f"Backup plan: {plan}")

    # Get status
    status = service.get_status()
    print(f"Service status: {status}")


if __name__ == "__main__":
    asyncio.run(main())
