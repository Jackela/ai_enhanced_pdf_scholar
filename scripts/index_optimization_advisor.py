#!/usr/bin/env python3
"""
Index Optimization Advisor for AI Enhanced PDF Scholar
Automated index recommendations based on query patterns and performance analysis.
"""

import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from scripts.query_performance_analyzer import QueryPerformanceAnalyzer
    from src.database.connection import DatabaseConnection
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)


@dataclass
class IndexRecommendation:
    """Represents an index optimization recommendation."""

    table_name: str
    columns: list[str]
    index_type: str  # btree, unique, partial, covering
    recommendation_type: str  # missing, redundant, optimize, composite
    priority: str  # critical, high, medium, low
    estimated_benefit: float  # Performance improvement percentage
    estimated_cost: float  # Storage cost in KB
    rationale: str
    supporting_queries: list[str] = field(default_factory=list)
    usage_frequency: int = 0
    current_performance_impact: float = 0.0

    def get_create_statement(self) -> str:
        """Generate the CREATE INDEX statement for this recommendation."""
        index_name = f"idx_{self.table_name}_{'_'.join(self.columns)}"

        if self.index_type == "unique":
            return f"CREATE UNIQUE INDEX {index_name} ON {self.table_name} ({', '.join(self.columns)});"
        elif self.index_type == "partial":
            # This would need specific WHERE conditions based on the analysis
            return f"CREATE INDEX {index_name} ON {self.table_name} ({', '.join(self.columns)}) WHERE {self.columns[0]} IS NOT NULL;"
        elif self.index_type == "covering":
            # Include additional columns for covering index
            return (
                f"CREATE INDEX {index_name} ON {self.table_name} ({', '.join(self.columns[:2])}) INCLUDE ({', '.join(self.columns[2:])});"
                if len(self.columns) > 2
                else f"CREATE INDEX {index_name} ON {self.table_name} ({', '.join(self.columns)});"
            )
        else:  # btree (default)
            return f"CREATE INDEX {index_name} ON {self.table_name} ({', '.join(self.columns)});"


@dataclass
class TableAnalysis:
    """Analysis results for a specific table."""

    table_name: str
    row_count: int
    data_size_kb: float
    existing_indexes: list[dict[str, Any]]
    query_patterns: list[dict[str, Any]]
    column_usage: dict[str, int]
    join_patterns: list[dict[str, Any]]
    performance_issues: list[str]


