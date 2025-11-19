#!/usr/bin/env python3
"""
Structured Log Analysis System
Advanced log analysis with pattern recognition, anomaly detection, and predictive analytics
for AI Enhanced PDF Scholar production monitoring.
"""

import argparse
import json
import logging
import re
import statistics
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Union

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Models and Enums
# ============================================================================


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AnalysisType(Enum):
    """Analysis type enumeration."""

    ERROR_PATTERNS = "error_patterns"
    PERFORMANCE_BOTTLENECKS = "performance_bottlenecks"
    SECURITY_EVENTS = "security_events"
    BUSINESS_METRICS = "business_metrics"
    ANOMALY_DETECTION = "anomaly_detection"
    PREDICTIVE_ANALYSIS = "predictive_analysis"


@dataclass
class LogEntry:
    """Structured log entry."""

    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    module: str | None = None
    function: str | None = None
    line_number: int | None = None
    request_id: str | None = None
    user_id: str | None = None
    ip_address: str | None = None
    response_time: float | None = None
    status_code: int | None = None
    endpoint: str | None = None
    raw_line: str | None = None
    additional_fields: dict[str, Any] | None = None


@dataclass
class PatternMatch:
    """Pattern matching result."""

    pattern_id: str
    pattern_name: str
    pattern_regex: str
    matches: list[LogEntry]
    frequency: int
    first_seen: datetime
    last_seen: datetime
    severity: str
    impact_score: float
    confidence: float


@dataclass
class PerformanceBottleneck:
    """Performance bottleneck analysis result."""

    endpoint: str
    avg_response_time: float
    max_response_time: float
    min_response_time: float
    percentile_95: float
    request_count: int
    error_rate: float
    trend: str  # "increasing", "decreasing", "stable"
    severity: str
    recommendations: list[str]


@dataclass
class SecurityEvent:
    """Security event analysis result."""

    event_type: str
    source_ip: str
    target_endpoint: str
    frequency: int
    first_seen: datetime
    last_seen: datetime
    risk_level: str
    attack_pattern: str | None = None
    countermeasures: list[str] = None


@dataclass
class BusinessMetric:
    """Business metric extraction result."""

    metric_name: str
    metric_value: Union[int, float]
    metric_type: str  # "counter", "gauge", "rate"
    time_period: str
    trend: str | None = None
    comparison: dict[str, Any] | None = None


@dataclass
class Anomaly:
    """Anomaly detection result."""

    anomaly_type: str
    description: str
    severity: str
    confidence: float
    affected_components: list[str]
    time_window: tuple[datetime, datetime]
    baseline_value: float | None = None
    anomalous_value: float | None = None
    deviation_score: float | None = None


@dataclass
class PredictiveInsight:
    """Predictive analysis result."""

    prediction_type: str
    prediction: str
    confidence: float
    time_horizon: str
    supporting_data: dict[str, Any]
    recommended_actions: list[str]
    risk_level: str


# ============================================================================
# Log Parsing and Pattern Definitions
# ============================================================================


class LogPatternLibrary:
    """Library of log patterns for various types of analysis."""

    ERROR_PATTERNS = {
        "database_connection_error": {
            "name": "Database Connection Error",
            "regex": r"(?i)(database|db|sql).*(connection|connect).*(error|fail|timeout)",
            "severity": "high",
            "impact_score": 0.9,
        },
        "out_of_memory": {
            "name": "Out of Memory Error",
            "regex": r"(?i)(out of memory|oom|memory.*error|malloc.*fail)",
            "severity": "critical",
            "impact_score": 0.95,
        },
        "api_timeout": {
            "name": "API Timeout Error",
            "regex": r"(?i)(timeout|timed out).*(api|request|response)",
            "severity": "medium",
            "impact_score": 0.6,
        },
        "file_not_found": {
            "name": "File Not Found Error",
            "regex": r"(?i)(file not found|no such file|filenotfound)",
            "severity": "low",
            "impact_score": 0.3,
        },
        "authentication_failure": {
            "name": "Authentication Failure",
            "regex": r"(?i)(auth.*fail|authentication.*error|login.*fail|invalid.*credential)",
            "severity": "high",
            "impact_score": 0.8,
        },
        "permission_denied": {
            "name": "Permission Denied",
            "regex": r"(?i)(permission denied|access denied|forbidden|unauthorized)",
            "severity": "medium",
            "impact_score": 0.5,
        },
        "rate_limit_exceeded": {
            "name": "Rate Limit Exceeded",
            "regex": r"(?i)(rate.*limit|too many requests|throttle)",
            "severity": "medium",
            "impact_score": 0.6,
        },
        "external_service_error": {
            "name": "External Service Error",
            "regex": r"(?i)(external.*service|third.*party|upstream).*(error|fail|unavailable)",
            "severity": "high",
            "impact_score": 0.7,
        },
    }

    PERFORMANCE_PATTERNS = {
        "slow_query": {
            "name": "Slow Database Query",
            "regex": r"(?i)slow.*query|query.*time.*([0-9]+\.?[0-9]*).*s",
            "severity": "medium",
            "impact_score": 0.6,
        },
        "high_response_time": {
            "name": "High Response Time",
            "regex": r"response.*time.*([0-9]+\.?[0-9]*).*ms",
            "severity": "medium",
            "impact_score": 0.5,
        },
        "memory_usage_high": {
            "name": "High Memory Usage",
            "regex": r"(?i)memory.*usage.*([0-9]+\.?[0-9]*)%",
            "severity": "medium",
            "impact_score": 0.6,
        },
        "cpu_usage_high": {
            "name": "High CPU Usage",
            "regex": r"(?i)cpu.*usage.*([0-9]+\.?[0-9]*)%",
            "severity": "medium",
            "impact_score": 0.6,
        },
    }

    SECURITY_PATTERNS = {
        "sql_injection_attempt": {
            "name": "SQL Injection Attempt",
            "regex": r"(?i)(union.*select|drop.*table|insert.*into|delete.*from|'.*or.*1.*=.*1)",
            "severity": "critical",
            "impact_score": 0.95,
        },
        "xss_attempt": {
            "name": "XSS Attack Attempt",
            "regex": r"(?i)(<script|javascript:|on\w+\s*=|eval\s*\()",
            "severity": "high",
            "impact_score": 0.8,
        },
        "failed_login_burst": {
            "name": "Failed Login Burst",
            "regex": r"(?i)(failed.*login|login.*failed|authentication.*failed)",
            "severity": "medium",
            "impact_score": 0.6,
        },
        "suspicious_user_agent": {
            "name": "Suspicious User Agent",
            "regex": r"(?i)(bot|crawl|scan|nikto|nmap|sqlmap|burp)",
            "severity": "low",
            "impact_score": 0.4,
        },
        "file_upload_suspicious": {
            "name": "Suspicious File Upload",
            "regex": r"(?i)upload.*(\.php|\.exe|\.bat|\.sh|\.py).*",
            "severity": "high",
            "impact_score": 0.8,
        },
    }

    BUSINESS_PATTERNS = {
        "document_upload": {
            "name": "Document Upload",
            "regex": r"(?i)(document.*upload|file.*upload|upload.*success)",
            "metric_type": "counter",
        },
        "rag_query": {
            "name": "RAG Query Execution",
            "regex": r"(?i)(rag.*query|query.*executed|semantic.*search)",
            "metric_type": "counter",
        },
        "user_registration": {
            "name": "User Registration",
            "regex": r"(?i)(user.*registered|registration.*success|account.*created)",
            "metric_type": "counter",
        },
        "pdf_processing": {
            "name": "PDF Processing",
            "regex": r"(?i)(pdf.*process|document.*index|vector.*index.*created)",
            "metric_type": "counter",
        },
    }


