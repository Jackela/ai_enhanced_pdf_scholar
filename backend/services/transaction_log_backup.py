"""
Continuous Transaction Log Backup Service
Provides real-time transaction log backup for minimal data loss scenarios.
Supports PostgreSQL WAL (Write-Ahead Log) streaming and archival.
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import aiofiles
from sqlalchemy import create_engine, text

from backend.core.secrets import get_secrets_manager
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class LogBackupStatus(str, Enum):
    """Transaction log backup status."""

    STREAMING = "streaming"
    ARCHIVING = "archiving"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class LogType(str, Enum):
    """Types of transaction logs."""

    WAL = "wal"  # PostgreSQL Write-Ahead Log
    TRANSACTION_LOG = "transaction_log"  # General transaction log
    REDO_LOG = "redo_log"  # Oracle/MySQL redo log
    BINARY_LOG = "binary_log"  # MySQL binary log


@dataclass
class LogSegment:
    """Transaction log segment metadata."""

    segment_id: str
    log_type: LogType
    sequence_number: int
    start_lsn: str  # Log Sequence Number
    end_lsn: str
    file_path: str
    backup_path: str
    file_size: int
    checksum: str
    created_at: datetime
    archived_at: datetime | None = None
    backup_status: LogBackupStatus = LogBackupStatus.STREAMING
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupConfiguration:
    """Transaction log backup configuration."""

    # Database connection
    connection_url: str
    database_name: str

    # Log directories
    source_log_dir: str
    archive_log_dir: str
    backup_log_dir: str

    # Backup settings
    archive_mode: bool = True
    archive_timeout: int = 300  # seconds
    max_wal_size: str = "1GB"
    min_wal_size: str = "80MB"

    # Streaming settings
    streaming_enabled: bool = True
    streaming_port: int = 5432
    max_replication_slots: int = 10

    # Compression and encryption
    compression_enabled: bool = True
    encryption_enabled: bool = True

    # Retention settings
    archive_retention_days: int = 30
    backup_retention_days: int = 7

    # Performance settings
    parallel_backup_workers: int = 2
    backup_buffer_size: str = "64MB"

    metadata: dict[str, Any] = field(default_factory=dict)


class PostgreSQLWALBackup:
    """PostgreSQL Write-Ahead Log backup implementation."""

    def __init__(self, config: BackupConfiguration):
        """Initialize PostgreSQL WAL backup."""
        self.config = config
        self.engine = create_engine(config.connection_url)
        self.active_segments: dict[str, LogSegment] = {}
        self.backup_process: asyncio.subprocess.Process | None = None
        self.is_streaming = False

        # Create directories
        self._create_backup_directories()

    def _create_backup_directories(self):
        """Create necessary backup directories."""
        dirs_to_create = [
            self.config.archive_log_dir,
            self.config.backup_log_dir,
            f"{self.config.backup_log_dir}/compressed",
            f"{self.config.backup_log_dir}/encrypted",
            f"{self.config.backup_log_dir}/metadata",
        ]

        for dir_path in dirs_to_create:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    async def setup_wal_archiving(self) -> bool:
        """Setup PostgreSQL WAL archiving configuration."""
        try:
            with self.engine.connect() as conn:
                # Check current WAL settings
                result = conn.execute(text("SHOW archive_mode"))
                current_archive_mode = result.scalar()

                if current_archive_mode != "on":
                    logger.warning(
                        "WAL archiving not enabled. Please enable in postgresql.conf:"
                    )
                    logger.warning("archive_mode = on")
                    logger.warning(
                        f"archive_command = 'cp %p {self.config.archive_log_dir}/%f'"
                    )
                    return False

                # Check replication settings
                result = conn.execute(text("SHOW wal_level"))
                wal_level = result.scalar()

                if wal_level not in ["replica", "logical"]:
                    logger.warning(
                        f"WAL level '{wal_level}' may not support streaming. Consider 'replica' or 'logical'."
                    )

                # Create replication slot if streaming is enabled
                if self.config.streaming_enabled:
                    slot_name = f"{self.config.database_name}_backup_slot"

                    try:
                        # Safe: slot_name is built from database_name configuration, not user input
                        conn.execute(
                            text(
                                f"SELECT pg_create_physical_replication_slot('{slot_name}')"
                            )
                        )
                        logger.info(f"Created replication slot: {slot_name}")
                    except Exception as e:
                        if "already exists" in str(e):
                            logger.info(f"Replication slot already exists: {slot_name}")
                        else:
                            logger.error(f"Failed to create replication slot: {e}")
                            return False

                logger.info("WAL archiving setup completed")
                return True

        except Exception as e:
            logger.error(f"Error setting up WAL archiving: {e}")
            return False

    async def start_continuous_backup(self) -> bool:
        """Start continuous WAL backup process."""
        try:
            if self.is_streaming:
                logger.warning("Continuous backup already running")
                return True

            # Setup WAL archiving first
            if not await self.setup_wal_archiving():
                return False

            self.is_streaming = True

            # Start background tasks
            tasks = [
                asyncio.create_task(self._wal_archive_monitor()),
                asyncio.create_task(self._wal_streaming_backup()),
                asyncio.create_task(self._cleanup_old_archives()),
            ]

            logger.info("Started continuous WAL backup")

            # Wait for tasks to complete (they should run indefinitely)
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.info("Continuous backup tasks cancelled")

            return True

        except Exception as e:
            logger.error(f"Error starting continuous backup: {e}")
            self.is_streaming = False
            return False

    async def _wal_archive_monitor(self):
        """Monitor WAL archive directory for new files."""
        archive_dir = Path(self.config.archive_log_dir)
        processed_files = set()

        logger.info(f"Starting WAL archive monitor for {archive_dir}")

        while self.is_streaming:
            try:
                # Scan for new WAL files
                wal_files = list(archive_dir.glob("*"))

                for wal_file in wal_files:
                    if wal_file.name not in processed_files and wal_file.is_file():
                        await self._process_wal_file(wal_file)
                        processed_files.add(wal_file.name)

                # Clean up processed files set to prevent memory growth
                if len(processed_files) > 10000:
                    # Keep only recent files
                    recent_files = {
                        f.name for f in archive_dir.glob("*") if f.is_file()
                    }
                    processed_files &= recent_files

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in WAL archive monitor: {e}")
                await asyncio.sleep(10)

    async def _process_wal_file(self, wal_file: Path):
        """Process a new WAL file."""
        try:
            # Create log segment metadata
            segment_id = f"wal_{wal_file.stem}_{int(time.time())}"

            # Calculate checksum
            checksum = await self._calculate_file_checksum(wal_file)

            # Parse WAL file metadata
            wal_info = await self._parse_wal_file_info(wal_file)

            segment = LogSegment(
                segment_id=segment_id,
                log_type=LogType.WAL,
                sequence_number=wal_info.get("sequence_number", 0),
                start_lsn=wal_info.get("start_lsn", "0/0"),
                end_lsn=wal_info.get("end_lsn", "0/0"),
                file_path=str(wal_file),
                backup_path="",  # Will be set during backup
                file_size=wal_file.stat().st_size,
                checksum=checksum,
                created_at=datetime.fromtimestamp(wal_file.stat().st_mtime),
                backup_status=LogBackupStatus.ARCHIVING,
                metadata=wal_info,
            )

            # Backup the WAL file
            await self._backup_wal_segment(segment)

            self.active_segments[segment_id] = segment

            logger.info(f"Processed WAL file: {wal_file.name} -> {segment.backup_path}")

        except Exception as e:
            logger.error(f"Error processing WAL file {wal_file}: {e}")

    async def _backup_wal_segment(self, segment: LogSegment):
        """Backup a WAL segment with optional compression and encryption."""
        try:
            source_file = Path(segment.file_path)
            timestamp = segment.created_at.strftime("%Y%m%d_%H%M%S")

            # Determine backup path
            backup_filename = f"{source_file.stem}_{timestamp}.wal"
            backup_path = Path(self.config.backup_log_dir) / backup_filename

            # Copy file to backup location
            shutil.copy2(source_file, backup_path)

            # Compress if enabled
            if self.config.compression_enabled:
                compressed_path = await self._compress_wal_file(backup_path)
                if compressed_path:
                    backup_path.unlink()  # Remove uncompressed version
                    backup_path = compressed_path

            # Encrypt if enabled
            if self.config.encryption_enabled:
                encrypted_path = await self._encrypt_wal_file(backup_path)
                if encrypted_path:
                    backup_path.unlink()  # Remove unencrypted version
                    backup_path = encrypted_path

            segment.backup_path = str(backup_path)
            segment.backup_status = LogBackupStatus.COMPLETED
            segment.archived_at = datetime.utcnow()

            # Save segment metadata
            await self._save_segment_metadata(segment)

        except Exception as e:
            segment.backup_status = LogBackupStatus.FAILED
            logger.error(f"Error backing up WAL segment {segment.segment_id}: {e}")

    async def _compress_wal_file(self, file_path: Path) -> Path | None:
        """Compress WAL file using gzip."""
        try:
            compressed_path = (
                Path(self.config.backup_log_dir) / "compressed" / f"{file_path.name}.gz"
            )

            # Use gzip command for compression
            cmd = ["gzip", "-c", str(file_path)]

            with open(compressed_path, "wb") as output_file:
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=output_file, stderr=asyncio.subprocess.PIPE
                )

                _, stderr = await process.communicate()

                if process.returncode == 0:
                    logger.debug(f"Compressed WAL file: {file_path.name}")
                    return compressed_path
                else:
                    error_msg = (
                        stderr.decode("utf-8")
                        if stderr
                        else "Unknown compression error"
                    )
                    logger.error(f"WAL compression failed: {error_msg}")
                    return None

        except Exception as e:
            logger.error(f"Error compressing WAL file: {e}")
            return None

    async def _encrypt_wal_file(self, file_path: Path) -> Path | None:
        """Encrypt WAL file using AES-256."""
        try:
            encrypted_path = (
                Path(self.config.backup_log_dir) / "encrypted" / f"{file_path.name}.enc"
            )

            # Use openssl for encryption (in production, use proper key management)
            encryption_key = (
                "your-encryption-key-here"  # Should come from secrets manager
            )

            cmd = [
                "openssl",
                "enc",
                "-aes-256-cbc",
                "-in",
                str(file_path),
                "-out",
                str(encrypted_path),
                "-k",
                encryption_key,
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.debug(f"Encrypted WAL file: {file_path.name}")
                return encrypted_path
            else:
                error_msg = (
                    stderr.decode("utf-8") if stderr else "Unknown encryption error"
                )
                logger.error(f"WAL encryption failed: {error_msg}")
                return None

        except Exception as e:
            logger.error(f"Error encrypting WAL file: {e}")
            return None

    async def _wal_streaming_backup(self):
        """Stream WAL using pg_receivewal for real-time backup."""
        if not self.config.streaming_enabled:
            return

        try:
            # Parse connection URL for pg_receivewal
            connection_params = self._parse_connection_url()

            # Build pg_receivewal command
            cmd = [
                "pg_receivewal",
                "--directory",
                self.config.backup_log_dir,
                "--host",
                connection_params["host"],
                "--port",
                str(connection_params["port"]),
                "--username",
                connection_params["username"],
                "--dbname",
                connection_params["database"],
                "--verbose",
                "--compress",
                "6" if self.config.compression_enabled else "0",
            ]

            # Set password environment variable
            env = os.environ.copy()
            if connection_params["password"]:
                env["PGPASSWORD"] = connection_params["password"]

            logger.info("Starting WAL streaming backup")

            # Start pg_receivewal process
            self.backup_process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Monitor the process
            while self.is_streaming and self.backup_process.returncode is None:
                try:
                    # Check if process is still running
                    await asyncio.wait_for(self.backup_process.wait(), timeout=5.0)
                    break
                except asyncio.TimeoutError:
                    # Process is still running, continue monitoring
                    continue

            # Process ended
            if self.backup_process.returncode != 0:
                _, stderr = await self.backup_process.communicate()
                error_msg = stderr.decode("utf-8") if stderr else "Unknown error"
                logger.error(f"WAL streaming failed: {error_msg}")
            else:
                logger.info("WAL streaming completed normally")

        except Exception as e:
            logger.error(f"Error in WAL streaming backup: {e}")

    async def _cleanup_old_archives(self):
        """Clean up old archived WAL files based on retention policy."""
        while self.is_streaming:
            try:
                cutoff_date = datetime.utcnow() - timedelta(
                    days=self.config.archive_retention_days
                )

                # Clean up archived WAL files
                archive_dir = Path(self.config.archive_log_dir)
                backup_dir = Path(self.config.backup_log_dir)

                for directory in [archive_dir, backup_dir]:
                    if directory.exists():
                        for file_path in directory.rglob("*"):
                            if file_path.is_file():
                                file_mtime = datetime.fromtimestamp(
                                    file_path.stat().st_mtime
                                )

                                if file_mtime < cutoff_date:
                                    try:
                                        file_path.unlink()
                                        logger.debug(
                                            f"Cleaned up old WAL file: {file_path}"
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to remove old file {file_path}: {e}"
                                        )

                # Clean up old segments from memory
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                expired_segments = [
                    seg_id
                    for seg_id, segment in self.active_segments.items()
                    if segment.created_at < cutoff_time
                ]

                for seg_id in expired_segments:
                    del self.active_segments[seg_id]

                # Sleep for 1 hour before next cleanup
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(3600)

    async def _parse_wal_file_info(self, wal_file: Path) -> dict[str, Any]:
        """Parse WAL file information."""
        try:
            # Use pg_waldump to get WAL file information
            cmd = ["pg_waldump", "--stats", str(wal_file)]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                decoded_output = stdout.decode("utf-8")

                # Parse output for relevant information
                info = {
                    "file_name": wal_file.name,
                    "file_size": wal_file.stat().st_size,
                    "parsed_successfully": True,
                    "raw_output_preview": decoded_output[:500],
                }

                # Extract timeline and segment info from filename
                # PostgreSQL WAL filename format: 000000010000000000000001
                wal_name = wal_file.stem
                if len(wal_name) == 24:  # Standard WAL filename length
                    info.update(
                        {
                            "timeline_id": wal_name[:8],
                            "log_file_id": wal_name[8:16],
                            "segment_id": wal_name[16:24],
                            "sequence_number": int(wal_name[16:24], 16),
                        }
                    )

                return info

            else:
                # pg_waldump not available or failed, return basic info
                return {
                    "file_name": wal_file.name,
                    "file_size": wal_file.stat().st_size,
                    "parsed_successfully": False,
                    "error": stderr.decode("utf-8") if stderr else "pg_waldump failed",
                }

        except Exception as e:
            return {
                "file_name": wal_file.name,
                "file_size": wal_file.stat().st_size,
                "parsed_successfully": False,
                "error": str(e),
            }

    async def _save_segment_metadata(self, segment: LogSegment):
        """Save segment metadata to file."""
        try:
            metadata_dir = Path(self.config.backup_log_dir) / "metadata"
            metadata_file = metadata_dir / f"{segment.segment_id}.json"

            metadata = {
                "segment_id": segment.segment_id,
                "log_type": segment.log_type.value,
                "sequence_number": segment.sequence_number,
                "start_lsn": segment.start_lsn,
                "end_lsn": segment.end_lsn,
                "file_path": segment.file_path,
                "backup_path": segment.backup_path,
                "file_size": segment.file_size,
                "checksum": segment.checksum,
                "created_at": segment.created_at.isoformat(),
                "archived_at": segment.archived_at.isoformat()
                if segment.archived_at
                else None,
                "backup_status": segment.backup_status.value,
                "metadata": segment.metadata,
            }

            async with aiofiles.open(metadata_file, "w") as f:
                await f.write(json.dumps(metadata, indent=2))

        except Exception as e:
            logger.error(f"Error saving segment metadata: {e}")

    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file."""
        hash_sha256 = hashlib.sha256()

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()

    def _parse_connection_url(self) -> dict[str, Any]:
        """Parse PostgreSQL connection URL."""
        from urllib.parse import urlparse

        parsed = urlparse(self.config.connection_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": parsed.path.lstrip("/") if parsed.path else "postgres",
            "username": parsed.username,
            "password": parsed.password,
        }

    async def stop_continuous_backup(self):
        """Stop continuous backup process."""
        logger.info("Stopping continuous WAL backup")
        self.is_streaming = False

        # Terminate streaming process if running
        if self.backup_process and self.backup_process.returncode is None:
            self.backup_process.terminate()
            try:
                await asyncio.wait_for(self.backup_process.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                self.backup_process.kill()
                await self.backup_process.wait()

        logger.info("Continuous WAL backup stopped")

    def get_backup_status(self) -> dict[str, Any]:
        """Get current backup status."""
        return {
            "is_streaming": self.is_streaming,
            "active_segments": len(self.active_segments),
            "last_processed": max(
                (seg.created_at for seg in self.active_segments.values()), default=None
            ),
            "backup_process_running": (
                self.backup_process is not None
                and self.backup_process.returncode is None
            ),
            "configuration": {
                "archive_mode": self.config.archive_mode,
                "streaming_enabled": self.config.streaming_enabled,
                "compression_enabled": self.config.compression_enabled,
                "encryption_enabled": self.config.encryption_enabled,
            },
        }


class TransactionLogBackupService:
    """Main transaction log backup service."""

    def __init__(self, metrics_service: MetricsService | None = None):
        """Initialize transaction log backup service."""
        self.metrics_service = metrics_service or MetricsService()
        self.secrets_manager = get_secrets_manager()

        # Active backup instances
        self.backup_instances: dict[str, PostgreSQLWALBackup] = {}

    def register_database(self, database_id: str, config: BackupConfiguration):
        """Register a database for transaction log backup."""
        backup_instance = PostgreSQLWALBackup(config)
        self.backup_instances[database_id] = backup_instance

        logger.info(f"Registered database for log backup: {database_id}")

    async def start_all_backups(self) -> dict[str, bool]:
        """Start transaction log backup for all registered databases."""
        results = {}

        for database_id, backup_instance in self.backup_instances.items():
            try:
                success = await backup_instance.start_continuous_backup()
                results[database_id] = success

                if success:
                    await self.metrics_service.record_counter(
                        "transaction_log_backup_started",
                        tags={"database_id": database_id},
                    )

            except Exception as e:
                logger.error(f"Failed to start backup for {database_id}: {e}")
                results[database_id] = False

        return results

    async def stop_all_backups(self):
        """Stop transaction log backup for all databases."""
        for database_id, backup_instance in self.backup_instances.items():
            try:
                await backup_instance.stop_continuous_backup()

                await self.metrics_service.record_counter(
                    "transaction_log_backup_stopped", tags={"database_id": database_id}
                )

            except Exception as e:
                logger.error(f"Failed to stop backup for {database_id}: {e}")

    def get_service_status(self) -> dict[str, Any]:
        """Get overall service status."""
        database_statuses = {}

        for database_id, backup_instance in self.backup_instances.items():
            database_statuses[database_id] = backup_instance.get_backup_status()

        return {
            "registered_databases": len(self.backup_instances),
            "database_statuses": database_statuses,
            "service_healthy": all(
                status["is_streaming"] for status in database_statuses.values()
            ),
        }


# Example usage and testing
async def main():
    """Example usage of transaction log backup service."""
    service = TransactionLogBackupService()

    # Configure database backup
    config = BackupConfiguration(
        connection_url="postgresql://user:pass@localhost:5432/mydb",
        database_name="mydb",
        source_log_dir="/var/lib/postgresql/12/main/pg_wal",
        archive_log_dir="/var/backups/wal_archive",
        backup_log_dir="/var/backups/wal_backup",
        streaming_enabled=True,
        compression_enabled=True,
        encryption_enabled=True,
    )

    # Register database
    service.register_database("primary_db", config)

    # Start backup service
    results = await service.start_all_backups()
    print(f"Backup start results: {results}")

    # Let it run for a bit (in production, this would run continuously)
    await asyncio.sleep(10)

    # Check status
    status = service.get_service_status()
    print(f"Service status: {status}")

    # Stop backups
    await service.stop_all_backups()
    print("Backup service stopped")


if __name__ == "__main__":
    asyncio.run(main())
