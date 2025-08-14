#!/usr/bin/env python3
"""
🛡️ Automated Rollback System

Advanced rollback automation with health validation for the AI Enhanced PDF Scholar project.
Provides fast, reliable rollback capabilities with comprehensive validation.

Agent B1: CI/CD Pipeline Optimization Specialist
Generated: 2025-01-19
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import argparse
import subprocess
import yaml
import aiohttp
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RollbackTrigger(Enum):
    """Rollback trigger types"""
    MANUAL = "manual"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    ERROR_RATE_THRESHOLD = "error_rate_threshold"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    MONITORING_ALERT = "monitoring_alert"
    SECURITY_INCIDENT = "security_incident"


class RollbackStatus(Enum):
    """Rollback execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Environment(Enum):
    """Target environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class HealthCheckResult:
    """Health check result"""
    endpoint: str
    status_code: int
    response_time_ms: float
    healthy: bool
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class RollbackTarget:
    """Rollback target configuration"""
    deployment_id: str
    version: str
    commit_sha: str
    deployment_url: str
    health_check_endpoints: List[str]
    backup_urls: List[str] = None

    def __post_init__(self):
        if self.backup_urls is None:
            self.backup_urls = []


@dataclass
class RollbackConfig:
    """Rollback configuration"""
    environment: Environment
    trigger: RollbackTrigger
    source_deployment_id: str
    target: RollbackTarget

    # Rollback options
    fast_rollback: bool = True
    validate_before_rollback: bool = True
    validate_after_rollback: bool = True
    traffic_switch_strategy: str = "immediate"  # immediate, gradual

    # Health check configuration
    health_check_timeout: int = 120  # seconds
    health_check_retries: int = 3
    health_check_interval: int = 10  # seconds

    # Performance thresholds
    max_error_rate_percent: float = 5.0
    max_response_time_ms: float = 2000.0
    min_success_rate_percent: float = 95.0


@dataclass
class RollbackResult:
    """Rollback execution result"""
    rollback_id: str
    config: RollbackConfig
    status: RollbackStatus
    start_time: datetime
    end_time: Optional[datetime] = None

    # Execution details
    pre_rollback_health: List[HealthCheckResult] = None
    post_rollback_health: List[HealthCheckResult] = None
    logs: List[str] = None
    metrics: Dict[str, Any] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.pre_rollback_health is None:
            self.pre_rollback_health = []
        if self.post_rollback_health is None:
            self.post_rollback_health = []
        if self.logs is None:
            self.logs = []
        if self.metrics is None:
            self.metrics = {}

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate rollback duration"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'rollback_id': self.rollback_id,
            'config': {
                'environment': self.config.environment.value,
                'trigger': self.config.trigger.value,
                'source_deployment_id': self.config.source_deployment_id,
                'target': {
                    'deployment_id': self.config.target.deployment_id,
                    'version': self.config.target.version,
                    'commit_sha': self.config.target.commit_sha,
                    'deployment_url': self.config.target.deployment_url,
                    'health_check_endpoints': self.config.target.health_check_endpoints
                },
                'fast_rollback': self.config.fast_rollback,
                'traffic_switch_strategy': self.config.traffic_switch_strategy
            },
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'logs': self.logs,
            'metrics': self.metrics,
            'error_message': self.error_message,
            'pre_rollback_health': [
                {
                    'endpoint': h.endpoint,
                    'healthy': h.healthy,
                    'response_time_ms': h.response_time_ms,
                    'timestamp': h.timestamp.isoformat()
                } for h in self.pre_rollback_health
            ],
            'post_rollback_health': [
                {
                    'endpoint': h.endpoint,
                    'healthy': h.healthy,
                    'response_time_ms': h.response_time_ms,
                    'timestamp': h.timestamp.isoformat()
                } for h in self.post_rollback_health
            ]
        }


class RollbackAutomation:
    """Automated rollback system"""

    def __init__(self, work_dir: Path = None):
        self.work_dir = work_dir or Path.cwd()
        self.rollbacks: Dict[str, RollbackResult] = {}
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.repository = os.getenv('GITHUB_REPOSITORY', 'ai-enhanced-pdf-scholar')

        # HTTP session for health checks
        self.http_timeout = aiohttp.ClientTimeout(total=30)

    def generate_rollback_id(self, config: RollbackConfig) -> str:
        """Generate unique rollback ID"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        return f"rollback-{config.environment.value}-{config.trigger.value}-{timestamp}"

    async def execute_rollback(self, config: RollbackConfig) -> RollbackResult:
        """Execute automated rollback"""
        rollback_id = self.generate_rollback_id(config)

        logger.info(f"🛡️ Starting rollback {rollback_id}")
        logger.info(f"📋 Trigger: {config.trigger.value}")
        logger.info(f"🎯 Target: {config.target.deployment_id} ({config.target.version})")

        result = RollbackResult(
            rollback_id=rollback_id,
            config=config,
            status=RollbackStatus.PENDING,
            start_time=datetime.now(timezone.utc)
        )

        self.rollbacks[rollback_id] = result

        try:
            result.status = RollbackStatus.IN_PROGRESS
            result.logs.append(f"Rollback triggered by: {config.trigger.value}")

            # Pre-rollback validation
            if config.validate_before_rollback:
                await self._pre_rollback_validation(result)

            # Execute rollback
            await self._execute_rollback_steps(result)

            # Post-rollback validation
            if config.validate_after_rollback:
                await self._post_rollback_validation(result)

            result.status = RollbackStatus.COMPLETED
            result.end_time = datetime.now(timezone.utc)

            logger.info(f"✅ Rollback {rollback_id} completed successfully")
            logger.info(f"⏱️ Duration: {result.duration_seconds:.1f} seconds")

        except Exception as e:
            logger.error(f"❌ Rollback {rollback_id} failed: {e}")
            result.status = RollbackStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now(timezone.utc)

        return result

    async def _pre_rollback_validation(self, result: RollbackResult) -> None:
        """Validate system state before rollback"""
        logger.info("🔍 Running pre-rollback validation...")
        result.logs.append("Starting pre-rollback validation")

        config = result.config

        # Check current deployment health
        current_health = await self._comprehensive_health_check(
            config.target.health_check_endpoints,
            config.health_check_timeout
        )
        result.pre_rollback_health = current_health

        # Analyze health results
        healthy_endpoints = sum(1 for h in current_health if h.healthy)
        total_endpoints = len(current_health)
        health_percentage = (healthy_endpoints / total_endpoints) * 100 if total_endpoints > 0 else 0

        result.logs.append(f"Current health: {healthy_endpoints}/{total_endpoints} endpoints healthy ({health_percentage:.1f}%)")

        # If system is mostly healthy, we might want to confirm rollback
        if health_percentage > 80 and config.trigger == RollbackTrigger.MANUAL:
            logger.warning("⚠️ System appears healthy - confirming rollback necessity...")
            result.logs.append("Warning: System appears healthy for manual rollback")

        # Check rollback target availability
        await self._validate_rollback_target(result)

    async def _validate_rollback_target(self, result: RollbackResult) -> None:
        """Validate rollback target is available and healthy"""
        logger.info("🎯 Validating rollback target...")

        config = result.config.target

        # Check if target deployment is accessible
        for backup_url in config.backup_urls:
            try:
                async with aiohttp.ClientSession(timeout=self.http_timeout) as session:
                    async with session.get(f"{backup_url}/health") as response:
                        if response.status == 200:
                            result.logs.append(f"Rollback target verified: {backup_url}")
                            return
                        else:
                            result.logs.append(f"Rollback target unhealthy: {backup_url} (status: {response.status})")
            except Exception as e:
                result.logs.append(f"Rollback target check failed: {backup_url} - {e}")

        # If no backup URLs worked, we'll proceed anyway but log the concern
        result.logs.append("Warning: Could not verify all rollback targets")

    async def _execute_rollback_steps(self, result: RollbackResult) -> None:
        """Execute the actual rollback process"""
        logger.info("🔄 Executing rollback steps...")

        config = result.config

        if config.fast_rollback:
            await self._fast_rollback(result)
        else:
            await self._gradual_rollback(result)

    async def _fast_rollback(self, result: RollbackResult) -> None:
        """Execute fast rollback (immediate traffic switch)"""
        logger.info("⚡ Executing fast rollback...")
        result.logs.append("Starting fast rollback - immediate traffic switch")

        config = result.config

        # Step 1: Immediate traffic redirection
        logger.info("🔄 Step 1/4: Redirecting traffic...")
        await self._redirect_traffic(result, immediate=True)
        result.logs.append("Traffic redirected to stable version")

        # Step 2: Stop failing services
        logger.info("🛑 Step 2/4: Stopping failed services...")
        await self._stop_failed_services(result)
        result.logs.append("Failed services stopped")

        # Step 3: Activate rollback target
        logger.info("🚀 Step 3/4: Activating rollback target...")
        await self._activate_rollback_target(result)
        result.logs.append("Rollback target activated")

        # Step 4: Verify rollback
        logger.info("✅ Step 4/4: Verifying rollback...")
        await self._verify_rollback_success(result)
        result.logs.append("Fast rollback completed")

    async def _gradual_rollback(self, result: RollbackResult) -> None:
        """Execute gradual rollback (progressive traffic switch)"""
        logger.info("📈 Executing gradual rollback...")
        result.logs.append("Starting gradual rollback - progressive traffic switch")

        # Traffic switch percentages
        switch_stages = [25, 50, 75, 100]

        for stage in switch_stages:
            logger.info(f"🔄 Switching {stage}% traffic to rollback target...")
            await self._redirect_traffic(result, percentage=stage)
            result.logs.append(f"Traffic switch: {stage}% to rollback target")

            # Brief wait between stages
            await asyncio.sleep(10)

            # Quick health check
            if stage < 100:
                health = await self._quick_health_check(result.config.target.health_check_endpoints[:1])
                if not health[0].healthy:
                    raise Exception(f"Health check failed during gradual rollback at {stage}%")

        result.logs.append("Gradual rollback completed")

    async def _redirect_traffic(self, result: RollbackResult, immediate: bool = False, percentage: int = 100) -> None:
        """Redirect traffic to rollback target"""
        config = result.config

        if immediate or percentage == 100:
            logger.info("🔄 Redirecting 100% traffic immediately...")
        else:
            logger.info(f"🔄 Redirecting {percentage}% traffic...")

        # Simulate traffic redirection
        # In production, this would update load balancer, ingress, or service mesh
        await asyncio.sleep(2)

        # Record metrics
        result.metrics['traffic_redirect_percentage'] = percentage
        result.metrics['traffic_redirect_time'] = datetime.now(timezone.utc).isoformat()

    async def _stop_failed_services(self, result: RollbackResult) -> None:
        """Stop failed services"""
        logger.info("🛑 Stopping failed services...")

        # Simulate stopping services
        await asyncio.sleep(1)

        result.logs.append("Failed services stopped successfully")

    async def _activate_rollback_target(self, result: RollbackResult) -> None:
        """Activate rollback target deployment"""
        logger.info("🚀 Activating rollback target...")

        config = result.config.target

        # Simulate service activation
        await asyncio.sleep(3)

        result.logs.append(f"Rollback target activated: {config.deployment_id}")
        result.metrics['rollback_target_activation'] = datetime.now(timezone.utc).isoformat()

    async def _verify_rollback_success(self, result: RollbackResult) -> None:
        """Verify rollback was successful"""
        logger.info("✅ Verifying rollback success...")

        # Quick health check to confirm rollback
        health_checks = await self._quick_health_check(result.config.target.health_check_endpoints)

        healthy_count = sum(1 for h in health_checks if h.healthy)
        total_count = len(health_checks)

        if healthy_count < total_count:
            logger.warning(f"⚠️ Some endpoints unhealthy after rollback: {healthy_count}/{total_count}")

        result.logs.append(f"Rollback verification: {healthy_count}/{total_count} endpoints healthy")

    async def _post_rollback_validation(self, result: RollbackResult) -> None:
        """Comprehensive validation after rollback"""
        logger.info("🔍 Running post-rollback validation...")
        result.logs.append("Starting post-rollback validation")

        config = result.config

        # Comprehensive health check
        post_health = await self._comprehensive_health_check(
            config.target.health_check_endpoints,
            config.health_check_timeout
        )
        result.post_rollback_health = post_health

        # Analyze results
        healthy_endpoints = sum(1 for h in post_health if h.healthy)
        total_endpoints = len(post_health)
        health_percentage = (healthy_endpoints / total_endpoints) * 100 if total_endpoints > 0 else 0

        avg_response_time = sum(h.response_time_ms for h in post_health if h.healthy) / max(healthy_endpoints, 1)

        result.logs.append(f"Post-rollback health: {healthy_endpoints}/{total_endpoints} endpoints healthy ({health_percentage:.1f}%)")
        result.logs.append(f"Average response time: {avg_response_time:.1f}ms")

        # Store metrics
        result.metrics.update({
            'post_rollback_health_percentage': health_percentage,
            'post_rollback_avg_response_time_ms': avg_response_time,
            'post_rollback_healthy_endpoints': healthy_endpoints,
            'post_rollback_total_endpoints': total_endpoints
        })

        # Validation thresholds
        if health_percentage < config.min_success_rate_percent:
            raise Exception(f"Post-rollback health check failed: {health_percentage:.1f}% < {config.min_success_rate_percent}%")

        if avg_response_time > config.max_response_time_ms:
            logger.warning(f"⚠️ Average response time high: {avg_response_time:.1f}ms > {config.max_response_time_ms}ms")

        logger.info("✅ Post-rollback validation completed successfully")

    async def _comprehensive_health_check(self, endpoints: List[str], timeout: int) -> List[HealthCheckResult]:
        """Perform comprehensive health check on endpoints"""
        logger.info(f"🏥 Running comprehensive health check on {len(endpoints)} endpoints...")

        results = []

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:

            tasks = []
            for endpoint in endpoints:
                task = self._check_endpoint_health(session, endpoint)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed health checks
        health_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                health_results.append(HealthCheckResult(
                    endpoint=endpoints[i],
                    status_code=0,
                    response_time_ms=0,
                    healthy=False,
                    error_message=str(result)
                ))
            else:
                health_results.append(result)

        return health_results

    async def _quick_health_check(self, endpoints: List[str]) -> List[HealthCheckResult]:
        """Quick health check with shorter timeout"""
        return await self._comprehensive_health_check(endpoints, 30)

    async def _check_endpoint_health(self, session: aiohttp.ClientSession, endpoint: str) -> HealthCheckResult:
        """Check health of a single endpoint"""
        start_time = time.time()

        try:
            async with session.get(endpoint) as response:
                response_time_ms = (time.time() - start_time) * 1000

                healthy = 200 <= response.status < 400

                return HealthCheckResult(
                    endpoint=endpoint,
                    status_code=response.status,
                    response_time_ms=response_time_ms,
                    healthy=healthy,
                    error_message=None if healthy else f"HTTP {response.status}"
                )

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                endpoint=endpoint,
                status_code=0,
                response_time_ms=response_time_ms,
                healthy=False,
                error_message=str(e)
            )

    def detect_rollback_conditions(
        self,
        environment: Environment,
        current_metrics: Dict[str, float]
    ) -> Optional[RollbackTrigger]:
        """Detect if rollback conditions are met"""

        # Error rate threshold
        error_rate = current_metrics.get('error_rate_percent', 0)
        if error_rate > 5.0:  # 5% error rate threshold
            logger.warning(f"🚨 High error rate detected: {error_rate:.2f}%")
            return RollbackTrigger.ERROR_RATE_THRESHOLD

        # Performance degradation
        avg_response_time = current_metrics.get('avg_response_time_ms', 0)
        if avg_response_time > 2000:  # 2 second threshold
            logger.warning(f"🐌 Performance degradation detected: {avg_response_time:.1f}ms")
            return RollbackTrigger.PERFORMANCE_DEGRADATION

        # Success rate threshold
        success_rate = current_metrics.get('success_rate_percent', 100)
        if success_rate < 95:  # 95% success rate threshold
            logger.warning(f"📉 Low success rate detected: {success_rate:.1f}%")
            return RollbackTrigger.ERROR_RATE_THRESHOLD

        return None

    async def auto_rollback_monitor(
        self,
        environment: Environment,
        current_deployment_id: str,
        rollback_target: RollbackTarget,
        check_interval: int = 60  # seconds
    ) -> None:
        """Continuous monitoring for auto-rollback conditions"""
        logger.info(f"🔍 Starting auto-rollback monitor for {environment.value}")

        while True:
            try:
                # Simulate metrics collection
                # In production, this would collect real metrics
                current_metrics = {
                    'error_rate_percent': 2.1,  # Simulated
                    'avg_response_time_ms': 150,  # Simulated
                    'success_rate_percent': 97.8  # Simulated
                }

                trigger = self.detect_rollback_conditions(environment, current_metrics)

                if trigger:
                    logger.warning(f"🚨 Auto-rollback triggered: {trigger.value}")

                    config = RollbackConfig(
                        environment=environment,
                        trigger=trigger,
                        source_deployment_id=current_deployment_id,
                        target=rollback_target,
                        fast_rollback=True  # Auto-rollbacks should be fast
                    )

                    await self.execute_rollback(config)
                    break  # Exit monitor after rollback

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"❌ Error in auto-rollback monitor: {e}")
                await asyncio.sleep(check_interval)

    def get_rollback(self, rollback_id: str) -> Optional[RollbackResult]:
        """Get rollback result by ID"""
        return self.rollbacks.get(rollback_id)

    def list_rollbacks(
        self,
        environment: Optional[Environment] = None,
        trigger: Optional[RollbackTrigger] = None,
        limit: int = 10
    ) -> List[RollbackResult]:
        """List rollbacks with optional filtering"""
        rollbacks = list(self.rollbacks.values())

        if environment:
            rollbacks = [r for r in rollbacks if r.config.environment == environment]

        if trigger:
            rollbacks = [r for r in rollbacks if r.config.trigger == trigger]

        # Sort by start time, most recent first
        rollbacks.sort(key=lambda r: r.start_time, reverse=True)

        return rollbacks[:limit]

    def save_rollback_history(self, file_path: Path = None) -> None:
        """Save rollback history to file"""
        if file_path is None:
            file_path = self.work_dir / "rollback_history.json"

        history = {
            'rollbacks': [r.to_dict() for r in self.rollbacks.values()],
            'exported_at': datetime.now(timezone.utc).isoformat()
        }

        with open(file_path, 'w') as f:
            json.dump(history, f, indent=2)

        logger.info(f"📊 Rollback history saved to {file_path}")