class LogParser:
    """Advanced log parser with multiple format support."""

    def __init__(self) -> None:
        # Common log format patterns
        self.format_patterns = {
            # Standard Python logging format
            "python_standard": re.compile(
                r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[,\.]\d{3})\s+"
                r"(?P<level>\w+)\s+"
                r"(?P<logger_name>[\w\.]+)\s*:\s*"
                r"(?P<message>.*)"
            ),
            # FastAPI/Uvicorn access log format
            "fastapi_access": re.compile(
                r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[,\.]\d{3})\s+"
                r"(?P<level>\w+)\s+"
                r"(?P<ip_address>[\d\.]+)\s*-\s*"
                r'"(?P<method>\w+)\s+(?P<endpoint>[^\s"]+)[^"]*"\s+'
                r"(?P<status_code>\d{3})\s+"
                r"(?P<response_time>[\d\.]+)"
            ),
            # JSON structured logs
            "json": re.compile(r"^{.*}$"),
            # Generic format
            "generic": re.compile(
                r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})"
                r".*?(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL|WARN|ERR)"
                r".*?(?P<message>.*)"
            ),
        }

    def parse_log_line(self, line: str) -> LogEntry | None:
        """Parse a single log line into structured data."""
        line = line.strip()
        if not line:
            return None

        try:
            # Try JSON format first
            if line.startswith("{"):
                return self._parse_json_log(line)

            # Try other formats
            for format_name, pattern in self.format_patterns.items():
                if format_name == "json":
                    continue

                match = pattern.match(line)
                if match:
                    return self._parse_structured_log(match, line, format_name)

            # Fallback: create minimal log entry
            return LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                logger_name="unknown",
                message=line,
                raw_line=line,
            )

        except Exception as e:
            logger.debug(f"Failed to parse log line: {line[:100]}... Error: {e}")
            return None

    def _parse_json_log(self, line: str) -> LogEntry:
        """Parse JSON formatted log entry."""
        try:
            data = json.loads(line)

            # Extract timestamp
            timestamp_str = (
                data.get("timestamp") or data.get("time") or data.get("@timestamp")
            )
            if timestamp_str:
                timestamp = self._parse_timestamp(timestamp_str)
            else:
                timestamp = datetime.now()

            # Extract level
            level_str = data.get("level") or data.get("severity") or "INFO"
            level = LogLevel(level_str.upper())

            return LogEntry(
                timestamp=timestamp,
                level=level,
                logger_name=data.get("logger", "unknown"),
                message=data.get("message", ""),
                module=data.get("module"),
                function=data.get("function"),
                line_number=data.get("lineno"),
                request_id=data.get("request_id"),
                user_id=data.get("user_id"),
                ip_address=data.get("ip") or data.get("remote_addr"),
                response_time=data.get("response_time"),
                status_code=data.get("status_code"),
                endpoint=data.get("endpoint") or data.get("path"),
                raw_line=line,
                additional_fields=data,
            )

        except json.JSONDecodeError:
            # Not valid JSON, treat as plain text
            return LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                logger_name="unknown",
                message=line,
                raw_line=line,
            )

    def _parse_structured_log(
        self, match: re.Match[str], line: str, format_name: str
    ) -> LogEntry:
        """Parse structured log entry from regex match."""
        groups = match.groupdict()

        # Parse timestamp
        timestamp = self._parse_timestamp(groups.get("timestamp"))

        # Parse level
        level_str = groups.get("level", "INFO").upper()
        # Handle common variations
        if level_str == "WARN":
            level_str = "WARNING"
        elif level_str == "ERR":
            level_str = "ERROR"
        level = LogLevel(level_str)

        # Extract additional fields based on format
        additional_fields = {}
        response_time = None
        status_code = None
        endpoint = None
        ip_address = None

        if format_name == "fastapi_access":
            response_time = float(groups.get("response_time", 0))
            status_code = int(groups.get("status_code", 0))
            endpoint = groups.get("endpoint")
            ip_address = groups.get("ip_address")
            additional_fields["method"] = groups.get("method")

        return LogEntry(
            timestamp=timestamp,
            level=level,
            logger_name=groups.get("logger_name", "unknown"),
            message=groups.get("message", ""),
            ip_address=ip_address,
            response_time=response_time,
            status_code=status_code,
            endpoint=endpoint,
            raw_line=line,
            additional_fields=additional_fields,
        )

    def _parse_timestamp(self, timestamp_str: str | None) -> datetime:
        """Parse timestamp string into datetime object."""
        if not timestamp_str:
            return datetime.now()

        # Common timestamp formats
        formats = [
            "%Y-%m-%d %H:%M:%S,%f",  # Python logging default
            "%Y-%m-%d %H:%M:%S.%f",  # Alternative microseconds
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with Z
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO format
            "%Y-%m-%d %H:%M:%S",  # No microseconds
            "%Y-%m-%dT%H:%M:%SZ",  # ISO format no microseconds
            "%Y-%m-%dT%H:%M:%S",  # ISO format basic
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        # Fallback to current time
        logger.debug(f"Could not parse timestamp: {timestamp_str}")
        return datetime.now()


# ============================================================================
# Log Analysis Engine
# ============================================================================


class LogAnalysisEngine:
    """Advanced log analysis engine with pattern recognition and predictive capabilities."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.parser = LogParser()
        self.pattern_library = LogPatternLibrary()
        self.cache_dir = cache_dir or Path("/tmp/log_analysis_cache")
        self.cache_dir.mkdir(exist_ok=True)

        # Analysis state
        self.log_entries: list[LogEntry] = []
        self.analysis_results: dict[str, Any] = {}

        # Pattern matching cache
        self.pattern_cache: dict[str, list[PatternMatch]] = {}

        # Performance tracking
        self.performance_metrics: Any = defaultdict(list[Any])
        self.response_time_history: Any = defaultdict(deque[Any])

        # Security event tracking
        self.security_events: Any = defaultdict(list[Any])
        self.ip_activity: Any = defaultdict(Counter)

        # Business metrics tracking
        self.business_metrics: Any = defaultdict(list[Any])

        logger.info(f"Log Analysis Engine initialized with cache dir: {self.cache_dir}")

    def analyze_logs(
        self,
        log_sources: list[Union[str, Path]],
        timeframe: str = "24h",
        analysis_types: list[AnalysisType] | None = None,
        output_format: str = "json",
    ) -> dict[str, Any]:
        """Main analysis entry point."""

        if analysis_types is None:
            analysis_types = list[Any](AnalysisType)

        logger.info(f"Starting log analysis for timeframe: {timeframe}")
        logger.info(f"Analysis types: {[t.value for t in analysis_types]}")

        # Parse log files
        self._load_logs(log_sources, timeframe)

        # Run analysis
        results = {}

        if AnalysisType.ERROR_PATTERNS in analysis_types:
            results["error_patterns"] = self._analyze_error_patterns()

        if AnalysisType.PERFORMANCE_BOTTLENECKS in analysis_types:
            results["performance_bottlenecks"] = self._analyze_performance_bottlenecks()

        if AnalysisType.SECURITY_EVENTS in analysis_types:
            results["security_events"] = self._analyze_security_events()

        if AnalysisType.BUSINESS_METRICS in analysis_types:
            results["business_metrics"] = self._extract_business_metrics()

        if AnalysisType.ANOMALY_DETECTION in analysis_types:
            results["anomalies"] = self._detect_anomalies()

        if AnalysisType.PREDICTIVE_ANALYSIS in analysis_types:
            results["predictions"] = self._generate_predictions()

        # Add metadata
        results["metadata"] = {
            "analysis_timestamp": datetime.now().isoformat(),
            "timeframe": timeframe,
            "total_log_entries": len(self.log_entries),
            "analysis_types": [t.value for t in analysis_types],
            "log_sources": [str(s) for s in log_sources],
        }

        self.analysis_results = results

        logger.info(
            f"Analysis completed. Processed {len(self.log_entries)} log entries"
        )

        return results

    def _load_logs(self, log_sources: list[Union[str, Path]], timeframe: str) -> None:
        """Load and parse log files within the specified timeframe."""

        # Calculate time window
        end_time = datetime.now()
        if timeframe.endswith("h"):
            hours = int(timeframe[:-1])
            start_time = end_time - timedelta(hours=hours)
        elif timeframe.endswith("d"):
            days = int(timeframe[:-1])
            start_time = end_time - timedelta(days=days)
        elif timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            start_time = end_time - timedelta(minutes=minutes)
        else:
            # Default to 24 hours
            start_time = end_time - timedelta(hours=24)

        logger.info(f"Loading logs from {start_time} to {end_time}")

        self.log_entries.clear()

        for log_source in log_sources:
            log_path = Path(log_source)

            if not log_path.exists():
                logger.warning(f"Log file not found: {log_path}")
                continue

            logger.info(f"Processing log file: {log_path}")

            try:
                with open(log_path, encoding="utf-8", errors="ignore") as f:
                    line_count = 0
                    parsed_count = 0

                    for line in f:
                        line_count += 1
                        log_entry = self.parser.parse_log_line(line)

                        if log_entry and start_time <= log_entry.timestamp <= end_time:
                            self.log_entries.append(log_entry)
                            parsed_count += 1

                    logger.info(
                        f"Processed {line_count} lines, parsed {parsed_count} entries from {log_path}"
                    )

            except Exception as e:
                logger.error(f"Error processing log file {log_path}: {e}")

        # Sort by timestamp
        self.log_entries.sort(key=lambda x: x.timestamp)
        logger.info(f"Total log entries loaded: {len(self.log_entries)}")

    def _analyze_error_patterns(self) -> list[PatternMatch]:
        """Analyze error patterns in the logs."""
        logger.info("Analyzing error patterns...")

        pattern_matches = []

        for pattern_id, pattern_config in self.pattern_library.ERROR_PATTERNS.items():
            regex = re.compile(pattern_config["regex"], re.IGNORECASE)
            matches = []

            for entry in self.log_entries:
                if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL, LogLevel.WARNING]:
                    if regex.search(entry.message) or (
                        entry.raw_line and regex.search(entry.raw_line)
                    ):
                        matches.append(entry)

            if matches:
                # Calculate confidence based on pattern specificity and match quality
                confidence = min(0.95, 0.5 + (len(matches) * 0.1))

                pattern_match = PatternMatch(
                    pattern_id=pattern_id,
                    pattern_name=pattern_config["name"],
                    pattern_regex=pattern_config["regex"],
                    matches=matches,
                    frequency=len(matches),
                    first_seen=min(m.timestamp for m in matches),
                    last_seen=max(m.timestamp for m in matches),
                    severity=pattern_config["severity"],
                    impact_score=pattern_config["impact_score"],
                    confidence=confidence,
                )

                pattern_matches.append(pattern_match)

        # Sort by impact score and frequency
        pattern_matches.sort(key=lambda x: (x.impact_score, x.frequency), reverse=True)

        logger.info(f"Found {len(pattern_matches)} error patterns")
        return pattern_matches

    def _analyze_performance_bottlenecks(self) -> list[PerformanceBottleneck]:
        """Analyze performance bottlenecks from log data."""
        logger.info("Analyzing performance bottlenecks...")

        # Group by endpoint
        endpoint_metrics: Any = defaultdict(list[Any])
        endpoint_errors: Any = defaultdict(int)
        endpoint_requests: Any = defaultdict(int)

        for entry in self.log_entries:
            if entry.endpoint:
                endpoint_requests[entry.endpoint] += 1

                if entry.response_time:
                    endpoint_metrics[entry.endpoint].append(entry.response_time)

                if entry.status_code and entry.status_code >= 500:
                    endpoint_errors[entry.endpoint] += 1

        bottlenecks = []

        for endpoint, response_times in endpoint_metrics.items():
            if len(response_times) < 5:  # Need minimum data
                continue

            avg_time = statistics.mean(response_times)
            max_time = max(response_times)
            min_time = min(response_times)
            percentile_95 = np.percentile(response_times, 95)

            request_count = endpoint_requests[endpoint]
            error_count = endpoint_errors[endpoint]
            error_rate = (error_count / request_count) * 100 if request_count > 0 else 0

            # Calculate trend (simple approach using recent vs older data)
            if len(response_times) >= 10:
                mid_point = len(response_times) // 2
                recent_avg = statistics.mean(response_times[mid_point:])
                older_avg = statistics.mean(response_times[:mid_point])

                if recent_avg > older_avg * 1.2:
                    trend = "increasing"
                elif recent_avg < older_avg * 0.8:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

            # Determine severity
            if avg_time > 5000 or percentile_95 > 10000:  # 5s avg or 10s p95
                severity = "critical"
            elif avg_time > 2000 or percentile_95 > 5000:  # 2s avg or 5s p95
                severity = "high"
            elif avg_time > 1000 or percentile_95 > 2000:  # 1s avg or 2s p95
                severity = "medium"
            else:
                severity = "low"

            # Generate recommendations
            recommendations = []
            if avg_time > 2000:
                recommendations.append("Optimize endpoint performance")
            if error_rate > 5:
                recommendations.append("Investigate error causes")
            if trend == "increasing":
                recommendations.append("Monitor for performance regression")
            if percentile_95 > avg_time * 3:
                recommendations.append("Check for performance outliers")

            bottleneck = PerformanceBottleneck(
                endpoint=endpoint,
                avg_response_time=avg_time,
                max_response_time=max_time,
                min_response_time=min_time,
                percentile_95=percentile_95,
                request_count=request_count,
                error_rate=error_rate,
                trend=trend,
                severity=severity,
                recommendations=recommendations,
            )

            bottlenecks.append(bottleneck)

        # Sort by severity and response time
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        bottlenecks.sort(
            key=lambda x: (severity_order.get(x.severity, 999), -x.avg_response_time)
        )

        logger.info(f"Found {len(bottlenecks)} performance bottlenecks")
        return bottlenecks

    def _analyze_security_events(self) -> list[SecurityEvent]:
        """Analyze security events and potential threats."""
        logger.info("Analyzing security events...")

        security_events = []

        # Track events by IP and pattern
        ip_events: Any = defaultdict(lambda: defaultdict(list[Any]))

        for (
            pattern_id,
            pattern_config,
        ) in self.pattern_library.SECURITY_PATTERNS.items():
            regex = re.compile(pattern_config["regex"], re.IGNORECASE)

            for entry in self.log_entries:
                message_text = entry.message + (entry.raw_line or "")

                if regex.search(message_text):
                    ip = entry.ip_address or "unknown"
                    endpoint = entry.endpoint or "unknown"

                    ip_events[ip][pattern_id].append(
                        {
                            "timestamp": entry.timestamp,
                            "endpoint": endpoint,
                            "entry": entry,
                        }
                    )

        # Analyze events by IP and pattern
        for ip, ip_patterns in ip_events.items():
            for pattern_id, events in ip_patterns.items():
                if not events:
                    continue

                pattern_config = self.pattern_library.SECURITY_PATTERNS[pattern_id]

                # Determine risk level based on frequency and pattern type
                frequency = len(events)

                if frequency > 50 or pattern_config["severity"] == "critical":
                    risk_level = "high"
                elif frequency > 10 or pattern_config["severity"] == "high":
                    risk_level = "medium"
                else:
                    risk_level = "low"

                # Generate countermeasures
                countermeasures = []
                if pattern_id in ["sql_injection_attempt", "xss_attempt"]:
                    countermeasures.extend(
                        [
                            "Block IP address",
                            "Review input validation",
                            "Enable WAF protection",
                        ]
                    )
                elif pattern_id == "failed_login_burst":
                    countermeasures.extend(
                        [
                            "Implement account lockout",
                            "Enable rate limiting",
                            "Monitor for credential stuffing",
                        ]
                    )
                elif pattern_id == "suspicious_user_agent":
                    countermeasures.extend(
                        [
                            "Block bot traffic",
                            "Implement CAPTCHA",
                            "Monitor for automated attacks",
                        ]
                    )

                # Determine attack pattern
                attack_pattern = None
                if frequency > 20 and len(set[str](e["endpoint"] for e in events)) > 5:
                    attack_pattern = "reconnaissance_scan"
                elif frequency > 50:
                    attack_pattern = "brute_force_attack"
                elif pattern_id == "sql_injection_attempt":
                    attack_pattern = "sql_injection_attack"

                security_event = SecurityEvent(
                    event_type=pattern_config["name"],
                    source_ip=ip,
                    target_endpoint=max(
                        set[str](e["endpoint"] for e in events),
                        key=lambda x: sum(1 for e in events if e["endpoint"] == x),
                    ),
                    frequency=frequency,
                    first_seen=min(e["timestamp"] for e in events),
                    last_seen=max(e["timestamp"] for e in events),
                    risk_level=risk_level,
                    attack_pattern=attack_pattern,
                    countermeasures=countermeasures,
                )

                security_events.append(security_event)

        # Sort by risk level and frequency
        risk_order = {"high": 0, "medium": 1, "low": 2}
        security_events.sort(
            key=lambda x: (risk_order.get(x.risk_level, 999), -x.frequency)
        )

        logger.info(f"Found {len(security_events)} security events")
        return security_events

    def _extract_business_metrics(self) -> list[BusinessMetric]:
        """Extract business metrics from log data."""
        logger.info("Extracting business metrics...")

        metrics = []

        # Track business events
        business_events = defaultdict(int)

        for (
            pattern_id,
            pattern_config,
        ) in self.pattern_library.BUSINESS_PATTERNS.items():
            regex = re.compile(pattern_config["regex"], re.IGNORECASE)
            count = 0

            for entry in self.log_entries:
                if regex.search(entry.message) or (
                    entry.raw_line and regex.search(entry.raw_line)
                ):
                    count += 1

            if count > 0:
                business_events[pattern_id] = count

        # Convert to business metrics
        for pattern_id, count in business_events.items():
            pattern_config = self.pattern_library.BUSINESS_PATTERNS[pattern_id]

            metric = BusinessMetric(
                metric_name=pattern_config["name"],
                metric_value=count,
                metric_type=pattern_config["metric_type"],
                time_period="analysis_window",
            )

            metrics.append(metric)

        # Calculate additional derived metrics
        if (
            business_events.get("document_upload", 0) > 0
            and business_events.get("rag_query", 0) > 0
        ):
            engagement_ratio = (
                business_events["rag_query"] / business_events["document_upload"]
            )

            metrics.append(
                BusinessMetric(
                    metric_name="Query to Upload Ratio",
                    metric_value=round(engagement_ratio, 2),
                    metric_type="ratio",
                    time_period="analysis_window",
                )
            )

        logger.info(f"Extracted {len(metrics)} business metrics")
        return metrics

    def _detect_anomalies(self) -> list[Anomaly]:
        """Detect anomalies in log patterns and system behavior."""
        logger.info("Detecting anomalies...")

        anomalies = []

        # 1. Response time anomalies
        response_times = [
            entry.response_time for entry in self.log_entries if entry.response_time
        ]

        if len(response_times) > 50:
            mean_response_time = statistics.mean(response_times)
            std_response_time = statistics.stdev(response_times)
            threshold = mean_response_time + (3 * std_response_time)  # 3 sigma rule

            outliers = [rt for rt in response_times if rt > threshold]

            if len(outliers) > len(response_times) * 0.05:  # More than 5% outliers
                anomaly = Anomaly(
                    anomaly_type="response_time_spike",
                    description=f"Unusual spike in response times detected. {len(outliers)} requests exceeded {threshold:.2f}ms",
                    severity=(
                        "medium"
                        if len(outliers) < len(response_times) * 0.1
                        else "high"
                    ),
                    confidence=0.8,
                    affected_components=["api_endpoints"],
                    time_window=(
                        min(
                            entry.timestamp
                            for entry in self.log_entries
                            if entry.response_time and entry.response_time > threshold
                        ),
                        max(
                            entry.timestamp
                            for entry in self.log_entries
                            if entry.response_time and entry.response_time > threshold
                        ),
                    ),
                    baseline_value=mean_response_time,
                    anomalous_value=max(outliers),
                    deviation_score=(max(outliers) - mean_response_time)
                    / std_response_time,
                )
                anomalies.append(anomaly)

        # 2. Error rate anomalies
        time_buckets: Any = defaultdict(lambda: {"total": 0, "errors": 0})

        for entry in self.log_entries:
            bucket_key = entry.timestamp.replace(minute=0, second=0, microsecond=0)
            time_buckets[bucket_key]["total"] += 1

            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                time_buckets[bucket_key]["errors"] += 1

        error_rates = []
        for bucket_data in time_buckets.values():
            if bucket_data["total"] > 0:
                error_rate = (bucket_data["errors"] / bucket_data["total"]) * 100
                error_rates.append(error_rate)

        if len(error_rates) > 5:
            mean_error_rate = statistics.mean(error_rates)
            std_error_rate = (
                statistics.stdev(error_rates) if len(error_rates) > 1 else 0
            )

            if std_error_rate > 0:
                threshold = mean_error_rate + (2 * std_error_rate)
                high_error_periods = [rate for rate in error_rates if rate > threshold]

                if high_error_periods and max(high_error_periods) > mean_error_rate * 2:
                    anomaly = Anomaly(
                        anomaly_type="error_rate_spike",
                        description=f"Error rate spike detected. Peak error rate: {max(high_error_periods):.2f}%",
                        severity="high" if max(high_error_periods) > 10 else "medium",
                        confidence=0.75,
                        affected_components=["application"],
                        time_window=(
                            datetime.now() - timedelta(hours=len(error_rates)),
                            datetime.now(),
                        ),
                        baseline_value=mean_error_rate,
                        anomalous_value=max(high_error_periods),
                        deviation_score=(max(high_error_periods) - mean_error_rate)
                        / max(std_error_rate, 0.1),
                    )
                    anomalies.append(anomaly)

        # 3. Traffic volume anomalies
        hourly_traffic: Any = defaultdict(int)
        for entry in self.log_entries:
            hour_key = entry.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_traffic[hour_key] += 1

        if len(hourly_traffic) > 5:
            traffic_volumes = list[Any](hourly_traffic.values())
            mean_traffic = statistics.mean(traffic_volumes)
            std_traffic = (
                statistics.stdev(traffic_volumes) if len(traffic_volumes) > 1 else 0
            )

            if std_traffic > mean_traffic * 0.5:  # High variability
                max_traffic = max(traffic_volumes)
                if max_traffic > mean_traffic + (3 * std_traffic):
                    anomaly = Anomaly(
                        anomaly_type="traffic_spike",
                        description=f"Unusual traffic spike detected. Peak: {max_traffic} requests/hour",
                        severity="medium",
                        confidence=0.7,
                        affected_components=["infrastructure"],
                        time_window=(
                            min(hourly_traffic.keys()),
                            max(hourly_traffic.keys()),
                        ),
                        baseline_value=mean_traffic,
                        anomalous_value=max_traffic,
                        deviation_score=(max_traffic - mean_traffic)
                        / max(std_traffic, 1),
                    )
                    anomalies.append(anomaly)

        logger.info(f"Detected {len(anomalies)} anomalies")
        return anomalies

    def _generate_predictions(self) -> list[PredictiveInsight]:
        """Generate predictive insights based on log analysis."""
        logger.info("Generating predictive insights...")

        predictions = []

        # 1. Error trend prediction
        error_counts: Any = defaultdict(int)
        for entry in self.log_entries:
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                hour_key = entry.timestamp.replace(minute=0, second=0, microsecond=0)
                error_counts[hour_key] += 1

        if len(error_counts) >= 6:  # Need at least 6 hours of data
            recent_hours = sorted(error_counts.keys())[-6:]
            recent_errors = [error_counts[hour] for hour in recent_hours]

            # Simple linear trend
            if len(recent_errors) > 3:
                x = list[Any](range(len(recent_errors)))
                slope = sum(
                    (x[i] - statistics.mean(x))
                    * (recent_errors[i] - statistics.mean(recent_errors))
                    for i in range(len(x))
                ) / sum((x[i] - statistics.mean(x)) ** 2 for i in range(len(x)))

                if slope > 0.5:  # Increasing trend
                    prediction = PredictiveInsight(
                        prediction_type="error_trend",
                        prediction="Error rates are trending upward. System stability may degrade if current trend continues.",
                        confidence=0.7,
                        time_horizon="next_6_hours",
                        supporting_data={
                            "recent_error_counts": recent_errors,
                            "trend_slope": slope,
                            "analysis_period": "6_hours",
                        },
                        recommended_actions=[
                            "Monitor error logs closely",
                            "Prepare incident response procedures",
                            "Consider scaling resources",
                            "Review recent deployments",
                        ],
                        risk_level="medium" if slope < 1.0 else "high",
                    )
                    predictions.append(prediction)

        # 2. Performance degradation prediction
        response_times = []
        for entry in self.log_entries:
            if entry.response_time and entry.response_time > 0:
                response_times.append((entry.timestamp, entry.response_time))

        if len(response_times) > 50:
            # Group by hour and calculate averages
            hourly_performance: Any = defaultdict(list[Any])
            for timestamp, response_time in response_times:
                hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
                hourly_performance[hour_key].append(response_time)

            # Calculate hourly averages
            hourly_averages = []
            for hour in sorted(hourly_performance.keys()):
                avg_response_time = statistics.mean(hourly_performance[hour])
                hourly_averages.append(avg_response_time)

            if len(hourly_averages) >= 4:
                recent_performance = hourly_averages[-4:]  # Last 4 hours

                # Check for degradation trend
                if len(recent_performance) > 2:
                    improvement = (
                        recent_performance[0] - recent_performance[-1]
                    ) / recent_performance[0]

                    if improvement < -0.2:  # 20% degradation
                        prediction = PredictiveInsight(
                            prediction_type="performance_degradation",
                            prediction="Performance is degrading. Response times may continue to increase without intervention.",
                            confidence=0.65,
                            time_horizon="next_4_hours",
                            supporting_data={
                                "recent_avg_response_times": recent_performance,
                                "degradation_percentage": abs(improvement * 100),
                                "analysis_period": "4_hours",
                            },
                            recommended_actions=[
                                "Investigate performance bottlenecks",
                                "Check system resource usage",
                                "Review database query performance",
                                "Consider horizontal scaling",
                            ],
                            risk_level="medium" if abs(improvement) < 0.5 else "high",
                        )
                        predictions.append(prediction)

        # 3. Security threat escalation prediction
        security_events_by_hour: Any = defaultdict(int)
        unique_ips_by_hour: Any = defaultdict(set[str])

        for entry in self.log_entries:
            # Check for security-related log patterns
            for pattern_config in self.pattern_library.SECURITY_PATTERNS.values():
                regex = re.compile(pattern_config["regex"], re.IGNORECASE)
                if regex.search(entry.message) or (
                    entry.raw_line and regex.search(entry.raw_line)
                ):
                    hour_key = entry.timestamp.replace(
                        minute=0, second=0, microsecond=0
                    )
                    security_events_by_hour[hour_key] += 1
                    if entry.ip_address:
                        unique_ips_by_hour[hour_key].add(entry.ip_address)
                    break

        if len(security_events_by_hour) > 0:
            recent_security_activity = list[Any](security_events_by_hour.values())[
                -6:
            ]  # Last 6 hours

            if len(recent_security_activity) > 3 and sum(recent_security_activity) > 20:
                total_recent_events = sum(recent_security_activity)
                unique_ips_count = (
                    len(set[str].union(*unique_ips_by_hour.values()))
                    if unique_ips_by_hour
                    else 0
                )

                prediction = PredictiveInsight(
                    prediction_type="security_threat_escalation",
                    prediction=f"Elevated security activity detected. {total_recent_events} suspicious events from {unique_ips_count} unique IPs. Monitor for potential coordinated attack.",
                    confidence=0.6,
                    time_horizon="next_2_hours",
                    supporting_data={
                        "recent_security_events": recent_security_activity,
                        "unique_source_ips": unique_ips_count,
                        "total_events": total_recent_events,
                    },
                    recommended_actions=[
                        "Enable additional security monitoring",
                        "Review firewall rules",
                        "Consider implementing rate limiting",
                        "Prepare incident response plan",
                    ],
                    risk_level="high" if total_recent_events > 50 else "medium",
                )
                predictions.append(prediction)

        logger.info(f"Generated {len(predictions)} predictive insights")
        return predictions


# ============================================================================
# Output Formatters
# ============================================================================


class OutputFormatter:
    """Format analysis results for different output formats."""

    @staticmethod
    def format_results(results: dict[str, Any], format_type: str = "json") -> str:
        """Format analysis results."""

        if format_type.lower() == "json":
            return OutputFormatter._format_json(results)
        elif format_type.lower() == "markdown":
            return OutputFormatter._format_markdown(results)
        elif format_type.lower() == "html":
            return OutputFormatter._format_html(results)
        else:
            return json.dumps(results, indent=2, default=str)

    @staticmethod
    def _format_json(results: dict[str, Any]) -> str:
        """Format as JSON."""

        def json_serializer(obj: Any) -> Any:
            if isinstance(obj, (datetime, LogLevel, AnalysisType)):
                return str(obj)
            elif hasattr(obj, "__dict__"):
                return asdict(obj)
            return str(obj)

        return json.dumps(results, indent=2, default=json_serializer)

    @staticmethod
    def _format_markdown(results: dict[str, Any]) -> str:
        """Format as Markdown report."""
        md_content = []

        # Header
        md_content.append("# Log Analysis Report")
        md_content.append(
            f"**Generated:** {results.get('metadata', {}).get('analysis_timestamp', 'Unknown')}"
        )
        md_content.append(
            f"**Timeframe:** {results.get('metadata', {}).get('timeframe', 'Unknown')}"
        )
        md_content.append(
            f"**Total Entries:** {results.get('metadata', {}).get('total_log_entries', 0)}"
        )
        md_content.append("")

        # Error Patterns
        if "error_patterns" in results:
            md_content.append("## Error Patterns")
            error_patterns = results["error_patterns"]

            if error_patterns:
                for pattern in error_patterns[:5]:  # Top 5
                    md_content.append(f"### {pattern['pattern_name']}")
                    md_content.append(f"- **Frequency:** {pattern['frequency']}")
                    md_content.append(f"- **Severity:** {pattern['severity']}")
                    md_content.append(f"- **Impact Score:** {pattern['impact_score']}")
                    md_content.append(f"- **First Seen:** {pattern['first_seen']}")
                    md_content.append(f"- **Last Seen:** {pattern['last_seen']}")
                    md_content.append("")
            else:
                md_content.append("No significant error patterns detected.")

            md_content.append("")

        # Performance Bottlenecks
        if "performance_bottlenecks" in results:
            md_content.append("## Performance Bottlenecks")
            bottlenecks = results["performance_bottlenecks"]

            if bottlenecks:
                for bottleneck in bottlenecks[:5]:  # Top 5
                    md_content.append(f"### {bottleneck['endpoint']}")
                    md_content.append(
                        f"- **Average Response Time:** {bottleneck['avg_response_time']:.2f}ms"
                    )
                    md_content.append(
                        f"- **95th Percentile:** {bottleneck['percentile_95']:.2f}ms"
                    )
                    md_content.append(
                        f"- **Request Count:** {bottleneck['request_count']}"
                    )
                    md_content.append(
                        f"- **Error Rate:** {bottleneck['error_rate']:.2f}%"
                    )
                    md_content.append(f"- **Trend:** {bottleneck['trend']}")
                    md_content.append(f"- **Severity:** {bottleneck['severity']}")
                    if bottleneck.get("recommendations"):
                        md_content.append("- **Recommendations:**")
                        for rec in bottleneck["recommendations"]:
                            md_content.append(f"  - {rec}")
                    md_content.append("")
            else:
                md_content.append("No significant performance bottlenecks detected.")

            md_content.append("")

        # Security Events
        if "security_events" in results:
            md_content.append("## Security Events")
            security_events = results["security_events"]

            if security_events:
                for event in security_events[:5]:  # Top 5
                    md_content.append(f"### {event['event_type']}")
                    md_content.append(f"- **Source IP:** {event['source_ip']}")
                    md_content.append(f"- **Frequency:** {event['frequency']}")
                    md_content.append(f"- **Risk Level:** {event['risk_level']}")
                    md_content.append(f"- **First Seen:** {event['first_seen']}")
                    md_content.append(f"- **Last Seen:** {event['last_seen']}")
                    if event.get("countermeasures"):
                        md_content.append("- **Recommended Countermeasures:**")
                        for measure in event["countermeasures"]:
                            md_content.append(f"  - {measure}")
                    md_content.append("")
            else:
                md_content.append("No significant security events detected.")

            md_content.append("")

        # Business Metrics
        if "business_metrics" in results:
            md_content.append("## Business Metrics")
            business_metrics = results["business_metrics"]

            if business_metrics:
                for metric in business_metrics:
                    md_content.append(
                        f"- **{metric['metric_name']}:** {metric['metric_value']} ({metric['metric_type']})"
                    )
                md_content.append("")
            else:
                md_content.append("No business metrics extracted.")

            md_content.append("")

        # Anomalies
        if "anomalies" in results:
            md_content.append("## Anomalies Detected")
            anomalies = results["anomalies"]

            if anomalies:
                for anomaly in anomalies:
                    md_content.append(f"### {anomaly['anomaly_type'].title()}")
                    md_content.append(f"- **Description:** {anomaly['description']}")
                    md_content.append(f"- **Severity:** {anomaly['severity']}")
                    md_content.append(f"- **Confidence:** {anomaly['confidence']:.2f}")
                    md_content.append("")
            else:
                md_content.append("No anomalies detected.")

            md_content.append("")

        # Predictions
        if "predictions" in results:
            md_content.append("## Predictive Insights")
            predictions = results["predictions"]

            if predictions:
                for prediction in predictions:
                    md_content.append(f"### {prediction['prediction_type'].title()}")
                    md_content.append(f"- **Prediction:** {prediction['prediction']}")
                    md_content.append(
                        f"- **Confidence:** {prediction['confidence']:.2f}"
                    )
                    md_content.append(
                        f"- **Time Horizon:** {prediction['time_horizon']}"
                    )
                    md_content.append(f"- **Risk Level:** {prediction['risk_level']}")
                    if prediction.get("recommended_actions"):
                        md_content.append("- **Recommended Actions:**")
                        for action in prediction["recommended_actions"]:
                            md_content.append(f"  - {action}")
                    md_content.append("")
            else:
                md_content.append("No predictive insights generated.")

        return "\n".join(md_content)

    @staticmethod
    def _format_html(results: dict[str, Any]) -> str:
        """Format as HTML report."""
        html_content = []

        # HTML header
        html_content.append(
            """
<!DOCTYPE html>
<html>
<head>
    <title>Log Analysis Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; }
        .metric { background: #f9f9f9; padding: 10px; margin: 5px 0; border-left: 4px solid #007cba; }
        .critical { border-left-color: #dc3545; }
        .high { border-left-color: #fd7e14; }
        .medium { border-left-color: #ffc107; }
        .low { border-left-color: #28a745; }
        .recommendations { background: #e7f3ff; padding: 10px; border-radius: 3px; }
    </style>
</head>
<body>
"""
        )

        # Header section
        metadata = results.get("metadata", {})
        html_content.append(
            f"""
<div class="header">
    <h1>Log Analysis Report</h1>
    <p><strong>Generated:</strong> {metadata.get('analysis_timestamp', 'Unknown')}</p>
    <p><strong>Timeframe:</strong> {metadata.get('timeframe', 'Unknown')}</p>
    <p><strong>Total Entries:</strong> {metadata.get('total_log_entries', 0)}</p>
</div>
"""
        )

        # Add sections for each analysis type
        sections = [
            ("error_patterns", "Error Patterns", "severity"),
            ("performance_bottlenecks", "Performance Bottlenecks", "severity"),
            ("security_events", "Security Events", "risk_level"),
            ("anomalies", "Anomalies", "severity"),
            ("predictions", "Predictive Insights", "risk_level"),
        ]

        for key, title, severity_key in sections:
            if key in results:
                html_content.append(f'<div class="section"><h2>{title}</h2>')

                items = results[key]
                if items:
                    for item in items[:10]:  # Top 10 items
                        severity = item.get(severity_key, "low")
                        html_content.append(f'<div class="metric {severity}">')

                        if key == "error_patterns":
                            html_content.append(f'<h3>{item["pattern_name"]}</h3>')
                            html_content.append(
                                f'<p><strong>Frequency:</strong> {item["frequency"]}</p>'
                            )
                            html_content.append(
                                f'<p><strong>Impact Score:</strong> {item["impact_score"]}</p>'
                            )
                        elif key == "performance_bottlenecks":
                            html_content.append(f'<h3>{item["endpoint"]}</h3>')
                            html_content.append(
                                f'<p><strong>Average Response Time:</strong> {item["avg_response_time"]:.2f}ms</p>'
                            )
                            html_content.append(
                                f'<p><strong>Error Rate:</strong> {item["error_rate"]:.2f}%</p>'
                            )
                        elif key == "security_events":
                            html_content.append(f'<h3>{item["event_type"]}</h3>')
                            html_content.append(
                                f'<p><strong>Source IP:</strong> {item["source_ip"]}</p>'
                            )
                            html_content.append(
                                f'<p><strong>Frequency:</strong> {item["frequency"]}</p>'
                            )
                        elif key == "anomalies":
                            html_content.append(
                                f'<h3>{item["anomaly_type"].title()}</h3>'
                            )
                            html_content.append(f'<p>{item["description"]}</p>')
                            html_content.append(
                                f'<p><strong>Confidence:</strong> {item["confidence"]:.2f}</p>'
                            )
                        elif key == "predictions":
                            html_content.append(
                                f'<h3>{item["prediction_type"].title()}</h3>'
                            )
                            html_content.append(f'<p>{item["prediction"]}</p>')
                            html_content.append(
                                f'<p><strong>Confidence:</strong> {item["confidence"]:.2f}</p>'
                            )

                        html_content.append("</div>")
                else:
                    html_content.append(f"<p>No {title.lower()} detected.</p>")

                html_content.append("</div>")

        # HTML footer
        html_content.append(
            """
</body>
</html>
"""
        )

        return "".join(html_content)


# ============================================================================
# Main CLI Interface
# ============================================================================


def main() -> Any:
    """Main CLI interface for the log analysis system."""
    parser = argparse.ArgumentParser(
        description="Advanced Log Analysis System for AI Enhanced PDF Scholar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze last 24 hours of logs
  python log_analyzer.py /var/log/ai_pdf_scholar.log --timeframe 24h

  # Analyze specific types only
  python log_analyzer.py /var/log/*.log --analysis error_patterns,security_events

  # Generate HTML report
  python log_analyzer.py /var/log/*.log --format html --output report.html

  # Focus on performance issues
  python log_analyzer.py /var/log/*.log --analysis performance_bottlenecks --timeframe 6h
        """,
    )

    # Input arguments
    parser.add_argument("log_files", nargs="+", help="Log files or patterns to analyze")

    parser.add_argument(
        "--timeframe",
        default="24h",
        help="Time window for analysis (e.g., 24h, 7d, 60m). Default: 24h",
    )

    parser.add_argument(
        "--analysis",
        help="Comma-separated list[Any] of analysis types: error_patterns, performance_bottlenecks, security_events, business_metrics, anomaly_detection, predictive_analysis",
    )

    parser.add_argument(
        "--format",
        choices=["json", "markdown", "html"],
        default="json",
        help="Output format. Default: json",
    )

    parser.add_argument(
        "--output", help="Output file path. If not specified, prints to stdout"
    )

    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Cache directory for analysis data. Default: /tmp/log_analysis_cache",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse analysis types
    analysis_types = None
    if args.analysis:
        type_names = [t.strip() for t in args.analysis.split(",")]
        analysis_types = []
        for type_name in type_names:
            try:
                analysis_types.append(AnalysisType(type_name))
            except ValueError:
                logger.error(f"Unknown analysis type: {type_name}")
                return 1

    # Initialize analysis engine
    try:
        engine = LogAnalysisEngine(cache_dir=args.cache_dir)

        logger.info(f"Starting analysis of {len(args.log_files)} log sources")

        # Run analysis
        results = engine.analyze_logs(
            log_sources=args.log_files,
            timeframe=args.timeframe,
            analysis_types=analysis_types,
            output_format=args.format,
        )

        # Format output
        formatted_output = OutputFormatter.format_results(results, args.format)

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(formatted_output)

            logger.info(f"Analysis report saved to: {output_path}")
        else:
            print(formatted_output)

        return 0

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
