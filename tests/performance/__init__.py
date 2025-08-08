"""
Performance Testing Suite for AI Enhanced PDF Scholar

This module provides comprehensive performance testing capabilities including:
- Concurrent user simulation
- Load testing scenarios
- Performance benchmarking
- Resource monitoring
- Scalability validation
"""

from .base_performance import (
    PerformanceTestBase,
    PerformanceMetrics,
    LoadTestScenario,
    ConcurrentUserSimulator
)

from .metrics_collector import (
    MetricsCollector,
    PerformanceReport,
    PerformanceThresholds
)

__all__ = [
    'PerformanceTestBase',
    'PerformanceMetrics',
    'LoadTestScenario',
    'ConcurrentUserSimulator',
    'MetricsCollector',
    'PerformanceReport',
    'PerformanceThresholds'
]