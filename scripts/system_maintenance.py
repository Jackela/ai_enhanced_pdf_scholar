#!/usr/bin/env python3
"""
Automated System Maintenance
Comprehensive maintenance automation for AI Enhanced PDF Scholar production system.
"""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil
import redis

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration and Models
# ============================================================================


@dataclass
class MaintenanceTask:
    """Maintenance task result."""

    task_name: str
    status: str  # success, failed, skipped, warning
    message: str
    execution_time: float
    details: dict[str, Any] = None
    metrics: dict[str, Any] = None


@dataclass
class MaintenanceReport:
    """Comprehensive maintenance report."""

    start_time: datetime
    end_time: datetime
    total_duration: float
    tasks_completed: list[MaintenanceTask]
    system_metrics_before: dict[str, Any]
    system_metrics_after: dict[str, Any]
    recommendations: list[str]
    next_scheduled: datetime | None = None


class MaintenanceConfig:
    """Configuration for maintenance operations."""

    # General settings
    DRY_RUN = os.getenv("MAINTENANCE_DRY_RUN", "false").lower() == "true"
    FORCE_MAINTENANCE = os.getenv("FORCE_MAINTENANCE", "false").lower() == "true"
    MAX_EXECUTION_TIME = int(os.getenv("MAX_MAINTENANCE_TIME", "3600"))  # 1 hour

    # Database settings
    DB_VACUUM_THRESHOLD = float(
        os.getenv("DB_VACUUM_THRESHOLD", "25.0")
    )  # 25% fragmentation
    DB_BACKUP_RETENTION = int(os.getenv("DB_BACKUP_RETENTION", "7"))  # days

    # Log settings
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
    LOG_COMPRESSION_DAYS = int(os.getenv("LOG_COMPRESSION_DAYS", "7"))

    # Cache settings
    CACHE_OPTIMIZATION_THRESHOLD = float(
        os.getenv("CACHE_OPT_THRESHOLD", "70.0")
    )  # hit rate %

    # Storage settings
    DISK_CLEANUP_THRESHOLD = float(
        os.getenv("DISK_CLEANUP_THRESHOLD", "80.0")
    )  # usage %

    # Performance baseline settings
    UPDATE_BASELINES = (
        os.getenv("UPDATE_PERFORMANCE_BASELINES", "true").lower() == "true"
    )

    # Application paths
    APP_ROOT = Path(os.getenv("APP_ROOT", Path.cwd()))
    DATA_DIR = Path(os.getenv("DATA_DIR", Path.home() / ".ai_pdf_scholar"))
    LOG_DIR = Path(os.getenv("LOG_DIR", "/var/log/ai_pdf_scholar"))


# ============================================================================
# System Maintenance Engine
# ============================================================================


