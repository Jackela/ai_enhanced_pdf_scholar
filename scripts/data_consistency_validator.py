#!/usr/bin/env python3
"""
Data Consistency Validator
Validates data integrity and consistency after disaster recovery operations.
Supports database, file system, and application-level consistency checks.
"""

import asyncio
import hashlib
import json
import logging
import os

# Add backend to path for imports
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import aiofiles
from sqlalchemy import create_engine, text

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from backend.core.secrets import get_secrets_manager
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class ConsistencyLevel(str, Enum):
    """Data consistency validation levels."""

    BASIC = "basic"  # Basic existence and access checks
    STRUCTURAL = "structural"  # Schema and structure validation
    CONTENT = "content"  # Content hash validation
    REFERENTIAL = "referential"  # Referential integrity checks
    COMPREHENSIVE = "comprehensive"  # All checks combined


class ValidationResult(str, Enum):
    """Validation result status."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class ValidationCheck:
    """Individual validation check definition."""

    check_id: str
    name: str
    description: str
    consistency_level: ConsistencyLevel
    check_type: str  # 'database', 'file_system', 'application'
    timeout_seconds: int = 300
    critical: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    """Result of an individual validation check."""

    check_id: str
    result: ValidationResult
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Comprehensive validation report."""

    validation_id: str
    start_time: datetime
    end_time: datetime | None = None
    total_duration: float = 0.0
    consistency_level: ConsistencyLevel

    # Results summary
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    skipped_checks: int = 0
    error_checks: int = 0

    # Check results
    check_results: list[CheckResult] = field(default_factory=list)

    # Overall status
    overall_status: ValidationResult = ValidationResult.FAILED
    critical_failures: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)