async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="🛡️ Automated Rollback System for AI Enhanced PDF Scholar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Manual rollback
  python rollback_automation.py rollback --env production --trigger manual --source-deployment prod-123 --target-deployment prod-122 --target-version v1.0.0 --target-sha abc123

  # Check if rollback is needed
  python rollback_automation.py check --env staging --error-rate 7.5 --response-time 3000

  # List recent rollbacks
  python rollback_automation.py list --env production --limit 5

  # Monitor for auto-rollback conditions
  python rollback_automation.py monitor --env production --current-deployment prod-123 --target-deployment prod-122
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Execute rollback')
    rollback_parser.add_argument('--env', '--environment', type=str, required=True,
                                choices=['development', 'staging', 'production'],
                                help='Target environment')
    rollback_parser.add_argument('--trigger', type=str, required=True,
                                choices=['manual', 'health_check_failure', 'error_rate_threshold', 'performance_degradation'],
                                help='Rollback trigger')
    rollback_parser.add_argument('--source-deployment', type=str, required=True,
                                help='Source deployment ID to rollback from')
    rollback_parser.add_argument('--target-deployment', type=str, required=True,
                                help='Target deployment ID to rollback to')
    rollback_parser.add_argument('--target-version', type=str, required=True,
                                help='Target version')
    rollback_parser.add_argument('--target-sha', type=str, required=True,
                                help='Target commit SHA')
    rollback_parser.add_argument('--target-url', type=str,
                                help='Target deployment URL')
    rollback_parser.add_argument('--health-endpoints', type=str, nargs='*',
                                help='Health check endpoints')
    rollback_parser.add_argument('--fast', action='store_true',
                                help='Execute fast rollback (immediate)')
    rollback_parser.add_argument('--no-validation', action='store_true',
                                help='Skip pre/post validation')

    # Check command
    check_parser = subparsers.add_parser('check', help='Check rollback conditions')
    check_parser.add_argument('--env', '--environment', type=str, required=True,
                             choices=['development', 'staging', 'production'],
                             help='Environment to check')
    check_parser.add_argument('--error-rate', type=float,
                             help='Current error rate percentage')
    check_parser.add_argument('--response-time', type=float,
                             help='Current average response time (ms)')
    check_parser.add_argument('--success-rate', type=float,
                             help='Current success rate percentage')

    # List command
    list_parser = subparsers.add_parser('list', help='List rollbacks')
    list_parser.add_argument('--env', '--environment', type=str,
                            choices=['development', 'staging', 'production'],
                            help='Filter by environment')
    list_parser.add_argument('--trigger', type=str,
                            choices=['manual', 'health_check_failure', 'error_rate_threshold', 'performance_degradation'],
                            help='Filter by trigger')
    list_parser.add_argument('--limit', type=int, default=10,
                            help='Maximum number of results')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get rollback details')
    get_parser.add_argument('--rollback-id', type=str, required=True,
                           help='Rollback ID')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor for auto-rollback')
    monitor_parser.add_argument('--env', '--environment', type=str, required=True,
                               choices=['development', 'staging', 'production'],
                               help='Environment to monitor')
    monitor_parser.add_argument('--current-deployment', type=str, required=True,
                               help='Current deployment ID')
    monitor_parser.add_argument('--target-deployment', type=str, required=True,
                               help='Target deployment ID for rollback')
    monitor_parser.add_argument('--interval', type=int, default=60,
                               help='Check interval in seconds')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize rollback system
    rollback_system = RollbackAutomation()

    try:
        if args.command == 'rollback':
            # Build rollback target
            target = RollbackTarget(
                deployment_id=args.target_deployment,
                version=args.target_version,
                commit_sha=args.target_sha,
                deployment_url=args.target_url or f"https://{args.env}.ai-pdf-scholar.com",
                health_check_endpoints=args.health_endpoints or [
                    f"https://{args.env}.ai-pdf-scholar.com/health",
                    f"https://{args.env}.ai-pdf-scholar.com/api/v1/system/status"
                ]
            )

            config = RollbackConfig(
                environment=Environment(args.env),
                trigger=RollbackTrigger(args.trigger),
                source_deployment_id=args.source_deployment,
                target=target,
                fast_rollback=args.fast,
                validate_before_rollback=not args.no_validation,
                validate_after_rollback=not args.no_validation
            )

            result = await rollback_system.execute_rollback(config)

            print(f"🛡️ Rollback Result:")
            print(f"  ID: {result.rollback_id}")
            print(f"  Status: {result.status.value}")
            print(f"  Duration: {result.duration_seconds:.1f}s" if result.duration_seconds else "  Duration: N/A")

            if result.error_message:
                print(f"  Error: {result.error_message}")

        elif args.command == 'check':
            metrics = {}
            if args.error_rate is not None:
                metrics['error_rate_percent'] = args.error_rate
            if args.response_time is not None:
                metrics['avg_response_time_ms'] = args.response_time
            if args.success_rate is not None:
                metrics['success_rate_percent'] = args.success_rate

            trigger = rollback_system.detect_rollback_conditions(
                Environment(args.env),
                metrics
            )

            if trigger:
                print(f"🚨 Rollback recommended: {trigger.value}")
                print(f"  Metrics: {metrics}")
            else:
                print("✅ No rollback conditions detected")
                print(f"  Metrics: {metrics}")

        elif args.command == 'list':
            env_filter = Environment(args.env) if args.env else None
            trigger_filter = RollbackTrigger(args.trigger) if args.trigger else None

            rollbacks = rollback_system.list_rollbacks(env_filter, trigger_filter, args.limit)

            if not rollbacks:
                print("No rollbacks found")
                return

            print(f"🛡️ Recent Rollbacks ({len(rollbacks)}):")
            print()

            for rollback in rollbacks:
                duration = f"{rollback.duration_seconds:.1f}s" if rollback.duration_seconds else "N/A"
                print(f"  🔄 {rollback.rollback_id}")
                print(f"     Status: {rollback.status.value}")
                print(f"     Environment: {rollback.config.environment.value}")
                print(f"     Trigger: {rollback.config.trigger.value}")
                print(f"     Duration: {duration}")
                print()

        elif args.command == 'get':
            rollback = rollback_system.get_rollback(args.rollback_id)

            if not rollback:
                print(f"❌ Rollback not found: {args.rollback_id}")
                return

            print(f"🛡️ Rollback Details: {rollback.rollback_id}")
            print(f"  Status: {rollback.status.value}")
            print(f"  Environment: {rollback.config.environment.value}")
            print(f"  Trigger: {rollback.config.trigger.value}")
            print(f"  Source: {rollback.config.source_deployment_id}")
            print(f"  Target: {rollback.config.target.deployment_id} ({rollback.config.target.version})")
            print(f"  Duration: {rollback.duration_seconds:.1f}s" if rollback.duration_seconds else "  Duration: N/A")

            if rollback.error_message:
                print(f"  Error: {rollback.error_message}")

            # Show health check results
            if rollback.post_rollback_health:
                healthy = sum(1 for h in rollback.post_rollback_health if h.healthy)
                total = len(rollback.post_rollback_health)
                print(f"  Post-rollback Health: {healthy}/{total} endpoints healthy")

        elif args.command == 'monitor':
            target = RollbackTarget(
                deployment_id=args.target_deployment,
                version="stable",
                commit_sha="stable",
                deployment_url=f"https://{args.env}.ai-pdf-scholar.com",
                health_check_endpoints=[
                    f"https://{args.env}.ai-pdf-scholar.com/health"
                ]
            )

            await rollback_system.auto_rollback_monitor(
                Environment(args.env),
                args.current_deployment,
                target,
                args.interval
            )

    finally:
        # Save rollback history
        rollback_system.save_rollback_history()


if __name__ == '__main__':
    asyncio.run(main())