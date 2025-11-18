#!/usr/bin/env python3
"""
Advanced Query Performance Analyzer for AI Enhanced PDF Scholar
Automated slow query detection, analysis, and optimization recommendations.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.database.connection import DatabaseConnection
except ImportError as e:
    logger.error(f"Failed to import DatabaseConnection: {e}")
    sys.exit(1)


@dataclass
class QueryExecutionStats:
    """Statistics for a single query execution."""

    query_id: str
    query_text: str
    parameters: tuple[Any, ...] | None
    execution_time_ms: float
    rows_affected: int
    rows_returned: int
    execution_plan: list[dict[str, Any]]
    timestamp: datetime
    thread_id: int
    memory_usage: int | None = None
    io_operations: int | None = None


@dataclass
class QueryAnalysisResult:
    """Result of query analysis with optimization recommendations."""

    query_id: str
    query_text: str
    avg_execution_time: float
    max_execution_time: float
    min_execution_time: float
    execution_count: int
    total_time: float
    performance_rating: str  # excellent, good, fair, poor
    bottlenecks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    index_usage: dict[str, Any] = field(default_factory=dict)
    similar_queries: list[str] = field(default_factory=list)


class QueryPerformanceAnalyzer:
    """
    Advanced Query Performance Analyzer

    Monitors, collects, and analyzes query performance data to identify
    slow queries, bottlenecks, and optimization opportunities.
    """

    # Performance thresholds (milliseconds)
    EXCELLENT_THRESHOLD = 1.0
    GOOD_THRESHOLD = 10.0
    FAIR_THRESHOLD = 50.0
    # Poor threshold is anything above FAIR_THRESHOLD

    # Collection settings
    SLOW_QUERY_THRESHOLD = 100.0  # Log queries slower than this
    MAX_QUERY_HISTORY = 10000  # Maximum queries to keep in memory
    ANALYSIS_BATCH_SIZE = 100  # Queries to analyze in one batch

    def __init__(
        self, db_connection: DatabaseConnection, enable_monitoring: bool = True
    ):
        """
        Initialize the Query Performance Analyzer.

        Args:
            db_connection: Database connection instance
            enable_monitoring: Whether to enable real-time monitoring
        """
        self.db = db_connection
        self.enable_monitoring = enable_monitoring

        # Query execution history
        self._query_history: list[QueryExecutionStats] = []
        self._query_patterns: dict[str, list[QueryExecutionStats]] = {}
        self._lock = threading.RLock()

        # Performance baselines
        self._performance_baselines: dict[str, float] = {}

        # Initialize monitoring table if needed
        if self.enable_monitoring:
            self._init_monitoring_tables()

    def _init_monitoring_tables(self) -> None:
        """Initialize tables for query performance monitoring."""
        try:
            # Create query performance monitoring table
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS query_performance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_id TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    rows_affected INTEGER,
                    rows_returned INTEGER,
                    execution_plan TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    thread_id INTEGER,
                    parameters TEXT
                )
            """
            )

            # Create index for efficient querying
            self.db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_perf_timestamp
                ON query_performance_log(timestamp DESC)
            """
            )

            self.db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_perf_query_id
                ON query_performance_log(query_id)
            """
            )

            self.db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_perf_execution_time
                ON query_performance_log(execution_time_ms DESC)
            """
            )

            logger.info("Query performance monitoring tables initialized")

        except Exception as e:
            logger.error(f"Failed to initialize monitoring tables: {e}")
            raise

    def _generate_query_id(self, query_text: str) -> str:
        """Generate a consistent ID for a query pattern."""
        import hashlib

        # Normalize query by removing extra whitespace and converting to lowercase
        normalized = " ".join(query_text.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:12]

    def record_query_execution(
        self,
        query_text: str,
        execution_time_ms: float,
        parameters: tuple[Any, ...] | None = None,
        rows_affected: int = 0,
        rows_returned: int = 0,
        execution_plan: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Record a query execution for performance analysis.

        Args:
            query_text: The SQL query text
            execution_time_ms: Execution time in milliseconds
            parameters: Query parameters if any
            rows_affected: Number of rows affected by the query
            rows_returned: Number of rows returned by the query
            execution_plan: Query execution plan if available
        """
        if not self.enable_monitoring:
            return

        try:
            query_id = self._generate_query_id(query_text)

            # Create execution stats
            stats = QueryExecutionStats(
                query_id=query_id,
                query_text=query_text,
                parameters=parameters,
                execution_time_ms=execution_time_ms,
                rows_affected=rows_affected,
                rows_returned=rows_returned,
                execution_plan=execution_plan or [],
                timestamp=datetime.now(),
                thread_id=threading.get_ident(),
            )

            with self._lock:
                # Add to history
                self._query_history.append(stats)

                # Add to pattern tracking
                if query_id not in self._query_patterns:
                    self._query_patterns[query_id] = []
                self._query_patterns[query_id].append(stats)

                # Maintain history size limit
                if len(self._query_history) > self.MAX_QUERY_HISTORY:
                    old_stats = self._query_history.pop(0)
                    # Also remove from patterns if it was the last one
                    pattern_list = self._query_patterns.get(old_stats.query_id, [])
                    if pattern_list and pattern_list[0] == old_stats:
                        pattern_list.pop(0)
                        if not pattern_list:
                            del self._query_patterns[old_stats.query_id]

            # Log slow queries immediately
            if execution_time_ms >= self.SLOW_QUERY_THRESHOLD:
                logger.warning(
                    f"Slow query detected: {execution_time_ms:.2f}ms - "
                    f"{query_text[:100]}{'...' if len(query_text) > 100 else ''}"
                )

            # Persist to database if monitoring is enabled
            self._persist_query_stats(stats)

        except Exception as e:
            logger.error(f"Failed to record query execution: {e}")

    def _persist_query_stats(self, stats: QueryExecutionStats) -> None:
        """Persist query statistics to database."""
        try:
            params_json = json.dumps(stats.parameters) if stats.parameters else None
            plan_json = (
                json.dumps(stats.execution_plan) if stats.execution_plan else None
            )

            self.db.execute(
                """
                INSERT INTO query_performance_log
                (query_id, query_text, execution_time_ms, rows_affected, rows_returned,
                 execution_plan, timestamp, thread_id, parameters)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    stats.query_id,
                    stats.query_text,
                    stats.execution_time_ms,
                    stats.rows_affected,
                    stats.rows_returned,
                    plan_json,
                    stats.timestamp.isoformat(),
                    stats.thread_id,
                    params_json,
                ),
            )

        except Exception as e:
            logger.debug(f"Failed to persist query stats: {e}")

    def get_slow_queries(
        self,
        threshold_ms: float | None = None,
        limit: int = 50,
        time_window_hours: int | None = None,
    ) -> list[QueryAnalysisResult]:
        """
        Get slow queries with analysis.

        Args:
            threshold_ms: Minimum execution time threshold (default: FAIR_THRESHOLD)
            limit: Maximum number of queries to return
            time_window_hours: Only consider queries within this time window

        Returns:
            List of slow query analysis results
        """
        if threshold_ms is None:
            threshold_ms = self.FAIR_THRESHOLD

        try:
            # Build time filter
            time_filter = ""
            params = []

            if time_window_hours:
                cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
                time_filter = "AND timestamp >= ?"
                params.append(cutoff_time.isoformat())

            # Get slow queries from database
            query = f"""
                SELECT query_id, query_text,
                       AVG(execution_time_ms) as avg_time,
                       MAX(execution_time_ms) as max_time,
                       MIN(execution_time_ms) as min_time,
                       COUNT(*) as execution_count,
                       SUM(execution_time_ms) as total_time
                FROM query_performance_log
                WHERE execution_time_ms >= ? {time_filter}
                GROUP BY query_id, query_text
                HAVING avg_time >= ?
                ORDER BY avg_time DESC, execution_count DESC
                LIMIT ?
            """

            params = [threshold_ms] + params + [threshold_ms, limit]
            slow_queries = self.db.fetch_all(query, tuple(params))

            # Analyze each slow query
            results = []
            for row in slow_queries:
                analysis = self._analyze_query_pattern(
                    row["query_id"],
                    row["query_text"],
                    row["avg_time"],
                    row["max_time"],
                    row["min_time"],
                    row["execution_count"],
                    row["total_time"],
                )
                results.append(analysis)

            logger.info(
                f"Found {len(results)} slow queries above {threshold_ms}ms threshold"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to get slow queries: {e}")
            return []

    def _analyze_query_pattern(
        self,
        query_id: str,
        query_text: str,
        avg_time: float,
        max_time: float,
        min_time: float,
        execution_count: int,
        total_time: float,
    ) -> QueryAnalysisResult:
        """Analyze a specific query pattern and generate recommendations."""
        # Determine performance rating
        if avg_time <= self.EXCELLENT_THRESHOLD:
            rating = "excellent"
        elif avg_time <= self.GOOD_THRESHOLD:
            rating = "good"
        elif avg_time <= self.FAIR_THRESHOLD:
            rating = "fair"
        else:
            rating = "poor"

        # Initialize analysis result
        analysis = QueryAnalysisResult(
            query_id=query_id,
            query_text=query_text,
            avg_execution_time=avg_time,
            max_execution_time=max_time,
            min_execution_time=min_time,
            execution_count=execution_count,
            total_time=total_time,
            performance_rating=rating,
        )

        # Analyze bottlenecks and generate recommendations
        self._identify_bottlenecks(analysis)
        self._generate_recommendations(analysis)
        self._analyze_index_usage(analysis)

        return analysis

    def _identify_bottlenecks(self, analysis: QueryAnalysisResult) -> None:
        """Identify potential bottlenecks in the query."""
        query_text_lower = analysis.query_text.lower()

        # Table scan indicators
        if "select * from" in query_text_lower:
            analysis.bottlenecks.append("Full table scan - SELECT * detected")

        # Missing WHERE clause on large operations
        if (
            any(op in query_text_lower for op in ["delete from", "update"])
            and "where" not in query_text_lower
        ):
            analysis.bottlenecks.append("Bulk operation without WHERE clause")

        # Complex JOINs
        join_count = query_text_lower.count(" join ")
        if join_count >= 3:
            analysis.bottlenecks.append(f"Complex query with {join_count} JOINs")

        # Subqueries
        subquery_count = query_text_lower.count("select")
        if subquery_count > 1:
            analysis.bottlenecks.append(
                f"Query contains {subquery_count - 1} subqueries"
            )

        # LIKE operations that can't use indexes
        if "like ?" in query_text_lower or "like '%'" in query_text_lower:
            analysis.bottlenecks.append("LIKE operation with leading wildcard")

        # ORDER BY without LIMIT
        if "order by" in query_text_lower and "limit" not in query_text_lower:
            analysis.bottlenecks.append(
                "ORDER BY without LIMIT may sort entire result set"
            )

        # Functions in WHERE clause
        if any(func in query_text_lower for func in ["lower(", "upper(", "substr("]):
            analysis.bottlenecks.append("Functions in WHERE clause prevent index usage")

    def _generate_recommendations(self, analysis: QueryAnalysisResult) -> None:
        """Generate optimization recommendations for the query."""
        query_text_lower = analysis.query_text.lower()

        # Recommendations based on bottlenecks
        if "Full table scan" in str(analysis.bottlenecks):
            analysis.recommendations.append(
                "Replace SELECT * with specific column names"
            )
            analysis.recommendations.append(
                "Add appropriate WHERE clause to filter results"
            )

        if "Bulk operation without WHERE clause" in str(analysis.bottlenecks):
            analysis.recommendations.append("Add WHERE clause to limit affected rows")
            analysis.recommendations.append("Consider batching large operations")

        if "Complex query" in str(analysis.bottlenecks):
            analysis.recommendations.append(
                "Consider breaking complex JOINs into simpler queries"
            )
            analysis.recommendations.append("Review if all JOINs are necessary")
            analysis.recommendations.append(
                "Ensure proper indexes exist on JOIN columns"
            )

        if "subqueries" in str(analysis.bottlenecks):
            analysis.recommendations.append(
                "Consider converting subqueries to JOINs where possible"
            )
            analysis.recommendations.append(
                "Evaluate if Common Table Expressions (CTEs) would be clearer"
            )

        if "LIKE operation" in str(analysis.bottlenecks):
            analysis.recommendations.append(
                "Consider Full-Text Search (FTS) for text searches"
            )
            analysis.recommendations.append(
                "Use prefix matching (LIKE 'value%') when possible"
            )

        if "ORDER BY without LIMIT" in str(analysis.bottlenecks):
            analysis.recommendations.append(
                "Add LIMIT clause if you don't need all results"
            )
            analysis.recommendations.append("Consider pagination for large result sets")

        if "Functions in WHERE clause" in str(analysis.bottlenecks):
            analysis.recommendations.append(
                "Consider storing computed values in indexed columns"
            )
            analysis.recommendations.append("Use functional indexes if available")

        # General recommendations based on performance
        if analysis.performance_rating == "poor":
            analysis.recommendations.append(
                "Review query execution plan for inefficiencies"
            )
            analysis.recommendations.append(
                "Consider adding database indexes on filtered columns"
            )
            analysis.recommendations.append(
                "Analyze table statistics with ANALYZE command"
            )

        if analysis.execution_count > 1000:
            analysis.recommendations.append(
                "High-frequency query - consider caching results"
            )
            analysis.recommendations.append(
                "Review if query can be optimized at application level"
            )

    def _analyze_index_usage(self, analysis: QueryAnalysisResult) -> None:
        """Analyze index usage for the query."""
        try:
            # Get execution plan for the query
            plan_query = f"EXPLAIN QUERY PLAN {analysis.query_text}"
            plan_rows = self.db.fetch_all(plan_query)

            index_info = {
                "uses_index": False,
                "index_names": [],
                "table_scans": 0,
                "plan_details": [],
            }

            for row in plan_rows:
                detail = row[3] if len(row) > 3 else str(row)  # SQLite EXPLAIN format
                index_info["plan_details"].append(detail)

                detail_lower = detail.lower()
                if "using index" in detail_lower:
                    index_info["uses_index"] = True
                    # Extract index name if possible
                    if " index " in detail_lower:
                        parts = detail_lower.split(" index ")
                        if len(parts) > 1:
                            index_name = parts[1].split()[0].strip("()")
                            if index_name not in index_info["index_names"]:
                                index_info["index_names"].append(index_name)

                if "scan table" in detail_lower:
                    index_info["table_scans"] += 1

            analysis.index_usage = index_info

            # Add index-related recommendations
            if not index_info["uses_index"] and analysis.performance_rating in [
                "poor",
                "fair",
            ]:
                analysis.recommendations.append(
                    "Query does not use indexes - consider adding appropriate indexes"
                )

            if index_info["table_scans"] > 0:
                analysis.recommendations.append(
                    f"Query performs {index_info['table_scans']} table scans"
                )

        except Exception as e:
            logger.debug(f"Failed to analyze index usage: {e}")
            analysis.index_usage = {"error": str(e)}

    def get_performance_summary(self, time_window_hours: int = 24) -> dict[str, Any]:
        """
        Get overall performance summary.

        Args:
            time_window_hours: Time window for analysis

        Returns:
            Performance summary dictionary
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

            # Get basic statistics
            stats_query = """
                SELECT
                    COUNT(*) as total_queries,
                    AVG(execution_time_ms) as avg_time,
                    MAX(execution_time_ms) as max_time,
                    MIN(execution_time_ms) as min_time,
                    SUM(execution_time_ms) as total_time,
                    COUNT(CASE WHEN execution_time_ms > ? THEN 1 END) as slow_queries
                FROM query_performance_log
                WHERE timestamp >= ?
            """

            stats = self.db.fetch_one(
                stats_query, (self.FAIR_THRESHOLD, cutoff_time.isoformat())
            )

            # Get query distribution by performance rating
            distribution = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}

            if stats and stats["total_queries"] > 0:
                # Count queries by performance rating
                for threshold, rating in [
                    (self.EXCELLENT_THRESHOLD, "excellent"),
                    (self.GOOD_THRESHOLD, "good"),
                    (self.FAIR_THRESHOLD, "fair"),
                ]:
                    count_query = """
                        SELECT COUNT(*) as count
                        FROM query_performance_log
                        WHERE timestamp >= ? AND execution_time_ms <= ?
                    """
                    result = self.db.fetch_one(
                        count_query, (cutoff_time.isoformat(), threshold)
                    )
                    if result:
                        distribution[rating] = result["count"]

                # Poor queries are everything above fair threshold
                poor_query = """
                    SELECT COUNT(*) as count
                    FROM query_performance_log
                    WHERE timestamp >= ? AND execution_time_ms > ?
                """
                result = self.db.fetch_one(
                    poor_query, (cutoff_time.isoformat(), self.FAIR_THRESHOLD)
                )
                if result:
                    distribution["poor"] = result["count"]

                # Adjust counts (subtract lower ratings from higher ones)
                distribution["fair"] -= distribution["poor"]
                distribution["good"] -= distribution["fair"] + distribution["poor"]
                distribution["excellent"] -= (
                    distribution["good"] + distribution["fair"] + distribution["poor"]
                )

            # Calculate performance score
            total_queries = stats["total_queries"] if stats else 0
            if total_queries > 0:
                score = (
                    (
                        distribution["excellent"] * 4
                        + distribution["good"] * 3
                        + distribution["fair"] * 2
                        + distribution["poor"] * 1
                    )
                    / (total_queries * 4)
                    * 100
                )
            else:
                score = 0

            return {
                "time_window_hours": time_window_hours,
                "total_queries": total_queries,
                "avg_execution_time_ms": stats["avg_time"] if stats else 0,
                "max_execution_time_ms": stats["max_time"] if stats else 0,
                "min_execution_time_ms": stats["min_time"] if stats else 0,
                "total_time_ms": stats["total_time"] if stats else 0,
                "slow_queries_count": stats["slow_queries"] if stats else 0,
                "performance_distribution": distribution,
                "overall_performance_score": round(score, 2),
                "performance_rating": self._get_rating_from_score(score),
            }

        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}

    def _get_rating_from_score(self, score: float) -> str:
        """Convert numeric score to rating."""
        if score >= 90:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "fair"
        else:
            return "poor"

    def optimize_query_automatically(self, query_text: str) -> dict[str, Any]:
        """
        Attempt to automatically optimize a query.

        Args:
            query_text: SQL query to optimize

        Returns:
            Dictionary with optimization suggestions and potentially rewritten query
        """
        try:
            query_lower = query_text.lower().strip()
            original_query = query_text
            optimized_query = query_text
            optimizations_applied = []

            # Optimization 1: Replace SELECT * with specific columns (if we can determine them)
            if "select *" in query_lower:
                # This would need table introspection - for now just flag it
                optimizations_applied.append(
                    "Flag: Replace SELECT * with specific columns"
                )

            # Optimization 2: Add LIMIT if ORDER BY is present but no LIMIT
            if "order by" in query_lower and "limit" not in query_lower:
                # Suggest adding LIMIT
                optimizations_applied.append(
                    "Suggestion: Add LIMIT clause to ORDER BY query"
                )

            # Optimization 3: Suggest indexes based on WHERE conditions
            where_columns = self._extract_where_columns(query_text)
            if where_columns:
                for column in where_columns:
                    optimizations_applied.append(
                        f"Suggestion: Consider index on column '{column}'"
                    )

            # Optimization 4: Rewrite LIKE with leading wildcard
            if "like '%%" in query_lower or "like '%" in query_lower:
                optimizations_applied.append(
                    "Suggestion: Consider Full-Text Search for wildcard searches"
                )

            return {
                "original_query": original_query,
                "optimized_query": optimized_query,
                "optimizations_applied": optimizations_applied,
                "estimated_improvement": "Manual review required",
            }

        except Exception as e:
            logger.error(f"Failed to optimize query automatically: {e}")
            return {"error": str(e)}

    def _extract_where_columns(self, query_text: str) -> list[str]:
        """Extract column names from WHERE clause (basic implementation)."""
        try:
            import re

            # Find WHERE clause
            where_match = re.search(
                r"\bwhere\b(.+?)(?:\bgroup\b|\border\b|\bhaving\b|\blimit\b|$)",
                query_text,
                re.IGNORECASE | re.DOTALL,
            )

            if not where_match:
                return []

            where_clause = where_match.group(1)

            # Extract column names (basic pattern matching)
            column_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[=<>!]"
            matches = re.findall(column_pattern, where_clause, re.IGNORECASE)

            # Filter out common SQL keywords
            sql_keywords = {
                "and",
                "or",
                "not",
                "in",
                "like",
                "between",
                "is",
                "null",
                "true",
                "false",
            }
            columns = [
                match.lower() for match in matches if match.lower() not in sql_keywords
            ]

            return list(set(columns))  # Remove duplicates

        except Exception as e:
            logger.debug(f"Failed to extract WHERE columns: {e}")
            return []

    def clear_old_data(self, days_to_keep: int = 30) -> int:
        """
        Clear old query performance data.

        Args:
            days_to_keep: Number of days of data to keep

        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            result = self.db.execute(
                """
                DELETE FROM query_performance_log
                WHERE timestamp < ?
            """,
                (cutoff_date.isoformat(),),
            )

            deleted_count = self.db.get_last_change_count()

            # Also clear in-memory data
            with self._lock:
                self._query_history = [
                    stats
                    for stats in self._query_history
                    if stats.timestamp >= cutoff_date
                ]

                # Rebuild pattern tracking
                self._query_patterns.clear()
                for stats in self._query_history:
                    if stats.query_id not in self._query_patterns:
                        self._query_patterns[stats.query_id] = []
                    self._query_patterns[stats.query_id].append(stats)

            logger.info(f"Cleared {deleted_count} old query performance records")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clear old data: {e}")
            return 0


def main():
    """CLI interface for the Query Performance Analyzer."""
    import argparse

    parser = argparse.ArgumentParser(description="Query Performance Analyzer")
    parser.add_argument("--db-path", required=True, help="Database file path")
    parser.add_argument("--analyze", action="store_true", help="Analyze slow queries")
    parser.add_argument(
        "--summary", action="store_true", help="Show performance summary"
    )
    parser.add_argument(
        "--threshold", type=float, default=50.0, help="Slow query threshold in ms"
    )
    parser.add_argument("--hours", type=int, default=24, help="Time window in hours")
    parser.add_argument("--clear-old", type=int, help="Clear data older than N days")
    parser.add_argument("--output", help="Output file for results (JSON)")

    args = parser.parse_args()

    try:
        # Initialize analyzer
        db = DatabaseConnection(args.db_path)
        analyzer = QueryPerformanceAnalyzer(db)

        results = {}

        if args.summary:
            print("Getting performance summary...")
            results["summary"] = analyzer.get_performance_summary(args.hours)

            summary = results["summary"]
            print(f"\nPerformance Summary ({args.hours}h window):")
            print(f"Total Queries: {summary['total_queries']}")
            print(f"Average Time: {summary['avg_execution_time_ms']:.2f}ms")
            print(f"Slow Queries: {summary['slow_queries_count']}")
            print(
                f"Performance Score: {summary['overall_performance_score']}/100 ({summary['performance_rating']})"
            )

        if args.analyze:
            print(f"Analyzing slow queries (threshold: {args.threshold}ms)...")
            slow_queries = analyzer.get_slow_queries(
                args.threshold, time_window_hours=args.hours
            )
            results["slow_queries"] = [
                {
                    "query_id": q.query_id,
                    "avg_time": q.avg_execution_time,
                    "execution_count": q.execution_count,
                    "rating": q.performance_rating,
                    "bottlenecks": q.bottlenecks,
                    "recommendations": q.recommendations,
                }
                for q in slow_queries
            ]

            print(f"Found {len(slow_queries)} slow queries:")
            for query in slow_queries[:10]:  # Show top 10
                print(f"  - Query ID: {query.query_id}")
                print(f"    Avg Time: {query.avg_execution_time:.2f}ms")
                print(f"    Executions: {query.execution_count}")
                print(f"    Rating: {query.performance_rating}")
                if query.recommendations:
                    print(
                        f"    Recommendations: {', '.join(query.recommendations[:2])}"
                    )
                print()

        if args.clear_old:
            deleted = analyzer.clear_old_data(args.clear_old)
            print(f"Cleared {deleted} old performance records")
            results["cleared_records"] = deleted

        # Save results if requested
        if args.output and results:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Results saved to {args.output}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