class DatabaseConsistencyValidator:
    """Database-specific consistency validation."""

    def __init__(self, connection_url: str):
        """Initialize database validator."""
        self.connection_url = connection_url
        self.engine = create_engine(connection_url)

    async def validate_basic_connectivity(self) -> CheckResult:
        """Test basic database connectivity."""
        check_result = CheckResult(
            check_id="db_connectivity",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            with self.engine.connect() as conn:
                # Simple connectivity test
                result = conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    check_result.result = ValidationResult.PASSED
                    check_result.message = "Database connectivity successful"
                else:
                    check_result.message = "Database connectivity test failed"

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Database connectivity error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result

    async def validate_schema_integrity(
        self, expected_tables: list[str]
    ) -> CheckResult:
        """Validate database schema integrity."""
        check_result = CheckResult(
            check_id="db_schema_integrity",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            with self.engine.connect() as conn:
                # Get list of tables
                if "postgresql" in self.connection_url:
                    result = conn.execute(
                        text(
                            """
                        SELECT table_name FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    """
                        )
                    )
                elif "sqlite" in self.connection_url:
                    result = conn.execute(
                        text(
                            """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    """
                        )
                    )
                else:
                    raise ValueError("Unsupported database type")

                actual_tables = set(row[0] for row in result.fetchall())
                expected_tables_set = set(expected_tables)

                missing_tables = expected_tables_set - actual_tables
                extra_tables = actual_tables - expected_tables_set

                if missing_tables:
                    check_result.result = ValidationResult.FAILED
                    check_result.message = (
                        f"Missing tables: {', '.join(missing_tables)}"
                    )
                    check_result.details["missing_tables"] = list(missing_tables)
                elif extra_tables:
                    check_result.result = ValidationResult.WARNING
                    check_result.message = (
                        f"Extra tables found: {', '.join(extra_tables)}"
                    )
                    check_result.details["extra_tables"] = list(extra_tables)
                else:
                    check_result.result = ValidationResult.PASSED
                    check_result.message = "All expected tables present"

                check_result.details["actual_tables"] = list(actual_tables)
                check_result.details["expected_tables"] = expected_tables

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Schema validation error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result

    async def validate_referential_integrity(self) -> CheckResult:
        """Validate referential integrity constraints."""
        check_result = CheckResult(
            check_id="db_referential_integrity",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            with self.engine.connect() as conn:
                integrity_issues = []

                # Check for orphaned records (example for common tables)
                # This would be customized for specific application schema

                # Example: Check for documents without valid library references
                try:
                    result = conn.execute(
                        text(
                            """
                        SELECT COUNT(*) FROM documents d
                        LEFT JOIN document_library dl ON d.library_id = dl.id
                        WHERE d.library_id IS NOT NULL AND dl.id IS NULL
                    """
                        )
                    )
                    orphaned_docs = result.scalar()

                    if orphaned_docs > 0:
                        integrity_issues.append(
                            f"Found {orphaned_docs} orphaned documents"
                        )

                except Exception as e:
                    # Table might not exist, which is fine for this check
                    logger.debug(f"Document referential integrity check skipped: {e}")

                # Example: Check for vector indexes without documents
                try:
                    result = conn.execute(
                        text(
                            """
                        SELECT COUNT(*) FROM vector_indexes vi
                        LEFT JOIN documents d ON vi.document_id = d.id
                        WHERE vi.document_id IS NOT NULL AND d.id IS NULL
                    """
                        )
                    )
                    orphaned_vectors = result.scalar()

                    if orphaned_vectors > 0:
                        integrity_issues.append(
                            f"Found {orphaned_vectors} orphaned vector indexes"
                        )

                except Exception as e:
                    logger.debug(
                        f"Vector index referential integrity check skipped: {e}"
                    )

                if integrity_issues:
                    check_result.result = ValidationResult.FAILED
                    check_result.message = "; ".join(integrity_issues)
                    check_result.details["integrity_issues"] = integrity_issues
                else:
                    check_result.result = ValidationResult.PASSED
                    check_result.message = "No referential integrity issues found"

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Referential integrity check error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result

    async def validate_data_counts(
        self, expected_counts: dict[str, int]
    ) -> CheckResult:
        """Validate expected data counts in tables."""
        check_result = CheckResult(
            check_id="db_data_counts",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            with self.engine.connect() as conn:
                count_issues = []
                actual_counts = {}

                for table, expected_count in expected_counts.items():
                    try:
                        # Safe: table names are from admin configuration, not user input
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        actual_count = result.scalar()
                        actual_counts[table] = actual_count

                        if actual_count < expected_count:
                            count_issues.append(
                                f"Table {table}: expected >= {expected_count}, got {actual_count}"
                            )
                    except Exception as e:
                        count_issues.append(
                            f"Table {table}: count check failed - {str(e)}"
                        )

                check_result.details["actual_counts"] = actual_counts
                check_result.details["expected_counts"] = expected_counts

                if count_issues:
                    check_result.result = ValidationResult.FAILED
                    check_result.message = "; ".join(count_issues)
                    check_result.details["count_issues"] = count_issues
                else:
                    check_result.result = ValidationResult.PASSED
                    check_result.message = "All table counts meet expectations"

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Data count validation error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result


class FileSystemConsistencyValidator:
    """File system consistency validation."""

    def __init__(self, base_paths: list[str]):
        """Initialize file system validator."""
        self.base_paths = [Path(p) for p in base_paths]

    async def validate_path_accessibility(self) -> CheckResult:
        """Validate that all base paths are accessible."""
        check_result = CheckResult(
            check_id="fs_path_accessibility",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            inaccessible_paths = []
            accessible_paths = []

            for path in self.base_paths:
                try:
                    if path.exists() and path.is_dir():
                        # Test read access
                        list(path.iterdir())
                        accessible_paths.append(str(path))
                    else:
                        inaccessible_paths.append(f"{path} (does not exist)")
                except PermissionError:
                    inaccessible_paths.append(f"{path} (permission denied)")
                except Exception as e:
                    inaccessible_paths.append(f"{path} ({str(e)})")

            check_result.details["accessible_paths"] = accessible_paths
            check_result.details["inaccessible_paths"] = inaccessible_paths

            if inaccessible_paths:
                check_result.result = ValidationResult.FAILED
                check_result.message = (
                    f"Inaccessible paths: {', '.join(inaccessible_paths)}"
                )
            else:
                check_result.result = ValidationResult.PASSED
                check_result.message = "All paths accessible"

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Path accessibility check error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result

    async def validate_file_integrity(
        self, checksum_file: str | None = None, sample_size: int = 100
    ) -> CheckResult:
        """Validate file integrity using checksums."""
        check_result = CheckResult(
            check_id="fs_file_integrity",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            corrupted_files = []
            validated_files = []

            # Load expected checksums if available
            expected_checksums = {}
            if checksum_file and Path(checksum_file).exists():
                async with aiofiles.open(checksum_file) as f:
                    content = await f.read()
                    for line in content.strip().split("\n"):
                        if line and " " in line:
                            checksum, filepath = line.split(" ", 1)
                            expected_checksums[filepath] = checksum

            # Validate files
            files_checked = 0
            for base_path in self.base_paths:
                if not base_path.exists():
                    continue

                for file_path in base_path.rglob("*"):
                    if file_path.is_file() and files_checked < sample_size:
                        try:
                            # Calculate current checksum
                            current_checksum = await self._calculate_file_checksum(
                                file_path
                            )
                            relative_path = str(file_path.relative_to(base_path))

                            if relative_path in expected_checksums:
                                expected_checksum = expected_checksums[relative_path]
                                if current_checksum == expected_checksum:
                                    validated_files.append(relative_path)
                                else:
                                    corrupted_files.append(
                                        f"{relative_path} (checksum mismatch)"
                                    )
                            else:
                                # No expected checksum, just verify file is readable
                                validated_files.append(relative_path)

                            files_checked += 1

                        except Exception as e:
                            corrupted_files.append(
                                f"{relative_path} (read error: {str(e)})"
                            )
                            files_checked += 1

            check_result.details["validated_files_count"] = len(validated_files)
            check_result.details["corrupted_files"] = corrupted_files
            check_result.details["files_checked"] = files_checked

            if corrupted_files:
                check_result.result = ValidationResult.FAILED
                check_result.message = f"Found {len(corrupted_files)} corrupted files"
            elif files_checked == 0:
                check_result.result = ValidationResult.SKIPPED
                check_result.message = "No files found to validate"
            else:
                check_result.result = ValidationResult.PASSED
                check_result.message = (
                    f"Validated {len(validated_files)} files successfully"
                )

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"File integrity check error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result

    async def validate_directory_structure(
        self, expected_structure: dict[str, Any]
    ) -> CheckResult:
        """Validate expected directory structure exists."""
        check_result = CheckResult(
            check_id="fs_directory_structure",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            missing_directories = []
            found_directories = []

            def check_structure(
                base_path: Path, structure: dict[str, Any], current_path: str = ""
            ):
                for name, content in structure.items():
                    full_path = (
                        base_path / name
                        if current_path == ""
                        else base_path / current_path / name
                    )

                    if full_path.exists() and full_path.is_dir():
                        found_directories.append(str(full_path.relative_to(base_path)))

                        # Recursively check subdirectories
                        if isinstance(content, dict):
                            check_structure(
                                base_path,
                                content,
                                str(full_path.relative_to(base_path)),
                            )
                    else:
                        missing_directories.append(
                            str(full_path.relative_to(base_path))
                        )

            for base_path in self.base_paths:
                if base_path.exists():
                    check_structure(base_path, expected_structure)

            check_result.details["found_directories"] = found_directories
            check_result.details["missing_directories"] = missing_directories

            if missing_directories:
                check_result.result = ValidationResult.FAILED
                check_result.message = (
                    f"Missing directories: {', '.join(missing_directories)}"
                )
            else:
                check_result.result = ValidationResult.PASSED
                check_result.message = "All expected directories found"

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Directory structure check error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result

    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        hash_sha256 = hashlib.sha256()

        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)

        return hash_sha256.hexdigest()


class ApplicationConsistencyValidator:
    """Application-level consistency validation."""

    def __init__(self, application_config: dict[str, Any]):
        """Initialize application validator."""
        self.config = application_config

    async def validate_configuration_integrity(self) -> CheckResult:
        """Validate application configuration integrity."""
        check_result = CheckResult(
            check_id="app_config_integrity",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            config_issues = []

            # Check required configuration keys
            required_keys = self.config.get("required_keys", [])
            for key in required_keys:
                if key not in self.config:
                    config_issues.append(f"Missing required config key: {key}")

            # Check configuration file accessibility
            config_files = self.config.get("config_files", [])
            for config_file in config_files:
                config_path = Path(config_file)
                if not config_path.exists():
                    config_issues.append(f"Config file not found: {config_file}")
                elif not config_path.is_file():
                    config_issues.append(f"Config path is not a file: {config_file}")

            check_result.details["config_issues"] = config_issues

            if config_issues:
                check_result.result = ValidationResult.FAILED
                check_result.message = (
                    f"Configuration issues: {'; '.join(config_issues)}"
                )
            else:
                check_result.result = ValidationResult.PASSED
                check_result.message = "Configuration integrity validated"

        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Configuration integrity check error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result

    async def validate_service_health(self, health_endpoints: list[str]) -> CheckResult:
        """Validate service health endpoints."""
        check_result = CheckResult(
            check_id="app_service_health",
            result=ValidationResult.FAILED,
            start_time=datetime.utcnow(),
        )

        try:
            import aiohttp

            unhealthy_services = []
            healthy_services = []

            async with aiohttp.ClientSession() as session:
                for endpoint in health_endpoints:
                    try:
                        async with session.get(endpoint, timeout=10) as response:
                            if response.status == 200:
                                healthy_services.append(endpoint)
                            else:
                                unhealthy_services.append(
                                    f"{endpoint} (status: {response.status})"
                                )
                    except Exception as e:
                        unhealthy_services.append(f"{endpoint} (error: {str(e)})")

            check_result.details["healthy_services"] = healthy_services
            check_result.details["unhealthy_services"] = unhealthy_services

            if unhealthy_services:
                check_result.result = ValidationResult.FAILED
                check_result.message = (
                    f"Unhealthy services: {'; '.join(unhealthy_services)}"
                )
            elif not healthy_services:
                check_result.result = ValidationResult.SKIPPED
                check_result.message = "No health endpoints to check"
            else:
                check_result.result = ValidationResult.PASSED
                check_result.message = f"All {len(healthy_services)} services healthy"

        except ImportError:
            check_result.result = ValidationResult.SKIPPED
            check_result.message = "aiohttp not available for service health checks"
        except Exception as e:
            check_result.result = ValidationResult.ERROR
            check_result.message = f"Service health check error: {str(e)}"
            check_result.errors.append(str(e))

        check_result.end_time = datetime.utcnow()
        check_result.duration_seconds = (
            check_result.end_time - check_result.start_time
        ).total_seconds()

        return check_result


class DataConsistencyValidator:
    """Main data consistency validation orchestrator."""

    def __init__(self, metrics_service: MetricsService | None = None):
        """Initialize data consistency validator."""
        self.metrics_service = metrics_service or MetricsService()
        self.secrets_manager = get_secrets_manager()

        # Validation checks registry
        self.validation_checks: list[ValidationCheck] = []

        # Initialize validators
        self.db_validator: DatabaseConsistencyValidator | None = None
        self.fs_validator: FileSystemConsistencyValidator | None = None
        self.app_validator: ApplicationConsistencyValidator | None = None

    def register_database_validation(self, connection_url: str):
        """Register database validation."""
        self.db_validator = DatabaseConsistencyValidator(connection_url)
        logger.info("Database consistency validator registered")

    def register_filesystem_validation(self, base_paths: list[str]):
        """Register file system validation."""
        self.fs_validator = FileSystemConsistencyValidator(base_paths)
        logger.info(
            f"File system consistency validator registered for {len(base_paths)} paths"
        )

    def register_application_validation(self, config: dict[str, Any]):
        """Register application validation."""
        self.app_validator = ApplicationConsistencyValidator(config)
        logger.info("Application consistency validator registered")

    def add_custom_check(self, check: ValidationCheck):
        """Add custom validation check."""
        self.validation_checks.append(check)
        logger.info(f"Custom validation check added: {check.name}")

    async def run_validation(
        self,
        consistency_level: ConsistencyLevel = ConsistencyLevel.STRUCTURAL,
        parallel_execution: bool = True,
    ) -> ValidationReport:
        """Run comprehensive data consistency validation."""
        validation_id = f"validation_{int(time.time())}"
        start_time = datetime.utcnow()

        report = ValidationReport(
            validation_id=validation_id,
            start_time=start_time,
            consistency_level=consistency_level,
        )

        logger.info(f"Starting data consistency validation: {validation_id}")

        try:
            # Build validation task list
            validation_tasks = []

            # Database validation tasks
            if self.db_validator:
                validation_tasks.extend(
                    [
                        (
                            "db_connectivity",
                            self.db_validator.validate_basic_connectivity(),
                        ),
                    ]
                )

                if consistency_level in [
                    ConsistencyLevel.STRUCTURAL,
                    ConsistencyLevel.COMPREHENSIVE,
                ]:
                    validation_tasks.extend(
                        [
                            (
                                "db_schema",
                                self.db_validator.validate_schema_integrity(
                                    [
                                        "documents",
                                        "document_library",
                                        "vector_indexes",
                                        "citations",
                                        "citation_relations",
                                    ]
                                ),
                            ),
                        ]
                    )

                if consistency_level in [
                    ConsistencyLevel.REFERENTIAL,
                    ConsistencyLevel.COMPREHENSIVE,
                ]:
                    validation_tasks.extend(
                        [
                            (
                                "db_referential",
                                self.db_validator.validate_referential_integrity(),
                            ),
                        ]
                    )

            # File system validation tasks
            if self.fs_validator:
                validation_tasks.extend(
                    [
                        (
                            "fs_accessibility",
                            self.fs_validator.validate_path_accessibility(),
                        ),
                    ]
                )

                if consistency_level in [
                    ConsistencyLevel.STRUCTURAL,
                    ConsistencyLevel.COMPREHENSIVE,
                ]:
                    validation_tasks.extend(
                        [
                            (
                                "fs_structure",
                                self.fs_validator.validate_directory_structure(
                                    {
                                        "documents": {},
                                        "vector_indexes": {},
                                        "logs": {},
                                        "temp": {},
                                    }
                                ),
                            ),
                        ]
                    )

                if consistency_level in [
                    ConsistencyLevel.CONTENT,
                    ConsistencyLevel.COMPREHENSIVE,
                ]:
                    validation_tasks.extend(
                        [
                            (
                                "fs_integrity",
                                self.fs_validator.validate_file_integrity(),
                            ),
                        ]
                    )

            # Application validation tasks
            if self.app_validator:
                validation_tasks.extend(
                    [
                        (
                            "app_config",
                            self.app_validator.validate_configuration_integrity(),
                        ),
                        (
                            "app_health",
                            self.app_validator.validate_service_health(
                                [
                                    "http://localhost:8000/health",
                                    "http://localhost:8000/api/health",
                                ]
                            ),
                        ),
                    ]
                )

            # Execute validation tasks
            if parallel_execution:
                # Run tasks in parallel
                task_results = await asyncio.gather(
                    *[task for _, task in validation_tasks], return_exceptions=True
                )

                # Process results
                for i, (task_name, _) in enumerate(validation_tasks):
                    result = task_results[i]
                    if isinstance(result, Exception):
                        # Handle exceptions
                        check_result = CheckResult(
                            check_id=task_name,
                            result=ValidationResult.ERROR,
                            start_time=start_time,
                            end_time=datetime.utcnow(),
                            message=f"Task execution error: {str(result)}",
                            errors=[str(result)],
                        )
                    else:
                        check_result = result

                    report.check_results.append(check_result)
            else:
                # Run tasks sequentially
                for task_name, task in validation_tasks:
                    try:
                        result = await task
                        report.check_results.append(result)
                    except Exception as e:
                        error_result = CheckResult(
                            check_id=task_name,
                            result=ValidationResult.ERROR,
                            start_time=datetime.utcnow(),
                            end_time=datetime.utcnow(),
                            message=f"Task execution error: {str(e)}",
                            errors=[str(e)],
                        )
                        report.check_results.append(error_result)

            # Process results and generate report
            self._process_validation_results(report)

            # Update metrics
            await self._update_metrics(report)

        except Exception as e:
            logger.error(f"Error during validation execution: {e}")
            report.overall_status = ValidationResult.ERROR
            report.metadata["execution_error"] = str(e)

        report.end_time = datetime.utcnow()
        report.total_duration = (report.end_time - report.start_time).total_seconds()

        logger.info(
            f"Validation completed: {report.overall_status.value} "
            f"({report.passed_checks}/{report.total_checks} checks passed)"
        )

        return report

    def _process_validation_results(self, report: ValidationReport):
        """Process validation results and update report summary."""
        report.total_checks = len(report.check_results)

        for check_result in report.check_results:
            if check_result.result == ValidationResult.PASSED:
                report.passed_checks += 1
            elif check_result.result == ValidationResult.FAILED:
                report.failed_checks += 1
                report.critical_failures.append(
                    f"{check_result.check_id}: {check_result.message}"
                )
            elif check_result.result == ValidationResult.WARNING:
                report.warning_checks += 1
            elif check_result.result == ValidationResult.SKIPPED:
                report.skipped_checks += 1
            elif check_result.result == ValidationResult.ERROR:
                report.error_checks += 1
                report.critical_failures.append(
                    f"{check_result.check_id}: {check_result.message}"
                )

        # Determine overall status
        if report.failed_checks > 0 or report.error_checks > 0:
            report.overall_status = ValidationResult.FAILED
        elif report.warning_checks > 0:
            report.overall_status = ValidationResult.WARNING
        elif report.passed_checks > 0:
            report.overall_status = ValidationResult.PASSED
        else:
            report.overall_status = ValidationResult.SKIPPED

    async def _update_metrics(self, report: ValidationReport):
        """Update metrics based on validation results."""
        try:
            # Record validation completion
            await self.metrics_service.record_counter(
                "data_consistency_validation_completed",
                tags={
                    "consistency_level": report.consistency_level.value,
                    "overall_status": report.overall_status.value,
                },
            )

            # Record validation duration
            await self.metrics_service.record_histogram(
                "data_consistency_validation_duration",
                report.total_duration,
                tags={"consistency_level": report.consistency_level.value},
            )

            # Record check results
            await self.metrics_service.record_gauge(
                "data_consistency_checks_passed",
                report.passed_checks,
                tags={"consistency_level": report.consistency_level.value},
            )

            await self.metrics_service.record_gauge(
                "data_consistency_checks_failed",
                report.failed_checks,
                tags={"consistency_level": report.consistency_level.value},
            )

            await self.metrics_service.record_gauge(
                "data_consistency_checks_total",
                report.total_checks,
                tags={"consistency_level": report.consistency_level.value},
            )

        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

    async def generate_report_json(self, report: ValidationReport) -> str:
        """Generate JSON report."""
        report_dict = {
            "validation_id": report.validation_id,
            "start_time": report.start_time.isoformat(),
            "end_time": report.end_time.isoformat() if report.end_time else None,
            "total_duration_seconds": report.total_duration,
            "consistency_level": report.consistency_level.value,
            "overall_status": report.overall_status.value,
            "summary": {
                "total_checks": report.total_checks,
                "passed_checks": report.passed_checks,
                "failed_checks": report.failed_checks,
                "warning_checks": report.warning_checks,
                "skipped_checks": report.skipped_checks,
                "error_checks": report.error_checks,
            },
            "critical_failures": report.critical_failures,
            "check_results": [
                {
                    "check_id": result.check_id,
                    "result": result.result.value,
                    "start_time": result.start_time.isoformat(),
                    "end_time": (
                        result.end_time.isoformat() if result.end_time else None
                    ),
                    "duration_seconds": result.duration_seconds,
                    "message": result.message,
                    "details": result.details,
                    "errors": result.errors,
                }
                for result in report.check_results
            ],
            "metadata": report.metadata,
        }

        return json.dumps(report_dict, indent=2, default=str)

    async def save_report(self, report: ValidationReport, output_path: str):
        """Save validation report to file."""
        report_json = await self.generate_report_json(report)

        async with aiofiles.open(output_path, "w") as f:
            await f.write(report_json)

        logger.info(f"Validation report saved: {output_path}")


# Example usage and testing
async def main():
    """Example usage of data consistency validator."""
    validator = DataConsistencyValidator()

    # Register validators
    validator.register_database_validation("sqlite:///test.db")
    validator.register_filesystem_validation(["/tmp/test", "/app/data"])
    validator.register_application_validation(
        {
            "required_keys": ["database_url", "secret_key"],
            "config_files": ["/etc/app/config.yaml"],
        }
    )

    # Run comprehensive validation
    report = await validator.run_validation(ConsistencyLevel.COMPREHENSIVE)

    print(f"Validation Status: {report.overall_status.value}")
    print(f"Checks: {report.passed_checks}/{report.total_checks} passed")
    print(f"Duration: {report.total_duration:.2f} seconds")

    if report.critical_failures:
        print("Critical Failures:")
        for failure in report.critical_failures:
            print(f"  - {failure}")

    # Save report
    await validator.save_report(
        report, f"validation_report_{report.validation_id}.json"
    )


if __name__ == "__main__":
    asyncio.run(main())