class SystemMaintenanceEngine:
    """Main maintenance automation engine."""

    def __init__(self, config: MaintenanceConfig | None = None) -> None:
        self.config = config or MaintenanceConfig()
        self.tasks_completed: list[MaintenanceTask] = []
        self.start_time = datetime.now()

        # System metrics before maintenance
        self.metrics_before = self._capture_system_metrics()

        logger.info(
            f"System Maintenance Engine initialized. Dry run: {self.config.DRY_RUN}"
        )

    def run_maintenance(self, task_types: list[str] | None = None) -> MaintenanceReport:
        """Run comprehensive maintenance tasks."""

        logger.info("Starting automated system maintenance")

        # Define maintenance tasks
        maintenance_tasks = {
            "database": self._database_maintenance,
            "logs": self._log_maintenance,
            "cache": self._cache_maintenance,
            "storage": self._storage_maintenance,
            "performance": self._performance_maintenance,
            "security": self._security_maintenance,
            "health_checks": self._health_verification,
        }

        # Run selected or all tasks
        if task_types:
            tasks_to_run = {
                k: v for k, v in maintenance_tasks.items() if k in task_types
            }
        else:
            tasks_to_run = maintenance_tasks

        logger.info(f"Running {len(tasks_to_run)} maintenance task types")

        for task_name, task_func in tasks_to_run.items():
            try:
                logger.info(f"Starting maintenance task: {task_name}")
                result = task_func()

                if isinstance(result, list):
                    self.tasks_completed.extend(result)
                else:
                    self.tasks_completed.append(result)

            except Exception as e:
                logger.error(f"Maintenance task {task_name} failed: {e}")
                self.tasks_completed.append(
                    MaintenanceTask(
                        task_name=task_name,
                        status="failed",
                        message=f"Task failed with error: {str(e)}",
                        execution_time=0.0,
                    )
                )

        # Generate maintenance report
        end_time = datetime.now()
        metrics_after = self._capture_system_metrics()

        report = MaintenanceReport(
            start_time=self.start_time,
            end_time=end_time,
            total_duration=(end_time - self.start_time).total_seconds(),
            tasks_completed=self.tasks_completed,
            system_metrics_before=self.metrics_before,
            system_metrics_after=metrics_after,
            recommendations=self._generate_recommendations(),
        )

        logger.info("System maintenance completed")
        return report

    def _capture_system_metrics(self) -> dict[str, Any]:
        """Capture current system metrics."""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "timestamp": datetime.now().isoformat(),
                "memory_usage_percent": memory.percent,
                "memory_available_mb": memory.available // (1024 * 1024),
                "disk_usage_percent": round(100 * disk.used / disk.total, 2),
                "disk_free_gb": disk.free // (1024 * 1024 * 1024),
                "cpu_usage_percent": psutil.cpu_percent(interval=1),
                "load_average": (
                    list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else None
                ),
                "uptime_seconds": time.time() - psutil.boot_time(),
            }
        except Exception as e:
            logger.warning(f"Failed to capture system metrics: {e}")
            return {"error": str(e)}

    # ============================================================================
    # Database Maintenance
    # ============================================================================

    def _database_maintenance(self) -> list[MaintenanceTask]:
        """Perform database maintenance operations."""
        tasks = []

        # Task 1: Database VACUUM and optimization
        tasks.append(self._database_vacuum())

        # Task 2: Database statistics update
        tasks.append(self._database_analyze())

        # Task 3: Database integrity check
        tasks.append(self._database_integrity_check())

        # Task 4: Database backup
        tasks.append(self._database_backup())

        # Task 5: Old backup cleanup
        tasks.append(self._database_backup_cleanup())

        return tasks

    def _database_vacuum(self) -> MaintenanceTask:
        """Perform SQLite VACUUM operation."""
        start_time = time.time()

        try:
            db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"

            if not db_path.exists():
                return MaintenanceTask(
                    task_name="database_vacuum",
                    status="skipped",
                    message="Database file not found",
                    execution_time=0.0,
                )

            # Get database size before
            size_before = db_path.stat().st_size

            if not self.config.DRY_RUN:
                # Connect and VACUUM
                with sqlite3.connect(str(db_path)) as conn:
                    cursor = conn.cursor()

                    # Check if VACUUM is needed
                    cursor.execute("PRAGMA freelist_count")
                    free_pages = cursor.fetchone()[0]

                    cursor.execute("PRAGMA page_count")
                    total_pages = cursor.fetchone()[0]

                    if total_pages > 0:
                        fragmentation = (free_pages / total_pages) * 100
                    else:
                        fragmentation = 0

                    if (
                        fragmentation > self.config.DB_VACUUM_THRESHOLD
                        or self.config.FORCE_MAINTENANCE
                    ):
                        logger.info(
                            f"Database fragmentation: {fragmentation:.2f}% - Running VACUUM"
                        )
                        cursor.execute("VACUUM")
                        conn.commit()

                        size_after = db_path.stat().st_size
                        space_saved = size_before - size_after

                        return MaintenanceTask(
                            task_name="database_vacuum",
                            status="success",
                            message=f"Database vacuumed. Space saved: {space_saved // 1024} KB",
                            execution_time=time.time() - start_time,
                            metrics={
                                "fragmentation_before": fragmentation,
                                "size_before_bytes": size_before,
                                "size_after_bytes": size_after,
                                "space_saved_bytes": space_saved,
                            },
                        )
                    else:
                        return MaintenanceTask(
                            task_name="database_vacuum",
                            status="skipped",
                            message=f"VACUUM not needed. Fragmentation: {fragmentation:.2f}%",
                            execution_time=time.time() - start_time,
                            metrics={"fragmentation": fragmentation},
                        )
            else:
                return MaintenanceTask(
                    task_name="database_vacuum",
                    status="success",
                    message="Database VACUUM simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="database_vacuum",
                status="failed",
                message=f"Database VACUUM failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _database_analyze(self) -> MaintenanceTask:
        """Update database statistics."""
        start_time = time.time()

        try:
            db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"

            if not db_path.exists():
                return MaintenanceTask(
                    task_name="database_analyze",
                    status="skipped",
                    message="Database file not found",
                    execution_time=0.0,
                )

            if not self.config.DRY_RUN:
                with sqlite3.connect(str(db_path)) as conn:
                    cursor = conn.cursor()

                    # Update statistics
                    cursor.execute("ANALYZE")
                    conn.commit()

                    # Get table statistics
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()

                    table_stats = {}
                    for table in tables:
                        table_name = table[0]
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        row_count = cursor.fetchone()[0]
                        table_stats[table_name] = row_count

                    return MaintenanceTask(
                        task_name="database_analyze",
                        status="success",
                        message=f"Database statistics updated for {len(table_stats)} tables",
                        execution_time=time.time() - start_time,
                        metrics={"table_stats": table_stats},
                    )
            else:
                return MaintenanceTask(
                    task_name="database_analyze",
                    status="success",
                    message="Database ANALYZE simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="database_analyze",
                status="failed",
                message=f"Database ANALYZE failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _database_integrity_check(self) -> MaintenanceTask:
        """Perform database integrity check."""
        start_time = time.time()

        try:
            db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"

            if not db_path.exists():
                return MaintenanceTask(
                    task_name="database_integrity_check",
                    status="skipped",
                    message="Database file not found",
                    execution_time=0.0,
                )

            if not self.config.DRY_RUN:
                with sqlite3.connect(str(db_path)) as conn:
                    cursor = conn.cursor()

                    # Quick integrity check
                    cursor.execute("PRAGMA quick_check")
                    result = cursor.fetchone()[0]

                    if result == "ok":
                        # Get additional info
                        cursor.execute("PRAGMA foreign_key_check")
                        fk_violations = cursor.fetchall()

                        if fk_violations:
                            return MaintenanceTask(
                                task_name="database_integrity_check",
                                status="warning",
                                message=f"Database integrity OK, but {len(fk_violations)} foreign key violations found",
                                execution_time=time.time() - start_time,
                                details={"foreign_key_violations": fk_violations},
                            )
                        else:
                            return MaintenanceTask(
                                task_name="database_integrity_check",
                                status="success",
                                message="Database integrity check passed",
                                execution_time=time.time() - start_time,
                            )
                    else:
                        return MaintenanceTask(
                            task_name="database_integrity_check",
                            status="failed",
                            message=f"Database integrity check failed: {result}",
                            execution_time=time.time() - start_time,
                        )
            else:
                return MaintenanceTask(
                    task_name="database_integrity_check",
                    status="success",
                    message="Database integrity check simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="database_integrity_check",
                status="failed",
                message=f"Database integrity check failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _database_backup(self) -> MaintenanceTask:
        """Create database backup."""
        start_time = time.time()

        try:
            db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"
            backup_dir = self.config.DATA_DIR / "backups"

            if not db_path.exists():
                return MaintenanceTask(
                    task_name="database_backup",
                    status="skipped",
                    message="Database file not found",
                    execution_time=0.0,
                )

            if not self.config.DRY_RUN:
                backup_dir.mkdir(exist_ok=True)

                # Create timestamped backup
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"ai_pdf_scholar_backup_{timestamp}.db"

                # Copy database file
                shutil.copy2(db_path, backup_path)

                # Verify backup
                backup_size = backup_path.stat().st_size
                original_size = db_path.stat().st_size

                if backup_size == original_size:
                    return MaintenanceTask(
                        task_name="database_backup",
                        status="success",
                        message=f"Database backup created: {backup_path.name}",
                        execution_time=time.time() - start_time,
                        metrics={
                            "backup_path": str(backup_path),
                            "backup_size_bytes": backup_size,
                        },
                    )
                else:
                    return MaintenanceTask(
                        task_name="database_backup",
                        status="failed",
                        message=f"Backup verification failed. Size mismatch: {backup_size} vs {original_size}",
                        execution_time=time.time() - start_time,
                    )
            else:
                return MaintenanceTask(
                    task_name="database_backup",
                    status="success",
                    message="Database backup simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="database_backup",
                status="failed",
                message=f"Database backup failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _database_backup_cleanup(self) -> MaintenanceTask:
        """Clean up old database backups."""
        start_time = time.time()

        try:
            backup_dir = self.config.DATA_DIR / "backups"

            if not backup_dir.exists():
                return MaintenanceTask(
                    task_name="database_backup_cleanup",
                    status="skipped",
                    message="Backup directory not found",
                    execution_time=0.0,
                )

            # Find old backups
            cutoff_date = datetime.now() - timedelta(
                days=self.config.DB_BACKUP_RETENTION
            )
            old_backups = []

            for backup_file in backup_dir.glob("ai_pdf_scholar_backup_*.db"):
                if backup_file.stat().st_mtime < cutoff_date.timestamp():
                    old_backups.append(backup_file)

            if old_backups:
                cleaned_count = 0
                total_size_freed = 0

                if not self.config.DRY_RUN:
                    for backup_file in old_backups:
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        total_size_freed += file_size
                        cleaned_count += 1

                return MaintenanceTask(
                    task_name="database_backup_cleanup",
                    status="success",
                    message=f"Cleaned up {len(old_backups) if self.config.DRY_RUN else cleaned_count} old backups. Space freed: {total_size_freed // (1024*1024)} MB",
                    execution_time=time.time() - start_time,
                    metrics={
                        "backups_cleaned": len(old_backups),
                        "space_freed_bytes": total_size_freed,
                    },
                )
            else:
                return MaintenanceTask(
                    task_name="database_backup_cleanup",
                    status="skipped",
                    message="No old backups to clean up",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="database_backup_cleanup",
                status="failed",
                message=f"Backup cleanup failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    # ============================================================================
    # Log Maintenance
    # ============================================================================

    def _log_maintenance(self) -> list[MaintenanceTask]:
        """Perform log maintenance operations."""
        tasks = []

        # Task 1: Log rotation
        tasks.append(self._log_rotation())

        # Task 2: Log compression
        tasks.append(self._log_compression())

        # Task 3: Log cleanup
        tasks.append(self._log_cleanup())

        return tasks

    def _log_rotation(self) -> MaintenanceTask:
        """Perform log rotation."""
        start_time = time.time()

        try:
            if not self.config.DRY_RUN:
                # Try system logrotate first
                try:
                    result = subprocess.run(
                        ["logrotate", "/etc/logrotate.d/ai-pdf-scholar"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                    if result.returncode == 0:
                        return MaintenanceTask(
                            task_name="log_rotation",
                            status="success",
                            message="Log rotation completed via logrotate",
                            execution_time=time.time() - start_time,
                        )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

                # Fallback to manual rotation
                rotated_count = 0
                for log_dir in [self.config.LOG_DIR, self.config.DATA_DIR / "logs"]:
                    if log_dir.exists():
                        for log_file in log_dir.glob("*.log"):
                            if log_file.stat().st_size > 100 * 1024 * 1024:  # 100MB
                                # Rotate large log files
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                rotated_path = log_file.with_suffix(f".log.{timestamp}")
                                log_file.rename(rotated_path)
                                rotated_count += 1

                return MaintenanceTask(
                    task_name="log_rotation",
                    status="success",
                    message=f"Manual log rotation completed. {rotated_count} files rotated",
                    execution_time=time.time() - start_time,
                    metrics={"files_rotated": rotated_count},
                )
            else:
                return MaintenanceTask(
                    task_name="log_rotation",
                    status="success",
                    message="Log rotation simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="log_rotation",
                status="failed",
                message=f"Log rotation failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _log_compression(self) -> MaintenanceTask:
        """Compress old log files."""
        start_time = time.time()

        try:
            compress_cutoff = datetime.now() - timedelta(
                days=self.config.LOG_COMPRESSION_DAYS
            )
            compressed_count = 0
            total_space_saved = 0

            for log_dir in [self.config.LOG_DIR, self.config.DATA_DIR / "logs"]:
                if not log_dir.exists():
                    continue

                # Find log files older than compression threshold
                for log_file in log_dir.rglob("*.log*"):
                    if log_file.suffix == ".gz":  # Already compressed
                        continue

                    if (
                        datetime.fromtimestamp(log_file.stat().st_mtime)
                        < compress_cutoff
                    ):
                        if not self.config.DRY_RUN:
                            # Compress with gzip
                            original_size = log_file.stat().st_size

                            try:
                                result = subprocess.run(
                                    ["gzip", str(log_file)], check=True, timeout=300
                                )

                                compressed_path = log_file.with_suffix(
                                    log_file.suffix + ".gz"
                                )
                                if compressed_path.exists():
                                    compressed_size = compressed_path.stat().st_size
                                    space_saved = original_size - compressed_size
                                    total_space_saved += space_saved
                                    compressed_count += 1

                            except (
                                subprocess.CalledProcessError,
                                subprocess.TimeoutExpired,
                            ):
                                logger.warning(f"Failed to compress {log_file}")
                        else:
                            compressed_count += 1

            if compressed_count > 0:
                return MaintenanceTask(
                    task_name="log_compression",
                    status="success",
                    message=f"Compressed {compressed_count} log files. Space saved: {total_space_saved // (1024*1024)} MB",
                    execution_time=time.time() - start_time,
                    metrics={
                        "files_compressed": compressed_count,
                        "space_saved_bytes": total_space_saved,
                    },
                )
            else:
                return MaintenanceTask(
                    task_name="log_compression",
                    status="skipped",
                    message="No log files need compression",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="log_compression",
                status="failed",
                message=f"Log compression failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _log_cleanup(self) -> MaintenanceTask:
        """Clean up old log files."""
        start_time = time.time()

        try:
            cleanup_cutoff = datetime.now() - timedelta(
                days=self.config.LOG_RETENTION_DAYS
            )
            deleted_count = 0
            total_space_freed = 0

            for log_dir in [self.config.LOG_DIR, self.config.DATA_DIR / "logs"]:
                if not log_dir.exists():
                    continue

                # Find old log files
                for log_file in log_dir.rglob("*.log*"):
                    if (
                        datetime.fromtimestamp(log_file.stat().st_mtime)
                        < cleanup_cutoff
                    ):
                        if not self.config.DRY_RUN:
                            file_size = log_file.stat().st_size
                            log_file.unlink()
                            total_space_freed += file_size
                            deleted_count += 1
                        else:
                            deleted_count += 1

            if deleted_count > 0:
                return MaintenanceTask(
                    task_name="log_cleanup",
                    status="success",
                    message=f"Cleaned up {deleted_count} old log files. Space freed: {total_space_freed // (1024*1024)} MB",
                    execution_time=time.time() - start_time,
                    metrics={
                        "files_deleted": deleted_count,
                        "space_freed_bytes": total_space_freed,
                    },
                )
            else:
                return MaintenanceTask(
                    task_name="log_cleanup",
                    status="skipped",
                    message="No old log files to clean up",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="log_cleanup",
                status="failed",
                message=f"Log cleanup failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    # ============================================================================
    # Cache Maintenance
    # ============================================================================

    def _cache_maintenance(self) -> list[MaintenanceTask]:
        """Perform cache maintenance operations."""
        tasks = []

        # Task 1: Redis cache optimization
        tasks.append(self._redis_cache_optimization())

        # Task 2: File cache cleanup
        tasks.append(self._file_cache_cleanup())

        # Task 3: Cache warming
        tasks.append(self._cache_warming())

        return tasks

    def _redis_cache_optimization(self) -> MaintenanceTask:
        """Optimize Redis cache."""
        start_time = time.time()

        try:
            # Try to connect to Redis
            try:
                r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=5)
                r.ping()
            except (redis.ConnectionError, redis.TimeoutError):
                return MaintenanceTask(
                    task_name="redis_cache_optimization",
                    status="skipped",
                    message="Redis not available",
                    execution_time=time.time() - start_time,
                )

            if not self.config.DRY_RUN:
                # Get Redis info
                info = r.info()
                used_memory = info.get("used_memory", 0)
                max_memory = info.get("maxmemory", 0)

                optimizations = []

                # Clear expired keys
                expired_count = 0
                for key in r.scan_iter(match="*", count=1000):
                    ttl = r.ttl(key)
                    if ttl == -1 and key.decode().startswith(
                        "temp:"
                    ):  # No TTL on temp keys
                        r.expire(key, 3600)  # Set 1 hour TTL
                        expired_count += 1

                if expired_count > 0:
                    optimizations.append(f"Set TTL on {expired_count} temp keys")

                # Memory defragmentation (Redis 6.0+)
                try:
                    r.memory_doctor()
                    optimizations.append("Memory analysis completed")
                except redis.ResponseError:
                    pass  # Feature not available

                # Clean old cache entries
                cleaned_keys = []
                for pattern in ["cache:temp:*", "session:expired:*", "lock:*"]:
                    keys = list(r.scan_iter(match=pattern, count=100))
                    if keys:
                        r.delete(*keys)
                        cleaned_keys.extend(keys)

                if cleaned_keys:
                    optimizations.append(
                        f"Cleaned {len(cleaned_keys)} old cache entries"
                    )

                return MaintenanceTask(
                    task_name="redis_cache_optimization",
                    status="success",
                    message=f"Redis optimization completed. {len(optimizations)} optimizations applied",
                    execution_time=time.time() - start_time,
                    metrics={
                        "used_memory_bytes": used_memory,
                        "max_memory_bytes": max_memory,
                        "memory_usage_percent": (
                            (used_memory / max_memory * 100) if max_memory > 0 else 0
                        ),
                        "optimizations": optimizations,
                    },
                )
            else:
                return MaintenanceTask(
                    task_name="redis_cache_optimization",
                    status="success",
                    message="Redis cache optimization simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="redis_cache_optimization",
                status="failed",
                message=f"Redis cache optimization failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _file_cache_cleanup(self) -> MaintenanceTask:
        """Clean up file-based caches."""
        start_time = time.time()

        try:
            cache_dirs = [
                self.config.DATA_DIR / "cache",
                self.config.DATA_DIR / "temp",
                Path("/tmp") / "ai_pdf_scholar_cache",
            ]

            total_cleaned = 0
            total_space_freed = 0

            for cache_dir in cache_dirs:
                if not cache_dir.exists():
                    continue

                # Clean files older than 24 hours
                cutoff_time = time.time() - (24 * 60 * 60)

                for cache_file in cache_dir.rglob("*"):
                    if (
                        cache_file.is_file()
                        and cache_file.stat().st_mtime < cutoff_time
                    ):
                        if not self.config.DRY_RUN:
                            file_size = cache_file.stat().st_size
                            cache_file.unlink()
                            total_space_freed += file_size
                            total_cleaned += 1
                        else:
                            total_cleaned += 1

            if total_cleaned > 0:
                return MaintenanceTask(
                    task_name="file_cache_cleanup",
                    status="success",
                    message=f"Cleaned up {total_cleaned} cache files. Space freed: {total_space_freed // (1024*1024)} MB",
                    execution_time=time.time() - start_time,
                    metrics={
                        "files_cleaned": total_cleaned,
                        "space_freed_bytes": total_space_freed,
                    },
                )
            else:
                return MaintenanceTask(
                    task_name="file_cache_cleanup",
                    status="skipped",
                    message="No cache files to clean up",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="file_cache_cleanup",
                status="failed",
                message=f"File cache cleanup failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _cache_warming(self) -> MaintenanceTask:
        """Warm up caches with frequently accessed data."""
        start_time = time.time()

        try:
            if self.config.DRY_RUN:
                return MaintenanceTask(
                    task_name="cache_warming",
                    status="success",
                    message="Cache warming simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

            warmed_items = 0

            # Warm up database query cache
            try:
                db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"
                if db_path.exists():
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.cursor()

                        # Pre-load frequently accessed queries
                        common_queries = [
                            "SELECT COUNT(*) FROM documents",
                            "SELECT * FROM documents ORDER BY created_at DESC LIMIT 10",
                            "SELECT * FROM settings",
                        ]

                        for query in common_queries:
                            try:
                                cursor.execute(query)
                                cursor.fetchall()
                                warmed_items += 1
                            except sqlite3.Error:
                                continue
            except Exception:
                pass

            # Warm up Redis cache with popular data
            try:
                r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=5)
                r.ping()

                # Pre-cache some common configuration
                cache_items = {
                    "system:version": "2.1.0",
                    "system:features": "rag,upload,query,indexing",
                    "maintenance:last_run": datetime.now().isoformat(),
                }

                for key, value in cache_items.items():
                    r.setex(key, 3600, value)  # 1 hour TTL
                    warmed_items += 1

            except (redis.ConnectionError, redis.TimeoutError):
                pass

            return MaintenanceTask(
                task_name="cache_warming",
                status="success",
                message=f"Cache warming completed. {warmed_items} items preloaded",
                execution_time=time.time() - start_time,
                metrics={"warmed_items": warmed_items},
            )

        except Exception as e:
            return MaintenanceTask(
                task_name="cache_warming",
                status="failed",
                message=f"Cache warming failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    # ============================================================================
    # Storage Maintenance
    # ============================================================================

    def _storage_maintenance(self) -> list[MaintenanceTask]:
        """Perform storage maintenance operations."""
        tasks = []

        # Task 1: Disk cleanup
        tasks.append(self._disk_cleanup())

        # Task 2: Directory organization
        tasks.append(self._directory_organization())

        return tasks

    def _disk_cleanup(self) -> MaintenanceTask:
        """Perform disk cleanup operations."""
        start_time = time.time()

        try:
            disk_usage = psutil.disk_usage("/")
            usage_percent = (disk_usage.used / disk_usage.total) * 100

            if (
                usage_percent < self.config.DISK_CLEANUP_THRESHOLD
                and not self.config.FORCE_MAINTENANCE
            ):
                return MaintenanceTask(
                    task_name="disk_cleanup",
                    status="skipped",
                    message=f"Disk usage ({usage_percent:.1f}%) below threshold ({self.config.DISK_CLEANUP_THRESHOLD}%)",
                    execution_time=time.time() - start_time,
                    metrics={"disk_usage_percent": usage_percent},
                )

            total_freed = 0
            cleanup_actions = []

            if not self.config.DRY_RUN:
                # Clean temporary files
                temp_dirs = ["/tmp", "/var/tmp", str(self.config.DATA_DIR / "temp")]

                for temp_dir in temp_dirs:
                    temp_path = Path(temp_dir)
                    if temp_path.exists():
                        for temp_file in temp_path.glob("*ai_pdf_scholar*"):
                            if temp_file.is_file():
                                try:
                                    if (
                                        temp_file.stat().st_mtime < time.time() - 86400
                                    ):  # 24 hours
                                        file_size = temp_file.stat().st_size
                                        temp_file.unlink()
                                        total_freed += file_size
                                except Exception:
                                    continue

                cleanup_actions.append("Cleaned temporary files")

                # Clean package caches (if available)
                try:
                    result = subprocess.run(
                        ["apt-get", "autoremove", "-y"],
                        capture_output=True,
                        timeout=300,
                    )
                    if result.returncode == 0:
                        cleanup_actions.append("Removed unused packages")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

                try:
                    result = subprocess.run(
                        ["apt-get", "autoclean"], capture_output=True, timeout=120
                    )
                    if result.returncode == 0:
                        cleanup_actions.append("Cleaned package cache")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

            else:
                cleanup_actions = ["Disk cleanup simulated (dry run)"]

            return MaintenanceTask(
                task_name="disk_cleanup",
                status="success",
                message=f"Disk cleanup completed. Actions: {', '.join(cleanup_actions)}. Space freed: {total_freed // (1024*1024)} MB",
                execution_time=time.time() - start_time,
                metrics={
                    "space_freed_bytes": total_freed,
                    "cleanup_actions": cleanup_actions,
                    "disk_usage_percent": usage_percent,
                },
            )

        except Exception as e:
            return MaintenanceTask(
                task_name="disk_cleanup",
                status="failed",
                message=f"Disk cleanup failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _directory_organization(self) -> MaintenanceTask:
        """Organize and clean up directory structure."""
        start_time = time.time()

        try:
            # Ensure required directories exist
            required_dirs = [
                self.config.DATA_DIR / "uploads",
                self.config.DATA_DIR / "vector_indexes",
                self.config.DATA_DIR / "vector_indexes" / "active",
                self.config.DATA_DIR / "vector_indexes" / "backup",
                self.config.DATA_DIR / "cache",
                self.config.DATA_DIR / "logs",
                self.config.DATA_DIR / "backups",
            ]

            created_dirs = []
            organized_items = 0

            if not self.config.DRY_RUN:
                for required_dir in required_dirs:
                    if not required_dir.exists():
                        required_dir.mkdir(parents=True, exist_ok=True)
                        created_dirs.append(str(required_dir))

                # Move misplaced files to correct locations
                if self.config.DATA_DIR.exists():
                    for item in self.config.DATA_DIR.iterdir():
                        if item.is_file():
                            # Move log files to logs directory
                            if item.suffix in [".log", ".out"]:
                                log_dir = self.config.DATA_DIR / "logs"
                                log_dir.mkdir(exist_ok=True)
                                item.rename(log_dir / item.name)
                                organized_items += 1

                            # Move backup files to backups directory
                            elif "backup" in item.name.lower():
                                backup_dir = self.config.DATA_DIR / "backups"
                                backup_dir.mkdir(exist_ok=True)
                                item.rename(backup_dir / item.name)
                                organized_items += 1

            message_parts = []
            if created_dirs:
                message_parts.append(f"Created {len(created_dirs)} directories")
            if organized_items > 0:
                message_parts.append(f"Organized {organized_items} misplaced files")

            if not message_parts:
                message = "Directory structure already organized"
                status = "skipped"
            else:
                message = (
                    f"Directory organization completed. {', '.join(message_parts)}"
                )
                status = "success"

            return MaintenanceTask(
                task_name="directory_organization",
                status=status,
                message=message,
                execution_time=time.time() - start_time,
                metrics={
                    "directories_created": len(created_dirs),
                    "files_organized": organized_items,
                    "created_directories": created_dirs,
                },
            )

        except Exception as e:
            return MaintenanceTask(
                task_name="directory_organization",
                status="failed",
                message=f"Directory organization failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    # ============================================================================
    # Performance Maintenance
    # ============================================================================

    def _performance_maintenance(self) -> list[MaintenanceTask]:
        """Perform performance maintenance operations."""
        tasks = []

        # Task 1: Performance baseline update
        tasks.append(self._performance_baseline_update())

        # Task 2: Index optimization
        tasks.append(self._index_optimization())

        return tasks

    def _performance_baseline_update(self) -> MaintenanceTask:
        """Update performance baselines."""
        start_time = time.time()

        try:
            if not self.config.UPDATE_BASELINES and not self.config.FORCE_MAINTENANCE:
                return MaintenanceTask(
                    task_name="performance_baseline_update",
                    status="skipped",
                    message="Performance baseline updates disabled",
                    execution_time=time.time() - start_time,
                )

            if not self.config.DRY_RUN:
                baseline_data = {
                    "timestamp": datetime.now().isoformat(),
                    "system_metrics": self._capture_system_metrics(),
                    "database_performance": {},
                    "cache_performance": {},
                }

                # Database performance baseline
                db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"
                if db_path.exists():
                    db_start = time.time()
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM documents")
                        document_count = cursor.fetchone()[0]

                        cursor.execute(
                            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                        )
                        table_count = cursor.fetchone()[0]

                    db_time = time.time() - db_start
                    baseline_data["database_performance"] = {
                        "connection_time_ms": db_time * 1000,
                        "document_count": document_count,
                        "table_count": table_count,
                    }

                # Save baseline data
                baseline_dir = self.config.DATA_DIR / "baselines"
                baseline_dir.mkdir(exist_ok=True)

                baseline_file = (
                    baseline_dir
                    / f"performance_baseline_{datetime.now().strftime('%Y%m%d')}.json"
                )
                with open(baseline_file, "w") as f:
                    json.dump(baseline_data, f, indent=2)

                return MaintenanceTask(
                    task_name="performance_baseline_update",
                    status="success",
                    message=f"Performance baseline updated: {baseline_file.name}",
                    execution_time=time.time() - start_time,
                    metrics=baseline_data,
                )
            else:
                return MaintenanceTask(
                    task_name="performance_baseline_update",
                    status="success",
                    message="Performance baseline update simulated (dry run)",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="performance_baseline_update",
                status="failed",
                message=f"Performance baseline update failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _index_optimization(self) -> MaintenanceTask:
        """Optimize database indexes and vector indexes."""
        start_time = time.time()

        try:
            optimizations = []

            if not self.config.DRY_RUN:
                # Database index optimization
                db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"
                if db_path.exists():
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.cursor()

                        # Reindex all indexes
                        cursor.execute("REINDEX")
                        optimizations.append("Database indexes reindexed")

                # Vector index optimization
                vector_dir = self.config.DATA_DIR / "vector_indexes"
                if vector_dir.exists():
                    # Clean up orphaned vector index files
                    active_dir = vector_dir / "active"
                    if active_dir.exists():
                        # This would integrate with your vector index management
                        # For now, we'll just count the indexes
                        index_count = len(list(active_dir.glob("*.index")))
                        if index_count > 0:
                            optimizations.append(
                                f"Verified {index_count} vector indexes"
                            )

            if optimizations:
                return MaintenanceTask(
                    task_name="index_optimization",
                    status="success",
                    message=f"Index optimization completed. {', '.join(optimizations)}",
                    execution_time=time.time() - start_time,
                    metrics={"optimizations": optimizations},
                )
            else:
                return MaintenanceTask(
                    task_name="index_optimization",
                    status="skipped",
                    message="No indexes to optimize",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="index_optimization",
                status="failed",
                message=f"Index optimization failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    # ============================================================================
    # Security Maintenance
    # ============================================================================

    def _security_maintenance(self) -> list[MaintenanceTask]:
        """Perform security maintenance operations."""
        tasks = []

        # Task 1: Permission audit
        tasks.append(self._permission_audit())

        # Task 2: Secret rotation check
        tasks.append(self._secret_rotation_check())

        return tasks

    def _permission_audit(self) -> MaintenanceTask:
        """Audit file and directory permissions."""
        start_time = time.time()

        try:
            issues = []
            checked_paths = []

            # Check critical application directories
            critical_paths = [
                self.config.DATA_DIR,
                self.config.DATA_DIR / "uploads",
                self.config.DATA_DIR / "backups",
                self.config.DATA_DIR / "logs",
            ]

            for path in critical_paths:
                if path.exists():
                    stat_info = path.stat()
                    permissions = oct(stat_info.st_mode)[-3:]

                    checked_paths.append(
                        {
                            "path": str(path),
                            "permissions": permissions,
                            "owner_readable": os.access(path, os.R_OK),
                            "owner_writable": os.access(path, os.W_OK),
                        }
                    )

                    # Check for overly permissive permissions
                    if permissions in ["777", "666"]:
                        issues.append(
                            f"{path}: Overly permissive permissions ({permissions})"
                        )

                    # Check for non-readable critical directories
                    if not os.access(path, os.R_OK):
                        issues.append(f"{path}: Not readable")

            if issues:
                return MaintenanceTask(
                    task_name="permission_audit",
                    status="warning",
                    message=f"Permission audit found {len(issues)} issues",
                    execution_time=time.time() - start_time,
                    details={"issues": issues, "checked_paths": checked_paths},
                )
            else:
                return MaintenanceTask(
                    task_name="permission_audit",
                    status="success",
                    message=f"Permission audit completed. {len(checked_paths)} paths checked, no issues found",
                    execution_time=time.time() - start_time,
                    metrics={"checked_paths": checked_paths},
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="permission_audit",
                status="failed",
                message=f"Permission audit failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _secret_rotation_check(self) -> MaintenanceTask:
        """Check if secrets need rotation."""
        start_time = time.time()

        try:
            # This would integrate with your secrets management system
            # For now, we'll do a basic check

            rotation_needed = []

            # Check environment variables for API keys
            sensitive_env_vars = [
                "GEMINI_API_KEY",
                "DATABASE_PASSWORD",
                "SECRET_KEY",
                "JWT_SECRET",
            ]

            for env_var in sensitive_env_vars:
                if env_var in os.environ:
                    # Basic check - in production, you'd check actual rotation dates
                    rotation_needed.append(f"{env_var}: Consider rotation")

            if rotation_needed:
                return MaintenanceTask(
                    task_name="secret_rotation_check",
                    status="warning",
                    message=f"Secret rotation check found {len(rotation_needed)} items for review",
                    execution_time=time.time() - start_time,
                    details={"rotation_candidates": rotation_needed},
                )
            else:
                return MaintenanceTask(
                    task_name="secret_rotation_check",
                    status="success",
                    message="Secret rotation check completed, no immediate rotation needed",
                    execution_time=time.time() - start_time,
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="secret_rotation_check",
                status="failed",
                message=f"Secret rotation check failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    # ============================================================================
    # Health Verification
    # ============================================================================

    def _health_verification(self) -> list[MaintenanceTask]:
        """Perform final health verification."""
        tasks = []

        # Task 1: System health check
        tasks.append(self._system_health_check())

        # Task 2: Service health check
        tasks.append(self._service_health_check())

        return tasks

    def _system_health_check(self) -> MaintenanceTask:
        """Verify system health post-maintenance."""
        start_time = time.time()

        try:
            health_checks = []
            warnings = []

            # Memory check
            memory = psutil.virtual_memory()
            if memory.percent < 90:
                health_checks.append(f"Memory usage: {memory.percent:.1f}% (healthy)")
            else:
                warnings.append(f"High memory usage: {memory.percent:.1f}%")

            # Disk check
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent < 85:
                health_checks.append(f"Disk usage: {disk_percent:.1f}% (healthy)")
            else:
                warnings.append(f"High disk usage: {disk_percent:.1f}%")

            # CPU check
            cpu_percent = psutil.cpu_percent(interval=2)
            if cpu_percent < 80:
                health_checks.append(f"CPU usage: {cpu_percent:.1f}% (healthy)")
            else:
                warnings.append(f"High CPU usage: {cpu_percent:.1f}%")

            if warnings:
                return MaintenanceTask(
                    task_name="system_health_check",
                    status="warning",
                    message=f"System health check completed with {len(warnings)} warnings",
                    execution_time=time.time() - start_time,
                    details={"health_checks": health_checks, "warnings": warnings},
                )
            else:
                return MaintenanceTask(
                    task_name="system_health_check",
                    status="success",
                    message=f"System health check passed all {len(health_checks)} checks",
                    execution_time=time.time() - start_time,
                    metrics={"health_checks": health_checks},
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="system_health_check",
                status="failed",
                message=f"System health check failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    def _service_health_check(self) -> MaintenanceTask:
        """Verify service health post-maintenance."""
        start_time = time.time()

        try:
            service_checks = []
            issues = []

            # Database connectivity test
            db_path = self.config.DATA_DIR / "ai_pdf_scholar.db"
            if db_path.exists():
                try:
                    with sqlite3.connect(str(db_path)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                    service_checks.append("Database: Connected")
                except Exception as e:
                    issues.append(f"Database: Connection failed - {str(e)}")
            else:
                issues.append("Database: File not found")

            # Redis connectivity test
            try:
                r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=5)
                r.ping()
                service_checks.append("Redis: Connected")
            except (redis.ConnectionError, redis.TimeoutError):
                issues.append("Redis: Connection failed")

            # File system access test
            try:
                test_file = self.config.DATA_DIR / "health_test.tmp"
                test_file.write_text("health_check")
                test_content = test_file.read_text()
                test_file.unlink()

                if test_content == "health_check":
                    service_checks.append("File System: Read/write OK")
                else:
                    issues.append("File System: Read/write test failed")
            except Exception as e:
                issues.append(f"File System: Access test failed - {str(e)}")

            if issues:
                return MaintenanceTask(
                    task_name="service_health_check",
                    status="warning",
                    message=f"Service health check found {len(issues)} issues",
                    execution_time=time.time() - start_time,
                    details={"service_checks": service_checks, "issues": issues},
                )
            else:
                return MaintenanceTask(
                    task_name="service_health_check",
                    status="success",
                    message=f"Service health check passed all {len(service_checks)} checks",
                    execution_time=time.time() - start_time,
                    metrics={"service_checks": service_checks},
                )

        except Exception as e:
            return MaintenanceTask(
                task_name="service_health_check",
                status="failed",
                message=f"Service health check failed: {str(e)}",
                execution_time=time.time() - start_time,
            )

    # ============================================================================
    # Reporting and Recommendations
    # ============================================================================

    def _generate_recommendations(self) -> list[str]:
        """Generate maintenance recommendations based on task results."""
        recommendations = []

        # Analyze task results for patterns
        failed_tasks = [t for t in self.tasks_completed if t.status == "failed"]
        warning_tasks = [t for t in self.tasks_completed if t.status == "warning"]

        if failed_tasks:
            recommendations.append(f"Review and retry {len(failed_tasks)} failed tasks")

        if warning_tasks:
            recommendations.append(
                f"Investigate {len(warning_tasks)} tasks with warnings"
            )

        # Resource-based recommendations
        current_metrics = self._capture_system_metrics()

        if current_metrics.get("memory_usage_percent", 0) > 80:
            recommendations.append(
                "Consider increasing memory or optimizing memory usage"
            )

        if current_metrics.get("disk_usage_percent", 0) > 85:
            recommendations.append(
                "Increase disk space or implement more aggressive cleanup policies"
            )

        # Task-specific recommendations
        for task in self.tasks_completed:
            if task.task_name == "database_vacuum" and task.status == "success":
                if (
                    task.metrics
                    and task.metrics.get("space_saved_bytes", 0) > 100 * 1024 * 1024
                ):  # 100MB
                    recommendations.append(
                        "Database had significant fragmentation - consider more frequent VACUUM operations"
                    )

            elif task.task_name == "log_cleanup" and task.status == "success":
                if task.metrics and task.metrics.get("files_deleted", 0) > 100:
                    recommendations.append(
                        "Large number of old log files - consider adjusting log retention policies"
                    )

        # Maintenance frequency recommendations
        total_tasks = len(self.tasks_completed)
        successful_tasks = len(
            [t for t in self.tasks_completed if t.status == "success"]
        )

        if successful_tasks / total_tasks > 0.9:
            recommendations.append(
                "System maintenance is working well - continue current schedule"
            )
        else:
            recommendations.append(
                "Consider increasing maintenance frequency or investigating recurring issues"
            )

        return recommendations


# ============================================================================
# Report Formatting
# ============================================================================


class MaintenanceReportFormatter:
    """Format maintenance reports for different outputs."""

    @staticmethod
    def format_report(report: MaintenanceReport, format_type: str = "text") -> str:
        """Format maintenance report."""

        if format_type.lower() == "json":
            return MaintenanceReportFormatter._format_json(report)
        elif format_type.lower() == "html":
            return MaintenanceReportFormatter._format_html(report)
        else:
            return MaintenanceReportFormatter._format_text(report)

    @staticmethod
    def _format_text(report: MaintenanceReport) -> str:
        """Format as text report."""
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("AI PDF SCHOLAR - SYSTEM MAINTENANCE REPORT")
        lines.append("=" * 60)
        lines.append(f"Start Time: {report.start_time}")
        lines.append(f"End Time: {report.end_time}")
        lines.append(f"Duration: {report.total_duration:.2f} seconds")
        lines.append("")

        # Summary
        total_tasks = len(report.tasks_completed)
        successful = len([t for t in report.tasks_completed if t.status == "success"])
        failed = len([t for t in report.tasks_completed if t.status == "failed"])
        warnings = len([t for t in report.tasks_completed if t.status == "warning"])
        skipped = len([t for t in report.tasks_completed if t.status == "skipped"])

        lines.append("SUMMARY")
        lines.append("-" * 20)
        lines.append(f"Total Tasks: {total_tasks}")
        lines.append(f"Successful: {successful}")
        lines.append(f"Failed: {failed}")
        lines.append(f"Warnings: {warnings}")
        lines.append(f"Skipped: {skipped}")
        lines.append("")

        # Task Details
        lines.append("TASK DETAILS")
        lines.append("-" * 20)

        for task in report.tasks_completed:
            status_indicator = {
                "success": "✓",
                "failed": "✗",
                "warning": "⚠",
                "skipped": "○",
            }.get(task.status, "?")

            lines.append(
                f"{status_indicator} {task.task_name.replace('_', ' ').title()}"
            )
            lines.append(f"  Status: {task.status.upper()}")
            lines.append(f"  Message: {task.message}")
            lines.append(f"  Duration: {task.execution_time:.2f}s")

            if task.metrics:
                lines.append("  Metrics:")
                for key, value in task.metrics.items():
                    lines.append(f"    {key}: {value}")

            lines.append("")

        # System Metrics Comparison
        if report.system_metrics_before and report.system_metrics_after:
            lines.append("SYSTEM METRICS COMPARISON")
            lines.append("-" * 30)

            metrics_to_compare = [
                "memory_usage_percent",
                "disk_usage_percent",
                "cpu_usage_percent",
            ]

            for metric in metrics_to_compare:
                before = report.system_metrics_before.get(metric, 0)
                after = report.system_metrics_after.get(metric, 0)
                change = after - before

                change_indicator = "↑" if change > 0 else "↓" if change < 0 else "→"
                lines.append(
                    f"{metric.replace('_', ' ').title()}: {before:.1f}% {change_indicator} {after:.1f}% ({change:+.1f}%)"
                )

            lines.append("")

        # Recommendations
        if report.recommendations:
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 20)
            for i, recommendation in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {recommendation}")
            lines.append("")

        lines.append("=" * 60)
        lines.append("Report generated by AI PDF Scholar Maintenance System")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def _format_json(report: MaintenanceReport) -> str:
        """Format as JSON."""
        return json.dumps(asdict(report), indent=2, default=str)

    @staticmethod
    def _format_html(report: MaintenanceReport) -> str:
        """Format as HTML report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>System Maintenance Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .summary {{ background: #e7f3ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .task {{ margin: 10px 0; padding: 10px; border-left: 4px solid #ddd; }}
        .task.success {{ border-left-color: #28a745; }}
        .task.failed {{ border-left-color: #dc3545; }}
        .task.warning {{ border-left-color: #ffc107; }}
        .task.skipped {{ border-left-color: #6c757d; }}
        .metrics {{ background: #f8f9fa; padding: 10px; margin: 10px 0; font-size: 0.9em; }}
        .recommendations {{ background: #fff3cd; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AI PDF Scholar - System Maintenance Report</h1>
        <p><strong>Start Time:</strong> {report.start_time}</p>
        <p><strong>End Time:</strong> {report.end_time}</p>
        <p><strong>Duration:</strong> {report.total_duration:.2f} seconds</p>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Tasks:</strong> {len(report.tasks_completed)}</p>
        <p><strong>Successful:</strong> {len([t for t in report.tasks_completed if t.status == "success"])}</p>
        <p><strong>Failed:</strong> {len([t for t in report.tasks_completed if t.status == "failed"])}</p>
        <p><strong>Warnings:</strong> {len([t for t in report.tasks_completed if t.status == "warning"])}</p>
        <p><strong>Skipped:</strong> {len([t for t in report.tasks_completed if t.status == "skipped"])}</p>
    </div>

    <h2>Task Details</h2>
"""

        for task in report.tasks_completed:
            status_symbols = {
                "success": "✓",
                "failed": "✗",
                "warning": "⚠",
                "skipped": "○",
            }

            html += f"""
    <div class="task {task.status}">
        <h3>{status_symbols.get(task.status, '?')} {task.task_name.replace('_', ' ').title()}</h3>
        <p><strong>Status:</strong> {task.status.upper()}</p>
        <p><strong>Message:</strong> {task.message}</p>
        <p><strong>Duration:</strong> {task.execution_time:.2f}s</p>
"""

            if task.metrics:
                html += '<div class="metrics"><strong>Metrics:</strong><ul>'
                for key, value in task.metrics.items():
                    html += f"<li>{key}: {value}</li>"
                html += "</ul></div>"

            html += "</div>"

        if report.recommendations:
            html += '<div class="recommendations"><h2>Recommendations</h2><ol>'
            for recommendation in report.recommendations:
                html += f"<li>{recommendation}</li>"
            html += "</ol></div>"

        html += """
</body>
</html>
"""

        return html


# ============================================================================
# Main CLI Interface
# ============================================================================


def main() -> Any:
    """Main CLI interface for system maintenance."""
    parser = argparse.ArgumentParser(
        description="Automated System Maintenance for AI Enhanced PDF Scholar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all maintenance tasks
  python system_maintenance.py

  # Run specific maintenance types
  python system_maintenance.py --tasks database,cache,logs

  # Dry run to see what would be done
  python system_maintenance.py --dry-run

  # Force maintenance regardless of thresholds
  python system_maintenance.py --force

  # Generate HTML report
  python system_maintenance.py --format html --output maintenance_report.html
        """,
    )

    parser.add_argument(
        "--tasks",
        help="Comma-separated list of maintenance types: database,logs,cache,storage,performance,security,health_checks",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force maintenance regardless of thresholds",
    )

    parser.add_argument(
        "--format",
        choices=["text", "json", "html"],
        default="text",
        help="Report output format. Default: text",
    )

    parser.add_argument(
        "--output", help="Output file path. If not specified, prints to stdout"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Set environment variables based on args
    if args.dry_run:
        os.environ["MAINTENANCE_DRY_RUN"] = "true"

    if args.force:
        os.environ["FORCE_MAINTENANCE"] = "true"

    # Parse task types
    task_types = None
    if args.tasks:
        task_types = [t.strip() for t in args.tasks.split(",")]

    try:
        # Initialize maintenance engine
        engine = SystemMaintenanceEngine()

        logger.info("Starting automated system maintenance")

        # Run maintenance
        report = engine.run_maintenance(task_types=task_types)

        # Format report
        formatted_report = MaintenanceReportFormatter.format_report(report, args.format)

        # Output report
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(formatted_report)

            logger.info(f"Maintenance report saved to: {output_path}")
        else:
            print(formatted_report)

        # Return appropriate exit code
        failed_tasks = [t for t in report.tasks_completed if t.status == "failed"]
        return 1 if failed_tasks else 0

    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