class IndexOptimizationAdvisor:
    """
    Advanced Index Optimization Advisor

    Analyzes query patterns, table usage, and performance metrics to provide
    intelligent index recommendations with cost-benefit analysis.
    """

    # Index recommendation thresholds
    MIN_QUERY_FREQUENCY = 5  # Minimum query frequency to consider
    MIN_TABLE_SIZE = 1000  # Minimum table size for index recommendations
    MAX_INDEX_OVERHEAD = 0.2  # Max acceptable index overhead (20% of table size)
    PERFORMANCE_THRESHOLD = 50.0  # Performance threshold in milliseconds

    def __init__(
        self,
        db_connection: DatabaseConnection,
        query_analyzer: QueryPerformanceAnalyzer | None = None,
    ) -> None:
        """
        Initialize the Index Optimization Advisor.

        Args:
            db_connection: Database connection instance
            query_analyzer: Optional query performance analyzer for detailed metrics
        """
        self.db = db_connection
        self.query_analyzer = query_analyzer

        # Analysis data
        self._table_analyses: dict[str, TableAnalysis] = {}
        self._query_patterns: dict[str, list[dict[str, Any]]] = {}
        self._index_usage_stats: dict[str, dict[str, Any]] = {}

        # Refresh database metadata
        self._refresh_database_metadata()

    def _refresh_database_metadata(self) -> None:
        """Refresh database metadata and statistics."""
        try:
            # Get all tables
            tables = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )

            for table_row in tables:
                table_name = table_row["name"]
                self._analyze_table(table_name)

            logger.info(f"Refreshed metadata for {len(self._table_analyses)} tables")

        except Exception as e:
            logger.error(f"Failed to refresh database metadata: {e}")

    def _analyze_table(self, table_name: str) -> None:
        """Analyze a specific table for optimization opportunities."""
        try:
            # Get table statistics
            count_result = self.db.fetch_one(
                f"SELECT COUNT(*) as count FROM {table_name}"
            )
            row_count = count_result["count"] if count_result else 0

            # Estimate table size (rough approximation)
            try:
                pragma_result = self.db.fetch_one(f"PRAGMA table_info({table_name})")
                if pragma_result:
                    # Rough estimate: 50 bytes per row on average
                    data_size_kb = (row_count * 50) / 1024
                else:
                    data_size_kb = 0
            except:
                data_size_kb = 0

            # Get existing indexes
            existing_indexes = []
            try:
                indexes = self.db.fetch_all(f"PRAGMA index_list({table_name})")
                for index_row in indexes:
                    index_name = index_row["name"]
                    index_info = self.db.fetch_all(f"PRAGMA index_info({index_name})")
                    existing_indexes.append(
                        {
                            "name": index_name,
                            "unique": bool(index_row["unique"]),
                            "columns": [col["name"] for col in index_info],
                        }
                    )
            except:
                pass

            # Create table analysis
            self._table_analyses[table_name] = TableAnalysis(
                table_name=table_name,
                row_count=row_count,
                data_size_kb=data_size_kb,
                existing_indexes=existing_indexes,
                query_patterns=[],
                column_usage={},
                join_patterns=[],
                performance_issues=[],
            )

        except Exception as e:
            logger.error(f"Failed to analyze table {table_name}: {e}")

    def analyze_query_patterns(self, time_window_hours: int = 24) -> None:
        """
        Analyze query patterns to identify index opportunities.

        Args:
            time_window_hours: Time window for query pattern analysis
        """
        if not self.query_analyzer:
            logger.warning(
                "Query analyzer not available - using basic pattern analysis"
            )
            self._analyze_basic_patterns()
            return

        try:
            # Get slow queries from analyzer
            slow_queries = self.query_analyzer.get_slow_queries(
                threshold_ms=self.PERFORMANCE_THRESHOLD,
                time_window_hours=time_window_hours,
            )

            # Analyze each slow query for indexing opportunities
            for query_result in slow_queries:
                self._analyze_query_for_indexes(
                    query_result.query_text,
                    query_result.execution_count,
                    query_result.avg_execution_time,
                )

            logger.info(
                f"Analyzed {len(slow_queries)} slow queries for indexing opportunities"
            )

        except Exception as e:
            logger.error(f"Failed to analyze query patterns: {e}")
            self._analyze_basic_patterns()

    def _analyze_basic_patterns(self) -> None:
        """Analyze basic query patterns from database schema."""
        try:
            # This is a fallback when query analyzer is not available
            # We analyze foreign key relationships and common query patterns

            for table_name in self._table_analyses:
                # Get table schema
                schema = self.db.fetch_all(f"PRAGMA table_info({table_name})")

                # Look for foreign key patterns
                foreign_keys = self.db.fetch_all(
                    f"PRAGMA foreign_key_list({table_name})"
                )

                for fk in foreign_keys:
                    column_name = fk["from"]
                    # Recommend index on foreign key column
                    self._record_column_usage(
                        table_name, column_name, 10
                    )  # Assume moderate usage

            logger.info("Completed basic pattern analysis")

        except Exception as e:
            logger.error(f"Failed to perform basic pattern analysis: {e}")

    def _analyze_query_for_indexes(
        self, query: str, frequency: int, avg_time: float
    ) -> None:
        """Analyze a specific query for indexing opportunities."""
        query_lower = query.lower()

        # Extract table names
        table_matches = re.findall(r"\bfrom\s+(\w+)", query_lower)
        join_matches = re.findall(r"\bjoin\s+(\w+)", query_lower)
        tables = set(table_matches + join_matches)

        # Extract WHERE conditions
        where_match = re.search(
            r"\bwhere\s+(.+?)(?:\bgroup|\border|\bhaving|\blimit|$)",
            query_lower,
            re.DOTALL,
        )
        if where_match:
            where_clause = where_match.group(1)
            self._analyze_where_clause(where_clause, tables, frequency)

        # Extract ORDER BY columns
        order_match = re.search(
            r"\border\s+by\s+(.+?)(?:\blimit|\bhaving|$)", query_lower
        )
        if order_match:
            order_clause = order_match.group(1)
            self._analyze_order_clause(order_clause, tables, frequency)

        # Extract JOIN conditions
        join_patterns = re.findall(
            r"(\w+)\s*\.\s*(\w+)\s*=\s*(\w+)\s*\.\s*(\w+)", query_lower
        )
        for pattern in join_patterns:
            table1, col1, table2, col2 = pattern
            self._record_join_pattern(table1, col1, table2, col2, frequency)

    def _analyze_where_clause(
        self, where_clause: str, tables: set[str], frequency: int
    ) -> None:
        """Analyze WHERE clause for column usage patterns."""
        # Extract column conditions
        condition_patterns = [
            r"(\w+)\s*[=<>!]+",  # column = value
            r"(\w+)\s+LIKE",  # column LIKE
            r"(\w+)\s+IN\s*\(",  # column IN (...)
            r"(\w+)\s+BETWEEN",  # column BETWEEN
            r"(\w+)\s+IS\s+(?:NOT\s+)?NULL",  # column IS NULL
        ]

        for pattern in condition_patterns:
            matches = re.findall(pattern, where_clause, re.IGNORECASE)
            for column in matches:
                # Try to match column to table
                for table in tables:
                    if table in self._table_analyses:
                        self._record_column_usage(table, column, frequency)

    def _analyze_order_clause(
        self, order_clause: str, tables: set[str], frequency: int
    ) -> None:
        """Analyze ORDER BY clause for column usage patterns."""
        # Extract column names from ORDER BY
        columns = re.findall(r"(\w+)(?:\s+(?:ASC|DESC))?", order_clause, re.IGNORECASE)

        for column in columns:
            for table in tables:
                if table in self._table_analyses:
                    # ORDER BY columns are good candidates for indexes
                    self._record_column_usage(
                        table, column, frequency * 2
                    )  # Higher weight

    def _record_column_usage(
        self, table_name: str, column_name: str, frequency: int
    ) -> None:
        """Record column usage for indexing analysis."""
        if table_name in self._table_analyses:
            analysis = self._table_analyses[table_name]
            if column_name not in analysis.column_usage:
                analysis.column_usage[column_name] = 0
            analysis.column_usage[column_name] += frequency

    def _record_join_pattern(
        self, table1: str, col1: str, table2: str, col2: str, frequency: int
    ) -> None:
        """Record JOIN patterns for index recommendations."""
        for table, col in [(table1, col1), (table2, col2)]:
            if table in self._table_analyses:
                analysis = self._table_analyses[table]

                join_pattern = {
                    "joined_table": table2 if table == table1 else table1,
                    "local_column": col,
                    "remote_column": col2 if table == table1 else col1,
                    "frequency": frequency,
                }

                analysis.join_patterns.append(join_pattern)
                # Record high column usage for JOIN columns
                self._record_column_usage(table, col, frequency * 3)

    def generate_recommendations(self) -> list[IndexRecommendation]:
        """
        Generate comprehensive index recommendations.

        Returns:
            List of index recommendations sorted by priority
        """
        recommendations = []

        for table_name, analysis in self._table_analyses.items():
            # Skip small tables
            if analysis.row_count < self.MIN_TABLE_SIZE:
                continue

            # Generate missing index recommendations
            recommendations.extend(self._recommend_missing_indexes(analysis))

            # Generate composite index recommendations
            recommendations.extend(self._recommend_composite_indexes(analysis))

            # Generate covering index recommendations
            recommendations.extend(self._recommend_covering_indexes(analysis))

            # Identify redundant indexes
            recommendations.extend(self._identify_redundant_indexes(analysis))

            # Identify unused indexes
            recommendations.extend(self._identify_unused_indexes(analysis))

        # Sort recommendations by priority and estimated benefit
        recommendations.sort(
            key=lambda x: (
                self._priority_score(x.priority),
                -x.estimated_benefit,
                -x.usage_frequency,
            )
        )

        logger.info(f"Generated {len(recommendations)} index recommendations")
        return recommendations

    def _recommend_missing_indexes(
        self, analysis: TableAnalysis
    ) -> list[IndexRecommendation]:
        """Recommend missing single-column indexes."""
        recommendations = []
        existing_columns = set()

        # Get columns that already have indexes
        for index in analysis.existing_indexes:
            if len(index["columns"]) == 1:
                existing_columns.add(index["columns"][0])

        # Analyze column usage
        for column, frequency in analysis.column_usage.items():
            if column in existing_columns:
                continue

            if frequency >= self.MIN_QUERY_FREQUENCY:
                # Estimate benefit and cost
                estimated_benefit = min(50.0, frequency * 2)  # Cap at 50%
                estimated_cost = analysis.row_count * 0.01  # Rough estimate in KB

                priority = self._calculate_priority(
                    frequency, estimated_benefit, estimated_cost
                )

                recommendation = IndexRecommendation(
                    table_name=analysis.table_name,
                    columns=[column],
                    index_type="btree",
                    recommendation_type="missing",
                    priority=priority,
                    estimated_benefit=estimated_benefit,
                    estimated_cost=estimated_cost,
                    rationale=f"Column '{column}' is used in {frequency} queries but has no index",
                    usage_frequency=frequency,
                )

                recommendations.append(recommendation)

        return recommendations

    def _recommend_composite_indexes(
        self, analysis: TableAnalysis
    ) -> list[IndexRecommendation]:
        """Recommend composite indexes for multi-column queries."""
        recommendations = []

        # Find column combinations that are frequently used together
        column_pairs = defaultdict(int)

        # This is simplified - in practice, you'd analyze actual query patterns
        # For now, we'll look at JOIN patterns and high-usage columns
        high_usage_columns = [
            col
            for col, freq in analysis.column_usage.items()
            if freq >= self.MIN_QUERY_FREQUENCY
        ]

        # Recommend composite indexes for columns used in JOINs
        for join_pattern in analysis.join_patterns:
            local_col = join_pattern["local_column"]
            frequency = join_pattern["frequency"]

            # Look for other frequently used columns to combine with
            for other_col in high_usage_columns:
                if other_col != local_col:
                    columns = sorted([local_col, other_col])

                    # Check if this combination already has an index
                    has_existing = any(
                        sorted(idx["columns"]) == columns
                        for idx in analysis.existing_indexes
                    )

                    if not has_existing:
                        estimated_benefit = min(30.0, frequency * 1.5)
                        estimated_cost = (
                            analysis.row_count * 0.015
                        )  # Slightly more than single column

                        priority = self._calculate_priority(
                            frequency, estimated_benefit, estimated_cost
                        )

                        recommendation = IndexRecommendation(
                            table_name=analysis.table_name,
                            columns=columns,
                            index_type="btree",
                            recommendation_type="composite",
                            priority=priority,
                            estimated_benefit=estimated_benefit,
                            estimated_cost=estimated_cost,
                            rationale=f"Composite index on {columns} for JOIN and WHERE optimization",
                            usage_frequency=frequency,
                        )

                        recommendations.append(recommendation)

        return recommendations

    def _recommend_covering_indexes(
        self, analysis: TableAnalysis
    ) -> list[IndexRecommendation]:
        """Recommend covering indexes to avoid table lookups."""
        recommendations = []

        # This is a simplified implementation
        # In practice, you'd analyze SELECT columns and WHERE/ORDER BY patterns

        # Look for opportunities where we can include additional columns
        for index in analysis.existing_indexes:
            if len(index["columns"]) == 1:
                base_column = index["columns"][0]

                # Find other columns frequently accessed with this one
                candidates = [
                    col
                    for col, freq in analysis.column_usage.items()
                    if col != base_column and freq >= self.MIN_QUERY_FREQUENCY // 2
                ]

                if candidates:
                    # Limit to 2-3 additional columns for practicality
                    covering_columns = index["columns"] + candidates[:2]

                    estimated_benefit = (
                        20.0  # Covering indexes provide moderate benefit
                    )
                    estimated_cost = analysis.row_count * 0.02  # Higher storage cost

                    priority = self._calculate_priority(
                        analysis.column_usage[base_column],
                        estimated_benefit,
                        estimated_cost,
                    )

                    recommendation = IndexRecommendation(
                        table_name=analysis.table_name,
                        columns=covering_columns,
                        index_type="covering",
                        recommendation_type="optimize",
                        priority=priority,
                        estimated_benefit=estimated_benefit,
                        estimated_cost=estimated_cost,
                        rationale=f"Covering index to avoid table lookups for columns {covering_columns}",
                        usage_frequency=analysis.column_usage[base_column],
                    )

                    recommendations.append(recommendation)

        return recommendations

    def _identify_redundant_indexes(
        self, analysis: TableAnalysis
    ) -> list[IndexRecommendation]:
        """Identify redundant indexes that can be removed."""
        recommendations = []

        # Look for indexes that are prefixes of other indexes
        for i, index1 in enumerate(analysis.existing_indexes):
            for j, index2 in enumerate(analysis.existing_indexes):
                if i != j and len(index1["columns"]) < len(index2["columns"]):
                    # Check if index1 is a prefix of index2
                    if index2["columns"][: len(index1["columns"])] == index1["columns"]:
                        # index1 is redundant
                        recommendation = IndexRecommendation(
                            table_name=analysis.table_name,
                            columns=index1["columns"],
                            index_type="redundant",
                            recommendation_type="redundant",
                            priority="medium",
                            estimated_benefit=0.0,  # Removal saves space but doesn't improve performance
                            estimated_cost=-analysis.row_count
                            * 0.01,  # Negative cost = space saving
                            rationale=f"Index {index1['name']} is redundant with {index2['name']}",
                            usage_frequency=0,
                        )

                        recommendations.append(recommendation)
                        break

        return recommendations

    def _identify_unused_indexes(
        self, analysis: TableAnalysis
    ) -> list[IndexRecommendation]:
        """Identify indexes that appear to be unused."""
        recommendations = []

        # This is simplified - in practice, you'd need query execution statistics
        indexed_columns = set()
        for index in analysis.existing_indexes:
            indexed_columns.update(index["columns"])

        used_columns = set(analysis.column_usage.keys())

        for index in analysis.existing_indexes:
            # If none of the index columns appear in column usage, it might be unused
            if not any(col in used_columns for col in index["columns"]):
                recommendation = IndexRecommendation(
                    table_name=analysis.table_name,
                    columns=index["columns"],
                    index_type="unused",
                    recommendation_type="redundant",
                    priority="low",
                    estimated_benefit=0.0,
                    estimated_cost=-analysis.row_count * 0.01,  # Space saving
                    rationale=f"Index {index['name']} appears unused in recent query patterns",
                    usage_frequency=0,
                )

                recommendations.append(recommendation)

        return recommendations

    def _calculate_priority(self, frequency: int, benefit: float, cost: float) -> str:
        """Calculate recommendation priority."""
        # Simple scoring based on frequency, benefit, and cost
        score = (frequency * benefit) / max(cost, 1)

        if score > 100:
            return "critical"
        elif score > 50:
            return "high"
        elif score > 20:
            return "medium"
        else:
            return "low"

    def _priority_score(self, priority: str) -> int:
        """Convert priority string to numeric score for sorting."""
        scores = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        return scores.get(priority, 5)

    def analyze_index_effectiveness(self) -> dict[str, Any]:
        """Analyze the effectiveness of existing indexes."""
        effectiveness_report = {
            "total_tables": len(self._table_analyses),
            "total_indexes": 0,
            "effective_indexes": 0,
            "redundant_indexes": 0,
            "unused_indexes": 0,
            "missing_indexes": 0,
            "overall_score": 0.0,
            "details": [],
        }

        for table_name, analysis in self._table_analyses.items():
            table_report = {
                "table": table_name,
                "row_count": analysis.row_count,
                "existing_indexes": len(analysis.existing_indexes),
                "column_usage_patterns": len(analysis.column_usage),
                "effectiveness_score": 0.0,
            }

            effectiveness_report["total_indexes"] += len(analysis.existing_indexes)

            # Calculate effectiveness score for this table
            if analysis.column_usage:
                indexed_columns = set()
                for index in analysis.existing_indexes:
                    indexed_columns.update(index["columns"])

                used_columns = set(analysis.column_usage.keys())

                if used_columns:
                    coverage = len(indexed_columns.intersection(used_columns)) / len(
                        used_columns
                    )
                    table_report["effectiveness_score"] = coverage * 100

                    if coverage > 0.8:
                        effectiveness_report["effective_indexes"] += len(
                            analysis.existing_indexes
                        )

            effectiveness_report["details"].append(table_report)

        # Calculate overall effectiveness score
        if effectiveness_report["total_indexes"] > 0:
            effectiveness_report["overall_score"] = (
                effectiveness_report["effective_indexes"]
                / effectiveness_report["total_indexes"]
                * 100
            )

        return effectiveness_report

    def generate_optimization_report(self) -> dict[str, Any]:
        """Generate a comprehensive optimization report."""
        recommendations = self.generate_recommendations()
        effectiveness = self.analyze_index_effectiveness()

        # Categorize recommendations
        by_type = defaultdict(list)
        by_priority = defaultdict(list)

        for rec in recommendations:
            by_type[rec.recommendation_type].append(rec)
            by_priority[rec.priority].append(rec)

        # Calculate potential benefits
        total_benefit = sum(rec.estimated_benefit for rec in recommendations)
        total_cost = sum(rec.estimated_cost for rec in recommendations)

        report = {
            "summary": {
                "total_recommendations": len(recommendations),
                "total_estimated_benefit": round(total_benefit, 2),
                "total_estimated_cost_kb": round(total_cost, 2),
                "net_benefit_ratio": round(total_benefit / max(abs(total_cost), 1), 2),
            },
            "by_priority": {
                priority: len(recs) for priority, recs in by_priority.items()
            },
            "by_type": {rec_type: len(recs) for rec_type, recs in by_type.items()},
            "effectiveness_analysis": effectiveness,
            "top_recommendations": [
                {
                    "table": rec.table_name,
                    "columns": rec.columns,
                    "type": rec.recommendation_type,
                    "priority": rec.priority,
                    "benefit": rec.estimated_benefit,
                    "cost": rec.estimated_cost,
                    "rationale": rec.rationale,
                    "create_statement": rec.get_create_statement(),
                }
                for rec in recommendations[:10]  # Top 10 recommendations
            ],
            "recommendations": [
                {
                    "table": rec.table_name,
                    "columns": rec.columns,
                    "type": rec.recommendation_type,
                    "priority": rec.priority,
                    "benefit": rec.estimated_benefit,
                    "cost": rec.estimated_cost,
                    "rationale": rec.rationale,
                    "create_statement": rec.get_create_statement(),
                    "usage_frequency": rec.usage_frequency,
                }
                for rec in recommendations
            ],
        }

        return report


