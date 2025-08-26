"""
Performance Metrics Collection and Reporting

Provides advanced metrics collection, monitoring, and reporting capabilities:
- Real-time metrics collection
- Performance threshold validation
- Historical trend analysis
- Alert generation
"""

import csv
import json
import sqlite3
import statistics
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class PerformanceThresholds:
    """Performance thresholds for alerting"""
    max_response_time_ms: float = 1000.0
    max_p95_ms: float = 2000.0
    max_p99_ms: float = 5000.0
    min_throughput_rps: float = 10.0
    max_error_rate_percent: float = 1.0
    max_memory_mb: float = 1024.0
    max_cpu_percent: float = 80.0

    # Degradation thresholds
    response_time_degradation_percent: float = 20.0
    throughput_degradation_percent: float = 15.0

    def validate_metrics(self, metrics: dict[str, Any]) -> list[str]:
        """Validate metrics against thresholds and return violations"""
        violations = []

        if metrics.get('avg_response_time', 0) > self.max_response_time_ms:
            violations.append(
                f"Average response time ({metrics['avg_response_time']:.2f}ms) "
                f"exceeds threshold ({self.max_response_time_ms}ms)"
            )

        if metrics.get('p95', 0) > self.max_p95_ms:
            violations.append(
                f"P95 response time ({metrics['p95']:.2f}ms) "
                f"exceeds threshold ({self.max_p95_ms}ms)"
            )

        if metrics.get('p99', 0) > self.max_p99_ms:
            violations.append(
                f"P99 response time ({metrics['p99']:.2f}ms) "
                f"exceeds threshold ({self.max_p99_ms}ms)"
            )

        if metrics.get('throughput', float('inf')) < self.min_throughput_rps:
            violations.append(
                f"Throughput ({metrics.get('throughput', 0):.2f} req/s) "
                f"below threshold ({self.min_throughput_rps} req/s)"
            )

        if metrics.get('error_rate', 0) > self.max_error_rate_percent:
            violations.append(
                f"Error rate ({metrics.get('error_rate', 0):.2f}%) "
                f"exceeds threshold ({self.max_error_rate_percent}%)"
            )

        if metrics.get('peak_memory_mb', 0) > self.max_memory_mb:
            violations.append(
                f"Peak memory ({metrics.get('peak_memory_mb', 0):.2f}MB) "
                f"exceeds threshold ({self.max_memory_mb}MB)"
            )

        if metrics.get('peak_cpu', 0) > self.max_cpu_percent:
            violations.append(
                f"Peak CPU ({metrics.get('peak_cpu', 0):.2f}%) "
                f"exceeds threshold ({self.max_cpu_percent}%)"
            )

        return violations


