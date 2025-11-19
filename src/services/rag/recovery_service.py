"""
RAG Recovery Service

Handles corruption detection, repair, and system diagnostics including:
- Index corruption detection and analysis
- Recovery and repair operations
- System health monitoring and checks
- Orphaned resource cleanup

This service focuses on maintaining system health and recovering
from various failure scenarios in the RAG system.
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from src.database.models import VectorIndexModel
from src.repositories.vector_repository import VectorIndexRepository
from src.services.error_recovery import HealthChecker, RecoveryOrchestrator

from .file_manager import RAGFileManager

logger = logging.getLogger(__name__)


class RAGRecoveryError(Exception):
    """Base exception for RAG recovery errors."""

    pass


class CorruptionDetectionError(RAGRecoveryError):
    """Exception raised when corruption detection fails."""

    pass


class RecoveryOperationError(RAGRecoveryError):
    """Exception raised when recovery operations fail."""

    pass


class RAGRecoveryService:
    """
    Handles corruption detection, repair, and system diagnostics.

    Responsibilities:
    - Index corruption detection and severity assessment
    - Recovery strategy determination and execution
    - System health monitoring and reporting
    - Orphaned resource identification and cleanup
    """

    def __init__(
        self,
        vector_repo: VectorIndexRepository,
        file_manager: RAGFileManager,
        health_checker: HealthChecker | None = None,
    ):
        """
        Initialize RAG recovery service.

        Args:
            vector_repo: Vector index repository instance
            file_manager: RAG file manager instance
            health_checker: Optional health checker instance
        """
        self.vector_repo = vector_repo
        self.file_manager = file_manager
        self.health_checker = health_checker or HealthChecker()
        self.recovery_orchestrator = RecoveryOrchestrator()

        # Setup health checks
        self._setup_health_checks()

        logger.info("RAG Recovery Service initialized")

    def _setup_health_checks(self) -> None:
        """Setup health checks for RAG system components."""
        self.health_checker.add_health_check(
            "vector_storage", self._check_vector_storage_health
        )
        self.health_checker.add_health_check(
            "database_connection", self._check_database_health
        )
        self.health_checker.add_health_check(
            "system_resources", self._check_system_resources
        )

    def _check_vector_storage_health(self) -> bool:
        """Check vector storage directory health."""
        return self.file_manager.is_accessible()

    def _check_database_health(self) -> bool:
        """Check database connection health."""
        try:
            # Try a simple database operation
            self.vector_repo.get_index_statistics()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def _check_system_resources(self) -> bool:
        """Check system resource availability."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            disk_usage = psutil.disk_usage(".")

            # Check memory and disk thresholds
            return (
                memory.percent < 90.0  # Less than 90% memory usage
                and disk_usage.free > 1024 * 1024 * 1024  # At least 1GB free space
            )
        except Exception as e:
            logger.error(f"System resource check failed: {e}")
            return False

    def analyze_index_corruption(
        self, vector_index: VectorIndexModel
    ) -> dict[str, Any]:
        """
        Analyze vector index for corruption and determine severity.

        Args:
            vector_index: Vector index model to analyze

        Returns:
            Dictionary with corruption analysis results

        Raises:
            CorruptionDetectionError: If analysis fails
        """
        logger.debug(f"Analyzing corruption for index {vector_index.id}")

        analysis_result = {
            "index_id": vector_index.id,
            "document_id": vector_index.document_id,
            "corruption_detected": False,
            "corruption_types": [],
            "corruption_severity": "none",  # none, light, moderate, critical
            "missing_files": [],
            "corrupted_files": [],
            "file_size_issues": [],
            "metadata_issues": [],
            "recommendations": [],
        }

        try:
            index_path = Path(vector_index.index_path)

            # Check if index directory exists
            if not index_path.exists():
                analysis_result.update(
                    {
                        "corruption_detected": True,
                        "corruption_types": ["missing_directory"],
                        "corruption_severity": "critical",
                        "recommendations": ["Rebuild index completely"],
                    }
                )
                return analysis_result

            # Check for required LlamaIndex files
            required_files = [
                "default__vector_store.json",
                "graph_store.json",
                "index_store.json",
            ]

            for required_file in required_files:
                file_path = index_path / required_file

                if not file_path.exists():
                    analysis_result["missing_files"].append(required_file)
                    analysis_result["corruption_detected"] = True
                    analysis_result["corruption_types"].append("missing_files")

                else:
                    # Check file integrity
                    self._analyze_file_integrity(file_path, analysis_result)

            # Determine overall corruption severity
            self._determine_corruption_severity(analysis_result)

            # Generate recommendations
            self._generate_recovery_recommendations(analysis_result)

            logger.debug(
                f"Corruption analysis completed: {analysis_result['corruption_severity']}"
            )
            return analysis_result

        except Exception as e:
            error_msg = f"Corruption analysis failed for index {vector_index.id}: {e}"
            logger.error(error_msg)
            raise CorruptionDetectionError(error_msg) from e

    def _analyze_file_integrity(
        self, file_path: Path, analysis_result: dict[str, Any]
    ) -> None:
        """Analyze individual file integrity."""
        try:
            # Check file size
            if file_path.stat().st_size == 0:
                analysis_result["file_size_issues"].append(file_path.name)
                analysis_result["corruption_detected"] = True
                analysis_result["corruption_types"].append("empty_files")

            # Validate JSON files
            if file_path.name.endswith(".json"):
                try:
                    with open(file_path) as f:
                        data = json.load(f)

                    # Basic structure validation for vector store
                    if file_path.name == "default__vector_store.json":
                        if not isinstance(data, dict[str, Any]) or "embedding_dict" not in data:
                            analysis_result["corrupted_files"].append(
                                f"{file_path.name}: Invalid structure"
                            )
                            analysis_result["corruption_detected"] = True
                            analysis_result["corruption_types"].append(
                                "corrupted_files"
                            )

                except json.JSONDecodeError as e:
                    analysis_result["corrupted_files"].append(
                        f"{file_path.name}: JSON decode error - {e}"
                    )
                    analysis_result["corruption_detected"] = True
                    analysis_result["corruption_types"].append("corrupted_files")

        except Exception as e:
            analysis_result["corrupted_files"].append(
                f"{file_path.name}: Analysis error - {e}"
            )
            analysis_result["corruption_detected"] = True

    def _determine_corruption_severity(self, analysis_result: dict[str, Any]) -> None:
        """Determine overall corruption severity based on analysis."""
        if not analysis_result["corruption_detected"]:
            analysis_result["corruption_severity"] = "none"
            return

        # Critical: Missing core files or directory
        if (
            analysis_result["missing_files"]
            or any("vector_store" in f for f in analysis_result["corrupted_files"])
            or "missing_directory" in analysis_result["corruption_types"]
        ):
            analysis_result["corruption_severity"] = "critical"

        # Moderate: Corrupted non-core files or empty files
        elif analysis_result["corrupted_files"] or analysis_result["file_size_issues"]:
            analysis_result["corruption_severity"] = "moderate"

        # Light: Metadata issues only
        elif analysis_result["metadata_issues"]:
            analysis_result["corruption_severity"] = "light"

        else:
            analysis_result["corruption_severity"] = "light"

    def _generate_recovery_recommendations(
        self, analysis_result: dict[str, Any]
    ) -> None:
        """Generate recovery recommendations based on corruption analysis."""
        severity = analysis_result["corruption_severity"]
        recommendations = []

        if severity == "critical":
            recommendations.append("Full index rebuild required")
            recommendations.append("Verify source document integrity")

        elif severity == "moderate":
            recommendations.append("Attempt partial repair first")
            recommendations.append("Fallback to full rebuild if repair fails")

        elif severity == "light":
            recommendations.append("Metadata repair may be sufficient")
            recommendations.append("Verify and update index metadata")

        else:
            recommendations.append("No action needed")

        analysis_result["recommendations"] = recommendations

    def recover_corrupted_index(
        self,
        vector_index: VectorIndexModel,
        force_rebuild: bool = False,
        rebuild_callback: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """
        Recover a corrupted vector index with comprehensive repair strategies.

        Args:
            vector_index: Vector index model to recover
            force_rebuild: If True, skip repair attempts and force rebuild
            rebuild_callback: Optional callback function for rebuilding index

        Returns:
            Dictionary with recovery results

        Raises:
            RecoveryOperationError: If recovery fails
        """
        recovery_start_time = datetime.now()
        logger.info(f"Starting index recovery for index {vector_index.id}")

        recovery_result = {
            "index_id": vector_index.id,
            "document_id": vector_index.document_id,
            "recovery_successful": False,
            "corruption_analysis": {},
            "repair_actions": [],
            "recovery_duration_ms": 0,
            "error": None,
        }

        try:
            # Analyze corruption first
            corruption_analysis = self.analyze_index_corruption(vector_index)
            recovery_result["corruption_analysis"] = corruption_analysis

            if not corruption_analysis["corruption_detected"] and not force_rebuild:
                # No corruption detected
                recovery_result["recovery_successful"] = True
                recovery_result["repair_actions"].append("no_action_needed")
                logger.info(f"No corruption detected for index {vector_index.id}")

            else:
                # Determine recovery strategy
                if (
                    force_rebuild
                    or corruption_analysis["corruption_severity"] == "critical"
                ):
                    # Full rebuild required
                    recovery_result["repair_actions"].append("full_rebuild")

                    if rebuild_callback:
                        success = rebuild_callback(vector_index)
                        recovery_result["recovery_successful"] = success
                        if success:
                            logger.info(f"Index {vector_index.id} rebuilt successfully")
                        else:
                            recovery_result["error"] = "Rebuild callback failed"
                    else:
                        recovery_result["error"] = (
                            "Rebuild required but no callback provided"
                        )

                elif corruption_analysis["corruption_severity"] == "moderate":
                    # Attempt partial repair
                    recovery_result["repair_actions"].append("partial_repair")
                    success = self._attempt_partial_repair(vector_index)
                    recovery_result["recovery_successful"] = success

                    if not success and rebuild_callback:
                        # Fallback to rebuild
                        recovery_result["repair_actions"].append("fallback_rebuild")
                        recovery_result["recovery_successful"] = rebuild_callback(
                            vector_index
                        )

                else:
                    # Light repair/verification
                    recovery_result["repair_actions"].append("verification_repair")
                    success = self._perform_verification_repair(vector_index)
                    recovery_result["recovery_successful"] = success

        except Exception as e:
            error_msg = f"Index recovery failed: {e}"
            recovery_result["error"] = error_msg
            logger.error(error_msg)
            raise RecoveryOperationError(error_msg) from e

        finally:
            recovery_duration = datetime.now() - recovery_start_time
            recovery_result["recovery_duration_ms"] = int(
                recovery_duration.total_seconds() * 1000
            )

        return recovery_result

    def _attempt_partial_repair(self, vector_index: VectorIndexModel) -> bool:
        """Attempt partial repair of corrupted index."""
        try:
            logger.info(f"Attempting partial repair of index {vector_index.id}")

            index_path = Path(vector_index.index_path)

            # Check if main vector store exists and is valid
            vector_store_file = index_path / "default__vector_store.json"

            if vector_store_file.exists() and vector_store_file.stat().st_size > 0:
                try:
                    with open(vector_store_file) as f:
                        vector_data = json.load(f)

                    if (
                        isinstance(vector_data, dict[str, Any])
                        and "embedding_dict" in vector_data
                    ):
                        # Vector store seems intact, try to regenerate missing metadata
                        self._regenerate_index_metadata(index_path, vector_data)

                        # Verify repair was successful
                        return self.file_manager.verify_index_files(str(index_path))

                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug(f"Vector store validation failed: {e}")

            logger.debug(f"Partial repair not possible for index {vector_index.id}")
            return False

        except Exception as e:
            logger.error(f"Partial repair failed for index {vector_index.id}: {e}")
            return False

    def _regenerate_index_metadata(
        self, index_path: Path, vector_data: dict[str, Any]
    ) -> None:
        """Regenerate missing index metadata files."""
        try:
            # Generate basic graph_store.json if missing
            graph_store_file = index_path / "graph_store.json"
            if not graph_store_file.exists():
                graph_store_data = {"graph": {}, "node_list": []}
                with open(graph_store_file, "w") as f:
                    json.dump(graph_store_data, f)
                logger.debug("Regenerated graph_store.json")

            # Generate basic index_store.json if missing
            index_store_file = index_path / "index_store.json"
            if not index_store_file.exists():
                index_store_data = {"index_struct": {"nodes": []}}
                with open(index_store_file, "w") as f:
                    json.dump(index_store_data, f)
                logger.debug("Regenerated index_store.json")

        except Exception as e:
            logger.error(f"Failed to regenerate metadata: {e}")
            raise

    def _perform_verification_repair(self, vector_index: VectorIndexModel) -> bool:
        """Perform light verification and repair of index."""
        try:
            logger.debug(f"Performing verification repair of index {vector_index.id}")

            # Update database metadata if files are OK but metadata is stale
            if self.file_manager.verify_index_files(vector_index.index_path):
                # Recalculate chunk count if it seems wrong
                actual_chunk_count = self.file_manager.get_chunk_count(
                    vector_index.index_path
                )

                if (
                    actual_chunk_count != vector_index.chunk_count
                    and actual_chunk_count > 0
                ):
                    vector_index.chunk_count = actual_chunk_count
                    self.vector_repo.update(vector_index)
                    logger.info(
                        f"Updated chunk count for index {vector_index.id}: {actual_chunk_count}"
                    )

                return True

            return False

        except Exception as e:
            logger.error(f"Verification repair failed for index {vector_index.id}: {e}")
            return False

    def perform_system_health_check(self) -> dict[str, Any]:
        """
        Perform comprehensive system health check and diagnosis.

        Returns:
            Dictionary with health check results and recommendations
        """
        check_start_time = datetime.now()
        logger.info("Starting comprehensive system health check")

        health_report = {
            "check_start_time": check_start_time.isoformat(),
            "health_status": {},
            "corrupted_indexes": [],
            "orphaned_resources": {},
            "cleanup_actions": [],
            "recommendations": [],
            "overall_status": "healthy",  # healthy, degraded, critical
        }

        try:
            # Run all health checks
            health_results = self.health_checker.run_all_checks()
            health_report["health_status"] = health_results

            if not all(health_results.values()):
                health_report["overall_status"] = "degraded"
                failed_checks = [
                    check for check, result in health_results.items() if not result
                ]
                health_report["recommendations"].extend(
                    [f"Address failed health check: {check}" for check in failed_checks]
                )

            # Identify corrupted indexes
            corrupted_indexes = self.identify_corrupted_indexes()
            health_report["corrupted_indexes"] = corrupted_indexes

            if corrupted_indexes:
                health_report["overall_status"] = (
                    "degraded"
                    if health_report["overall_status"] == "healthy"
                    else "critical"
                )
                health_report["recommendations"].append(
                    f"Repair or rebuild {len(corrupted_indexes)} corrupted indexes"
                )

            # Check for orphaned resources
            orphaned_count = self.cleanup_orphaned_resources()
            if orphaned_count > 0:
                health_report["cleanup_actions"].append(
                    f"Cleaned up {orphaned_count} orphaned resources"
                )

        except Exception as e:
            logger.error(f"System health check failed: {e}")
            health_report["overall_status"] = "critical"
            health_report["error"] = str(e)

        finally:
            check_duration = datetime.now() - check_start_time
            health_report["check_duration_ms"] = int(
                check_duration.total_seconds() * 1000
            )
            health_report["check_end_time"] = datetime.now().isoformat()

        logger.info(f"System health check completed: {health_report['overall_status']}")
        return health_report

    def identify_corrupted_indexes(self) -> list[dict[str, Any]]:
        """
        Identify all corrupted indexes in the system.

        Returns:
            List of corrupted index information dictionaries
        """
        corrupted_indexes = []

        try:
            # Get all vector indexes from database
            all_indexes = self.vector_repo.get_all_indexes()

            for vector_index in all_indexes:
                try:
                    corruption_analysis = self.analyze_index_corruption(vector_index)

                    if corruption_analysis["corruption_detected"]:
                        corrupted_info = {
                            "index_id": vector_index.id,
                            "document_id": vector_index.document_id,
                            "corruption_severity": corruption_analysis[
                                "corruption_severity"
                            ],
                            "corruption_types": corruption_analysis["corruption_types"],
                            "recommendations": corruption_analysis["recommendations"],
                        }
                        corrupted_indexes.append(corrupted_info)

                except Exception as e:
                    logger.error(f"Failed to analyze index {vector_index.id}: {e}")

        except Exception as e:
            logger.error(f"Failed to identify corrupted indexes: {e}")

        return corrupted_indexes

    def cleanup_orphaned_resources(self) -> int:
        """
        Clean up orphaned resources including database records and filesystem directories.

        Returns:
            Number of orphaned resources cleaned up
        """
        try:
            # Clean up database orphans
            db_orphans = self.vector_repo.cleanup_orphaned_indexes()

            # Clean up filesystem orphans
            all_indexes = self.vector_repo.get_all_indexes()
            valid_paths = [idx.index_path for idx in all_indexes]
            orphaned_dirs = self.file_manager.find_orphaned_directories(valid_paths)
            fs_orphans = self.file_manager.cleanup_orphaned_directories(orphaned_dirs)

            total_orphans = db_orphans + fs_orphans

            if total_orphans > 0:
                logger.info(
                    f"Cleaned up {total_orphans} orphaned resources ({db_orphans} DB + {fs_orphans} FS)"
                )

            return total_orphans

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned resources: {e}")
            return 0

    def get_recovery_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive recovery and diagnostic metrics.

        Returns:
            Dictionary with recovery service metrics
        """
        try:
            metrics = {
                "service_name": "RAGRecoveryService",
                "health_status": self.health_checker.run_all_checks(),
                "storage_stats": self.file_manager.get_storage_statistics(),
                "recovery_orchestrator_metrics": self.recovery_orchestrator.get_comprehensive_metrics(),
            }

            # Add database statistics
            try:
                db_stats = self.vector_repo.get_index_statistics()
                metrics["database_stats"] = db_stats
            except Exception as e:
                metrics["database_stats"] = {"error": str(e)}

            return metrics

        except Exception as e:
            logger.error(f"Failed to get recovery metrics: {e}")
            return {"error": str(e)}