def main() -> Any:
    """CLI interface for the Index Optimization Advisor."""
    import argparse

    parser = argparse.ArgumentParser(description="Index Optimization Advisor")
    parser.add_argument("--db-path", required=True, help="Database file path")
    parser.add_argument("--analyze", action="store_true", help="Analyze query patterns")
    parser.add_argument(
        "--recommend", action="store_true", help="Generate recommendations"
    )
    parser.add_argument(
        "--report", action="store_true", help="Generate full optimization report"
    )
    parser.add_argument(
        "--effectiveness", action="store_true", help="Analyze index effectiveness"
    )
    parser.add_argument(
        "--time-window", type=int, default=24, help="Time window in hours for analysis"
    )
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument(
        "--sql-output", help="Output SQL file for CREATE INDEX statements"
    )

    args = parser.parse_args()

    try:
        # Initialize advisor
        db = DatabaseConnection(args.db_path)

        # Try to initialize query analyzer
        query_analyzer = None
        try:
            query_analyzer = QueryPerformanceAnalyzer(db)
        except:
            logger.warning("Query analyzer not available - using basic analysis")

        advisor = IndexOptimizationAdvisor(db, query_analyzer)

        results = {}

        if args.analyze or args.recommend or args.report:
            print("Analyzing query patterns...")
            advisor.analyze_query_patterns(args.time_window)

        if args.effectiveness:
            effectiveness = advisor.analyze_index_effectiveness()
            results["effectiveness"] = effectiveness

            print("Index Effectiveness Analysis:")
            print(f"Total Tables: {effectiveness['total_tables']}")
            print(f"Total Indexes: {effectiveness['total_indexes']}")
            print(f"Overall Effectiveness: {effectiveness['overall_score']:.1f}%")

        if args.recommend:
            recommendations = advisor.generate_recommendations()
            results["recommendations"] = [
                {
                    "table": rec.table_name,
                    "columns": rec.columns,
                    "type": rec.recommendation_type,
                    "priority": rec.priority,
                    "benefit": rec.estimated_benefit,
                    "cost": rec.estimated_cost,
                    "rationale": rec.rationale,
                    "create_statement": rec.get_create_statement(),
                }
                for rec in recommendations
            ]

            print(f"\nIndex Recommendations ({len(recommendations)} total):")
            for i, rec in enumerate(recommendations[:10], 1):  # Show top 10
                print(
                    f"{i}. {rec.priority.upper()}: {rec.table_name}.{', '.join(rec.columns)}"
                )
                print(f"   Type: {rec.recommendation_type}")
                print(
                    f"   Benefit: {rec.estimated_benefit:.1f}%, Cost: {rec.estimated_cost:.1f}KB"
                )
                print(f"   Rationale: {rec.rationale}")
                print(f"   SQL: {rec.get_create_statement()}")
                print()

        if args.report:
            report = advisor.generate_optimization_report()
            results["full_report"] = report

            print("\nOptimization Report Summary:")
            print(
                f"Total Recommendations: {report['summary']['total_recommendations']}"
            )
            print(
                f"Estimated Benefit: {report['summary']['total_estimated_benefit']:.1f}%"
            )
            print(
                f"Estimated Cost: {report['summary']['total_estimated_cost_kb']:.1f}KB"
            )
            print(f"Net Benefit Ratio: {report['summary']['net_benefit_ratio']:.2f}")

            print("\nBy Priority:")
            for priority, count in report["by_priority"].items():
                print(f"  {priority.upper()}: {count}")

        # Save results if requested
        if args.output and results:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Results saved to {args.output}")

        # Save SQL statements if requested
        if args.sql_output and "recommendations" in results:
            with open(args.sql_output, "w") as f:
                f.write("-- Index Optimization Recommendations\n")
                f.write(f"-- Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                for rec in results["recommendations"]:
                    if (
                        rec["recommendation_type"] != "redundant"
                    ):  # Don't include DROP statements
                        f.write(f"-- {rec['priority'].upper()}: {rec['rationale']}\n")
                        f.write(f"{rec['create_statement']}\n\n")

            print(f"SQL statements saved to {args.sql_output}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