@dataclass
class MetricsSnapshot:
    """Point-in-time metrics snapshot"""
    timestamp: datetime
    scenario: str
    concurrent_users: int
    throughput: float
    avg_response_time: float
    p50: float
    p95: float
    p99: float
    error_rate: float
    memory_mb: float
    cpu_percent: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class MetricsCollector:
    """Collects and aggregates performance metrics"""

    def __init__(self,
                 storage_path: Path | None = None,
                 window_size: int = 100):
        """
        Initialize metrics collector

        Args:
            storage_path: Path for persistent storage
            window_size: Size of sliding window for real-time metrics
        """
        self.storage_path = storage_path or Path("performance_metrics.db")
        self.window_size = window_size

        # Real-time metrics windows
        self.response_times_window = deque(maxlen=window_size)
        self.throughput_window = deque(maxlen=window_size)
        self.error_rate_window = deque(maxlen=window_size)

        # Historical data
        self.snapshots: list[MetricsSnapshot] = []

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for metrics storage"""
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                scenario TEXT NOT NULL,
                concurrent_users INTEGER,
                throughput REAL,
                avg_response_time REAL,
                p50 REAL,
                p95 REAL,
                p99 REAL,
                error_rate REAL,
                memory_mb REAL,
                cpu_percent REAL,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON metrics(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scenario
            ON metrics(scenario)
        """)

        conn.commit()
        conn.close()

    def record_snapshot(self, snapshot: MetricsSnapshot):
        """Record a metrics snapshot"""
        self.snapshots.append(snapshot)

        # Update sliding windows
        self.response_times_window.append(snapshot.avg_response_time)
        self.throughput_window.append(snapshot.throughput)
        self.error_rate_window.append(snapshot.error_rate)

        # Persist to database
        self._persist_snapshot(snapshot)

    def _persist_snapshot(self, snapshot: MetricsSnapshot):
        """Persist snapshot to database"""
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO metrics (
                timestamp, scenario, concurrent_users, throughput,
                avg_response_time, p50, p95, p99, error_rate,
                memory_mb, cpu_percent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.timestamp.isoformat(),
            snapshot.scenario,
            snapshot.concurrent_users,
            snapshot.throughput,
            snapshot.avg_response_time,
            snapshot.p50,
            snapshot.p95,
            snapshot.p99,
            snapshot.error_rate,
            snapshot.memory_mb,
            snapshot.cpu_percent
        ))

        conn.commit()
        conn.close()

    def get_real_time_stats(self) -> dict[str, Any]:
        """Get real-time statistics from sliding windows"""
        stats = {}

        if self.response_times_window:
            stats['current_avg_response_time'] = statistics.mean(self.response_times_window)
            stats['current_response_time_trend'] = self._calculate_trend(
                list(self.response_times_window)
            )

        if self.throughput_window:
            stats['current_avg_throughput'] = statistics.mean(self.throughput_window)
            stats['current_throughput_trend'] = self._calculate_trend(
                list(self.throughput_window)
            )

        if self.error_rate_window:
            stats['current_avg_error_rate'] = statistics.mean(self.error_rate_window)
            stats['current_error_rate_trend'] = self._calculate_trend(
                list(self.error_rate_window)
            )

        return stats

    def _calculate_trend(self, values: list[float]) -> str:
        """Calculate trend direction"""
        if len(values) < 2:
            return "stable"

        # Simple linear regression
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable"

        slope = numerator / denominator

        # Determine trend based on slope
        if abs(slope) < 0.01:
            return "stable"
        elif slope > 0:
            return "increasing"
        else:
            return "decreasing"

    def get_historical_metrics(
        self,
        scenario: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None
    ) -> list[MetricsSnapshot]:
        """Retrieve historical metrics from database"""
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.cursor()

        query = "SELECT * FROM metrics WHERE 1=1"
        params = []

        if scenario:
            query += " AND scenario = ?"
            params.append(scenario)

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY timestamp"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        snapshots = []
        for row in rows:
            snapshots.append(MetricsSnapshot(
                timestamp=datetime.fromisoformat(row[1]),
                scenario=row[2],
                concurrent_users=row[3],
                throughput=row[4],
                avg_response_time=row[5],
                p50=row[6],
                p95=row[7],
                p99=row[8],
                error_rate=row[9],
                memory_mb=row[10],
                cpu_percent=row[11]
            ))

        return snapshots

    def detect_regression(
        self,
        current_metrics: dict[str, Any],
        baseline_scenario: str,
        threshold_percent: float = 10.0
    ) -> list[str]:
        """Detect performance regression compared to baseline"""
        # Get baseline metrics
        baseline_snapshots = self.get_historical_metrics(
            scenario=baseline_scenario,
            start_time=datetime.now() - timedelta(days=7)
        )

        if not baseline_snapshots:
            return []

        regressions = []

        # Calculate baseline averages
        baseline_response_times = [s.avg_response_time for s in baseline_snapshots]
        baseline_throughput = [s.throughput for s in baseline_snapshots]

        baseline_avg_response = statistics.mean(baseline_response_times)
        baseline_avg_throughput = statistics.mean(baseline_throughput)

        # Check for regression
        current_response = current_metrics.get('avg_response_time', 0)
        current_throughput = current_metrics.get('throughput', 0)

        response_degradation = ((current_response - baseline_avg_response) /
                               baseline_avg_response * 100)

        if response_degradation > threshold_percent:
            regressions.append(
                f"Response time regression: {response_degradation:.1f}% "
                f"slower than baseline"
            )

        throughput_degradation = ((baseline_avg_throughput - current_throughput) /
                                 baseline_avg_throughput * 100)

        if throughput_degradation > threshold_percent:
            regressions.append(
                f"Throughput regression: {throughput_degradation:.1f}% "
                f"lower than baseline"
            )

        return regressions

    def export_metrics(self, format: str = "json", output_path: Path | None = None):
        """Export metrics to file"""
        output_path = output_path or Path(f"metrics_export_{datetime.now():%Y%m%d_%H%M%S}.{format}")

        if format == "json":
            data = [s.to_dict() for s in self.snapshots]
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)

        elif format == "csv":
            if not self.snapshots:
                return

            with open(output_path, 'w', newline='') as f:
                fieldnames = self.snapshots[0].to_dict().keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for snapshot in self.snapshots:
                    writer.writerow(snapshot.to_dict())


