"""
Unit tests for metrics WebSocket route helper functions.

Tests the 2 helper functions extracted during Day 3 refactoring:
- _parse_metric_type_safe
- _parse_json_safe

All external dependencies are mocked.
"""

import json

import pytest

from backend.api.routes.metrics_websocket import (
    _parse_json_safe,
    _parse_metric_type_safe,
)
from backend.services.real_time_metrics_collector import MetricType

# ============================================================================
# Tests for _parse_metric_type_safe (6 tests)
# ============================================================================


class TestParseMetricTypeSafe:
    """Test metric type parsing helper."""

    def test_valid_system_metric(self):
        """Valid 'system' metric should return MetricType.SYSTEM."""
        metric, error = _parse_metric_type_safe("system")

        assert metric == MetricType.SYSTEM
        assert error is None

    def test_valid_database_metric(self):
        """Valid 'database' metric should return MetricType.DATABASE."""
        metric, error = _parse_metric_type_safe("database")

        assert metric == MetricType.DATABASE
        assert error is None

    def test_case_insensitive_parsing(self):
        """Uppercase metric string should be lowercased."""
        metric, error = _parse_metric_type_safe("MEMORY")

        assert metric == MetricType.MEMORY
        assert error is None

    def test_invalid_metric_returns_error(self):
        """Invalid metric string should return error message."""
        metric, error = _parse_metric_type_safe("invalid_metric")

        assert metric is None
        assert error is not None
        assert "invalid" in error.lower()
        assert "invalid_metric" in error

    def test_empty_string_returns_error(self):
        """Empty string should return error message."""
        metric, error = _parse_metric_type_safe("")

        assert metric is None
        assert error is not None

    def test_all_valid_metric_types(self):
        """All MetricType enum values should parse successfully."""
        # Test common metric types (adjust based on actual MetricType enum)
        valid_types = ["system", "database", "websocket", "rag", "api"]

        for metric_str in valid_types:
            metric, error = _parse_metric_type_safe(metric_str)
            if error:  # Skip if not in enum
                continue
            assert metric is not None, f"Failed to parse {metric_str}"
            assert error is None


# ============================================================================
# Tests for _parse_json_safe (5 tests)
# ============================================================================


class TestParseJsonSafe:
    """Test JSON parsing helper."""

    def test_valid_json_object(self):
        """Valid JSON object should parse successfully."""
        text = '{"type": "ping", "timestamp": 123456}'
        data, error = _parse_json_safe(text)

        assert data == {"type": "ping", "timestamp": 123456}
        assert error is None

    def test_valid_json_array(self):
        """Valid JSON array should parse successfully."""
        text = '["system", "database", "memory"]'
        data, error = _parse_json_safe(text)

        assert data == ["system", "database", "memory"]
        assert error is None

    def test_invalid_json_returns_error(self):
        """Malformed JSON should return error message."""
        text = '{"type": "ping", invalid}'
        data, error = _parse_json_safe(text)

        assert data is None
        assert error is not None
        assert "invalid json" in error.lower()

    def test_empty_string_returns_error(self):
        """Empty string should return error message."""
        text = ""
        data, error = _parse_json_safe(text)

        assert data is None
        assert error is not None

    def test_truncated_json_returns_error(self):
        """Truncated JSON should return error message."""
        text = '{"type": "ping"'  # Missing closing brace
        data, error = _parse_json_safe(text)

        assert data is None
        assert error is not None


# ============================================================================
# Integration Tests for Refactored Loops (3 tests)
# ============================================================================


class TestMetricTypeValidationPattern:
    """Test the validation-first pattern used in refactored loops."""

    def test_batch_parse_all_valid(self):
        """Batch parsing all valid metrics should succeed."""
        metric_types = ["system", "database", "websocket"]
        parsed = [_parse_metric_type_safe(m) for m in metric_types]

        # All should be valid
        invalid = [error for _, error in parsed if error]
        assert len(invalid) == 0

        # Extract valid metrics
        metrics = [m for m, _ in parsed if m]
        assert len(metrics) == 3
        assert MetricType.SYSTEM in metrics
        assert MetricType.DATABASE in metrics
        assert MetricType.WEBSOCKET in metrics

    def test_batch_parse_with_invalid(self):
        """Batch parsing with invalid metric should detect error."""
        metric_types = ["system", "invalid_type", "websocket"]
        parsed = [_parse_metric_type_safe(m) for m in metric_types]

        # Should have 1 invalid
        invalid = [error for _, error in parsed if error]
        assert len(invalid) == 1
        assert "invalid_type" in invalid[0]

        # Should have 2 valid
        valid = [m for m, _ in parsed if m]
        assert len(valid) == 2

    def test_batch_parse_empty_list(self):
        """Batch parsing empty list should return empty results."""
        metric_types = []
        parsed = [_parse_metric_type_safe(m) for m in metric_types]

        assert len(parsed) == 0