class PerformanceReport:
    """Generate comprehensive performance reports"""

    def __init__(self, collector: MetricsCollector, thresholds: PerformanceThresholds):
        self.collector = collector
        self.thresholds = thresholds

    def generate_summary(self, scenarios: list[str]) -> str:
        """Generate summary report for multiple scenarios"""
        report = []
        report.append("=" * 80)
        report.append("PERFORMANCE TEST SUMMARY REPORT")
        report.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
        report.append("=" * 80)

        for scenario in scenarios:
            snapshots = self.collector.get_historical_metrics(
                scenario=scenario,
                start_time=datetime.now() - timedelta(hours=1)
            )

            if not snapshots:
                continue

            report.append(f"\n## Scenario: {scenario}")
            report.append("-" * 40)

            # Calculate aggregates
            avg_response = statistics.mean([s.avg_response_time for s in snapshots])
            avg_throughput = statistics.mean([s.throughput for s in snapshots])
            max_users = max([s.concurrent_users for s in snapshots])
            avg_error_rate = statistics.mean([s.error_rate for s in snapshots])

            report.append(f"Samples: {len(snapshots)}")
            report.append(f"Max Concurrent Users: {max_users}")
            report.append(f"Avg Response Time: {avg_response:.2f}ms")
            report.append(f"Avg Throughput: {avg_throughput:.2f} req/s")
            report.append(f"Avg Error Rate: {avg_error_rate:.2f}%")

            # Check thresholds
            latest_snapshot = snapshots[-1]
            violations = self.thresholds.validate_metrics({
                'avg_response_time': latest_snapshot.avg_response_time,
                'p95': latest_snapshot.p95,
                'p99': latest_snapshot.p99,
                'throughput': latest_snapshot.throughput,
                'error_rate': latest_snapshot.error_rate,
                'peak_memory_mb': latest_snapshot.memory_mb,
                'peak_cpu': latest_snapshot.cpu_percent
            })

            if violations:
                report.append("\n### Threshold Violations:")
                for violation in violations:
                    report.append(f"  - {violation}")
            else:
                report.append("\n### Status: All thresholds passed")

        # Real-time stats
        rt_stats = self.collector.get_real_time_stats()
        if rt_stats:
            report.append("\n## Real-Time Metrics")
            report.append("-" * 40)
            for key, value in rt_stats.items():
                if isinstance(value, float):
                    report.append(f"{key}: {value:.2f}")
                else:
                    report.append(f"{key}: {value}")

        report.append("\n" + "=" * 80)
        return "\n".join(report)

    def generate_html_report(self, scenarios: list[str]) -> str:
        """Generate HTML performance report with charts"""
        html = []
        html.append("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Performance Test Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                h2 { color: #666; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .violation { color: red; font-weight: bold; }
                .success { color: green; font-weight: bold; }
                .metric-card {
                    display: inline-block;
                    border: 1px solid #ddd;
                    padding: 15px;
                    margin: 10px;
                    border-radius: 5px;
                    background: #f9f9f9;
                }
                .metric-value { font-size: 24px; font-weight: bold; color: #333; }
                .metric-label { color: #666; margin-top: 5px; }
            </style>
        </head>
        <body>
        """)

        html.append("<h1>Performance Test Report</h1>")
        html.append(f"<p>Generated: {datetime.now():%Y-%m-%d %H:%M:%S}</p>")

        for scenario in scenarios:
            snapshots = self.collector.get_historical_metrics(
                scenario=scenario,
                start_time=datetime.now() - timedelta(hours=1)
            )

            if not snapshots:
                continue

            html.append(f"<h2>{scenario}</h2>")

            # Summary metrics cards
            latest = snapshots[-1]
            html.append('<div class="metrics-container">')

            metrics_cards = [
                ("Response Time", f"{latest.avg_response_time:.2f}ms", "avg"),
                ("P95", f"{latest.p95:.2f}ms", "p95"),
                ("P99", f"{latest.p99:.2f}ms", "p99"),
                ("Throughput", f"{latest.throughput:.2f} req/s", "throughput"),
                ("Error Rate", f"{latest.error_rate:.2f}%", "error"),
                ("Users", str(latest.concurrent_users), "users")
            ]

            for label, value, metric_type in metrics_cards:
                html.append(f'''
                <div class="metric-card">
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}</div>
                </div>
                ''')

            html.append('</div>')

            # Detailed table
            html.append("<table>")
            html.append("<tr><th>Timestamp</th><th>Users</th><th>Response Time</th>"
                       "<th>Throughput</th><th>Error Rate</th><th>Memory</th><th>CPU</th></tr>")

            for snapshot in snapshots[-10:]:  # Last 10 snapshots
                html.append(f"""
                <tr>
                    <td>{snapshot.timestamp:%H:%M:%S}</td>
                    <td>{snapshot.concurrent_users}</td>
                    <td>{snapshot.avg_response_time:.2f}ms</td>
                    <td>{snapshot.throughput:.2f} req/s</td>
                    <td>{snapshot.error_rate:.2f}%</td>
                    <td>{snapshot.memory_mb:.2f}MB</td>
                    <td>{snapshot.cpu_percent:.2f}%</td>
                </tr>
                """)

            html.append("</table>")

            # Threshold validation
            violations = self.thresholds.validate_metrics({
                'avg_response_time': latest.avg_response_time,
                'p95': latest.p95,
                'p99': latest.p99,
                'throughput': latest.throughput,
                'error_rate': latest.error_rate,
                'peak_memory_mb': latest.memory_mb,
                'peak_cpu': latest.cpu_percent
            })

            if violations:
                html.append('<h3 class="violation">Threshold Violations:</h3>')
                html.append("<ul>")
                for violation in violations:
                    html.append(f'<li class="violation">{violation}</li>')
                html.append("</ul>")
            else:
                html.append('<h3 class="success">All thresholds passed</h3>')

        html.append("</body></html>")
        return "".join(html)
