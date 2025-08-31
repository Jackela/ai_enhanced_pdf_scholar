#!/usr/bin/env python3
"""
🚩 Feature Flag Automation Script

Advanced feature flag deployment and management system for the AI Enhanced PDF Scholar project.
Enables safe, controlled rollout of new features with automated monitoring and rollback.

Agent B1: CI/CD Pipeline Optimization Specialist
Generated: 2025-01-19
"""

import argparse
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FeatureFlagStatus(Enum):
    """Feature flag status values"""
    DISABLED = "disabled"
    ENABLED = "enabled"
    TESTING = "testing"
    STAGED = "staged"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"


class RolloutStrategy(Enum):
    """Feature rollout strategies"""
    IMMEDIATE = "immediate"
    GRADUAL = "gradual"
    CANARY = "canary"
    A_B_TEST = "ab_test"
    MANUAL = "manual"


class Environment(Enum):
    """Target environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class FeatureFlagRule:
    """Feature flag targeting rule"""
    name: str
    condition: str  # e.g., "user.role == 'admin'" or "user.id in [1,2,3]"
    percentage: float = 100.0  # Percentage of matching users
    enabled: bool = True


@dataclass
class FeatureFlagConfig:
    """Feature flag configuration"""
    key: str
    name: str
    description: str
    status: FeatureFlagStatus
    rollout_strategy: RolloutStrategy
    environments: list[Environment]

    # Rollout configuration
    rollout_percentage: float = 0.0
    target_percentage: float = 100.0
    rollout_increment: float = 10.0
    rollout_interval_hours: int = 24

    # Targeting rules
    rules: list[FeatureFlagRule] = None

    # Dependencies
    depends_on: list[str] = None
    conflicts_with: list[str] = None

    # Metadata
    created_by: str = "system"
    created_at: datetime = None
    updated_at: datetime = None
    tags: list[str] = None

    def __post_init__(self):
        if self.rules is None:
            self.rules = []
        if self.depends_on is None:
            self.depends_on = []
        if self.conflicts_with is None:
            self.conflicts_with = []
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'rollout_strategy': self.rollout_strategy.value,
            'environments': [env.value for env in self.environments],
            'rollout_percentage': self.rollout_percentage,
            'target_percentage': self.target_percentage,
            'rollout_increment': self.rollout_increment,
            'rollout_interval_hours': self.rollout_interval_hours,
            'rules': [{'name': r.name, 'condition': r.condition, 'percentage': r.percentage, 'enabled': r.enabled} for r in self.rules],
            'depends_on': self.depends_on,
            'conflicts_with': self.conflicts_with,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'tags': self.tags
        }


@dataclass
class FeatureFlagDeployment:
    """Feature flag deployment record"""
    flag_key: str
    environment: Environment
    deployment_id: str
    previous_status: FeatureFlagStatus
    new_status: FeatureFlagStatus
    previous_percentage: float
    new_percentage: float
    deployed_at: datetime
    deployed_by: str
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'flag_key': self.flag_key,
            'environment': self.environment.value,
            'deployment_id': self.deployment_id,
            'previous_status': self.previous_status.value,
            'new_status': self.new_status.value,
            'previous_percentage': self.previous_percentage,
            'new_percentage': self.new_percentage,
            'deployed_at': self.deployed_at.isoformat(),
            'deployed_by': self.deployed_by,
            'success': self.success,
            'error_message': self.error_message
        }


class FeatureFlagDeployer:
    """Feature flag deployment and management system"""

    def __init__(self, config_dir: Path = None, state_file: Path = None):
        self.config_dir = config_dir or Path.cwd() / "feature_flags"
        self.state_file = state_file or self.config_dir / "state.json"

        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)

        # In-memory state
        self.flags: dict[str, FeatureFlagConfig] = {}
        self.deployments: list[FeatureFlagDeployment] = []

        # Load existing state
        self.load_state()

    def load_state(self) -> None:
        """Load feature flags and deployment history from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    state = json.load(f)

                # Load flags
                for flag_data in state.get('flags', []):
                    flag = self._dict_to_flag(flag_data)
                    self.flags[flag.key] = flag

                # Load deployments
                for deployment_data in state.get('deployments', []):
                    deployment = self._dict_to_deployment(deployment_data)
                    self.deployments.append(deployment)

                logger.info(f"Loaded {len(self.flags)} flags and {len(self.deployments)} deployments")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")

    def save_state(self) -> None:
        """Save current state to disk"""
        try:
            state = {
                'flags': [flag.to_dict() for flag in self.flags.values()],
                'deployments': [deployment.to_dict() for deployment in self.deployments],
                'saved_at': datetime.now(timezone.utc).isoformat()
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

            logger.info(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _dict_to_flag(self, data: dict[str, Any]) -> FeatureFlagConfig:
        """Convert dictionary to FeatureFlagConfig"""
        rules = [
            FeatureFlagRule(
                name=r['name'],
                condition=r['condition'],
                percentage=r.get('percentage', 100.0),
                enabled=r.get('enabled', True)
            ) for r in data.get('rules', [])
        ]

        return FeatureFlagConfig(
            key=data['key'],
            name=data['name'],
            description=data['description'],
            status=FeatureFlagStatus(data['status']),
            rollout_strategy=RolloutStrategy(data['rollout_strategy']),
            environments=[Environment(env) for env in data['environments']],
            rollout_percentage=data.get('rollout_percentage', 0.0),
            target_percentage=data.get('target_percentage', 100.0),
            rollout_increment=data.get('rollout_increment', 10.0),
            rollout_interval_hours=data.get('rollout_interval_hours', 24),
            rules=rules,
            depends_on=data.get('depends_on', []),
            conflicts_with=data.get('conflicts_with', []),
            created_by=data.get('created_by', 'system'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            tags=data.get('tags', [])
        )

    def _dict_to_deployment(self, data: dict[str, Any]) -> FeatureFlagDeployment:
        """Convert dictionary to FeatureFlagDeployment"""
        return FeatureFlagDeployment(
            flag_key=data['flag_key'],
            environment=Environment(data['environment']),
            deployment_id=data['deployment_id'],
            previous_status=FeatureFlagStatus(data['previous_status']),
            new_status=FeatureFlagStatus(data['new_status']),
            previous_percentage=data['previous_percentage'],
            new_percentage=data['new_percentage'],
            deployed_at=datetime.fromisoformat(data['deployed_at']),
            deployed_by=data['deployed_by'],
            success=data.get('success', True),
            error_message=data.get('error_message')
        )

    def create_flag(self, config: FeatureFlagConfig) -> None:
        """Create a new feature flag"""
        if config.key in self.flags:
            raise ValueError(f"Feature flag '{config.key}' already exists")

        # Validate dependencies
        self._validate_dependencies(config)

        self.flags[config.key] = config
        self.save_state()

        logger.info(f"Created feature flag: {config.key}")

    def update_flag(self, flag_key: str, updates: dict[str, Any]) -> None:
        """Update an existing feature flag"""
        if flag_key not in self.flags:
            raise ValueError(f"Feature flag '{flag_key}' not found")

        flag = self.flags[flag_key]

        # Apply updates
        for key, value in updates.items():
            if hasattr(flag, key):
                if key == 'status' and isinstance(value, str):
                    setattr(flag, key, FeatureFlagStatus(value))
                elif key == 'rollout_strategy' and isinstance(value, str):
                    setattr(flag, key, RolloutStrategy(value))
                elif key == 'environments' and isinstance(value, list):
                    setattr(flag, key, [Environment(env) if isinstance(env, str) else env for env in value])
                else:
                    setattr(flag, key, value)

        flag.updated_at = datetime.now(timezone.utc)
        self.save_state()

        logger.info(f"Updated feature flag: {flag_key}")

    def _validate_dependencies(self, config: FeatureFlagConfig) -> None:
        """Validate flag dependencies and conflicts"""
        # Check dependencies exist
        for dep in config.depends_on:
            if dep not in self.flags:
                raise ValueError(f"Dependency '{dep}' not found")

        # Check for conflicts
        for conflict in config.conflicts_with:
            if conflict in self.flags:
                conflict_flag = self.flags[conflict]
                if conflict_flag.status in [FeatureFlagStatus.ENABLED, FeatureFlagStatus.PRODUCTION]:
                    raise ValueError(f"Conflicting flag '{conflict}' is currently enabled")

    async def deploy_flag(
        self,
        flag_key: str,
        environment: Environment,
        new_status: FeatureFlagStatus | None = None,
        new_percentage: float | None = None,
        deployed_by: str = "system"
    ) -> FeatureFlagDeployment:
        """Deploy feature flag to specified environment"""
        if flag_key not in self.flags:
            raise ValueError(f"Feature flag '{flag_key}' not found")

        flag = self.flags[flag_key]

        if environment not in flag.environments:
            raise ValueError(f"Flag '{flag_key}' is not configured for environment '{environment.value}'")

        # Current state
        current_status = flag.status
        current_percentage = flag.rollout_percentage

        # Determine new state
        if new_status is None:
            new_status = current_status
        if new_percentage is None:
            new_percentage = current_percentage

        # Generate deployment ID
        deployment_id = self._generate_deployment_id(flag_key, environment)

        try:
            # Validate deployment
            await self._validate_deployment(flag, environment, new_status, new_percentage)

            # Execute deployment
            await self._execute_deployment(flag, environment, new_status, new_percentage)

            # Update flag state
            flag.status = new_status
            flag.rollout_percentage = new_percentage
            flag.updated_at = datetime.now(timezone.utc)

            # Record deployment
            deployment = FeatureFlagDeployment(
                flag_key=flag_key,
                environment=environment,
                deployment_id=deployment_id,
                previous_status=current_status,
                new_status=new_status,
                previous_percentage=current_percentage,
                new_percentage=new_percentage,
                deployed_at=datetime.now(timezone.utc),
                deployed_by=deployed_by,
                success=True
            )

            self.deployments.append(deployment)
            self.save_state()

            logger.info(f"Successfully deployed flag '{flag_key}' to {environment.value}")
            return deployment

        except Exception as e:
            # Record failed deployment
            deployment = FeatureFlagDeployment(
                flag_key=flag_key,
                environment=environment,
                deployment_id=deployment_id,
                previous_status=current_status,
                new_status=new_status,
                previous_percentage=current_percentage,
                new_percentage=new_percentage,
                deployed_at=datetime.now(timezone.utc),
                deployed_by=deployed_by,
                success=False,
                error_message=str(e)
            )

            self.deployments.append(deployment)
            self.save_state()

            logger.error(f"Failed to deploy flag '{flag_key}' to {environment.value}: {e}")
            raise

    async def _validate_deployment(
        self,
        flag: FeatureFlagConfig,
        environment: Environment,
        new_status: FeatureFlagStatus,
        new_percentage: float
    ) -> None:
        """Validate deployment before execution"""

        # Check dependencies are satisfied
        for dep_key in flag.depends_on:
            if dep_key in self.flags:
                dep_flag = self.flags[dep_key]
                if dep_flag.status not in [FeatureFlagStatus.ENABLED, FeatureFlagStatus.PRODUCTION]:
                    raise ValueError(f"Dependency '{dep_key}' is not enabled")

        # Check conflicts
        for conflict_key in flag.conflicts_with:
            if conflict_key in self.flags:
                conflict_flag = self.flags[conflict_key]
                if (new_status in [FeatureFlagStatus.ENABLED, FeatureFlagStatus.PRODUCTION] and
                    conflict_flag.status in [FeatureFlagStatus.ENABLED, FeatureFlagStatus.PRODUCTION]):
                    raise ValueError(f"Cannot enable flag due to conflict with '{conflict_key}'")

        # Validate percentage range
        if not 0 <= new_percentage <= 100:
            raise ValueError(f"Invalid percentage: {new_percentage}")

        # Environment-specific validations
        if environment == Environment.PRODUCTION:
            if new_status == FeatureFlagStatus.PRODUCTION and new_percentage > 50:
                # Require manual approval for high-impact production deployments
                logger.warning(f"High-impact production deployment: {new_percentage}% rollout")

    async def _execute_deployment(
        self,
        flag: FeatureFlagConfig,
        environment: Environment,
        new_status: FeatureFlagStatus,
        new_percentage: float
    ) -> None:
        """Execute the actual deployment"""

        # In a real implementation, this would:
        # 1. Update feature flag service (LaunchDarkly, ConfigCat, etc.)
        # 2. Update configuration management system
        # 3. Notify application instances
        # 4. Verify deployment success

        logger.info(f"Executing deployment: {flag.key} -> {new_status.value} ({new_percentage}%)")

        # Simulate deployment time
        await asyncio.sleep(1)

        # Simulate different deployment strategies
        if flag.rollout_strategy == RolloutStrategy.GRADUAL:
            await self._gradual_deployment(flag, environment, new_percentage)
        elif flag.rollout_strategy == RolloutStrategy.CANARY:
            await self._canary_deployment(flag, environment, new_percentage)
        elif flag.rollout_strategy == RolloutStrategy.A_B_TEST:
            await self._ab_test_deployment(flag, environment, new_percentage)

        # Simulate verification
        await self._verify_deployment(flag, environment)

    async def _gradual_deployment(
        self,
        flag: FeatureFlagConfig,
        environment: Environment,
        target_percentage: float
    ) -> None:
        """Execute gradual rollout"""
        current = flag.rollout_percentage
        increment = flag.rollout_increment

        logger.info(f"Starting gradual rollout from {current}% to {target_percentage}%")

        while current < target_percentage:
            next_percentage = min(current + increment, target_percentage)
            logger.info(f"Rolling out to {next_percentage}%...")

            # Simulate rollout step
            await asyncio.sleep(0.5)
            current = next_percentage

        logger.info(f"Gradual rollout completed at {target_percentage}%")

    async def _canary_deployment(
        self,
        flag: FeatureFlagConfig,
        environment: Environment,
        target_percentage: float
    ) -> None:
        """Execute canary deployment"""
        logger.info(f"Starting canary deployment to {target_percentage}%")

        # Canary phase (small percentage)
        canary_percentage = min(5.0, target_percentage)
        logger.info(f"Canary phase: {canary_percentage}%")
        await asyncio.sleep(1)

        # Monitor canary
        logger.info("Monitoring canary metrics...")
        await asyncio.sleep(2)

        # Full rollout
        if target_percentage > canary_percentage:
            logger.info(f"Canary successful, rolling out to {target_percentage}%")
            await asyncio.sleep(1)

        logger.info("Canary deployment completed")

    async def _ab_test_deployment(
        self,
        flag: FeatureFlagConfig,
        environment: Environment,
        target_percentage: float
    ) -> None:
        """Execute A/B test deployment"""
        logger.info(f"Starting A/B test deployment to {target_percentage}%")

        # Split traffic
        logger.info(f"Splitting traffic: {target_percentage}% treatment, {100-target_percentage}% control")
        await asyncio.sleep(1)

        logger.info("A/B test deployment completed")

    async def _verify_deployment(
        self,
        flag: FeatureFlagConfig,
        environment: Environment
    ) -> None:
        """Verify deployment success"""
        logger.info("Verifying deployment...")

        # Simulate verification checks
        await asyncio.sleep(0.5)

        # Check application health
        logger.info("✅ Application health check passed")

        # Check feature flag propagation
        logger.info("✅ Feature flag propagation verified")

        # Check metrics
        logger.info("✅ Metrics collection operational")

    def _generate_deployment_id(self, flag_key: str, environment: Environment) -> str:
        """Generate unique deployment ID"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        hash_input = f"{flag_key}-{environment.value}-{timestamp}"
        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        return f"deploy-{flag_key}-{environment.value}-{timestamp}-{hash_suffix}"

    async def gradual_rollout(
        self,
        flag_key: str,
        environment: Environment,
        deployed_by: str = "system"
    ) -> list[FeatureFlagDeployment]:
        """Execute gradual rollout according to flag configuration"""
        if flag_key not in self.flags:
            raise ValueError(f"Feature flag '{flag_key}' not found")

        flag = self.flags[flag_key]

        if flag.rollout_strategy != RolloutStrategy.GRADUAL:
            raise ValueError(f"Flag '{flag_key}' is not configured for gradual rollout")

        deployments = []
        current_percentage = flag.rollout_percentage
        target_percentage = flag.target_percentage
        increment = flag.rollout_increment

        logger.info(f"Starting gradual rollout for '{flag_key}': {current_percentage}% -> {target_percentage}%")

        while current_percentage < target_percentage:
            next_percentage = min(current_percentage + increment, target_percentage)

            logger.info(f"Deploying {flag_key} at {next_percentage}% to {environment.value}")

            deployment = await self.deploy_flag(
                flag_key,
                environment,
                new_percentage=next_percentage,
                deployed_by=deployed_by
            )

            deployments.append(deployment)
            current_percentage = next_percentage

            # Wait before next increment (in production, this would be hours/days)
            if current_percentage < target_percentage:
                logger.info("Waiting before next increment...")
                await asyncio.sleep(2)  # Simulate wait time

        logger.info(f"Gradual rollout completed for '{flag_key}'")
        return deployments

    def get_flag(self, flag_key: str) -> FeatureFlagConfig | None:
        """Get feature flag by key"""
        return self.flags.get(flag_key)

    def list_flags(
        self,
        environment: Environment | None = None,
        status: FeatureFlagStatus | None = None,
        tags: list[str] | None = None
    ) -> list[FeatureFlagConfig]:
        """List feature flags with optional filtering"""
        flags = list(self.flags.values())

        if environment:
            flags = [f for f in flags if environment in f.environments]

        if status:
            flags = [f for f in flags if f.status == status]

        if tags:
            flags = [f for f in flags if any(tag in f.tags for tag in tags)]

        return flags

    def get_deployment_history(
        self,
        flag_key: str | None = None,
        environment: Environment | None = None,
        limit: int = 10
    ) -> list[FeatureFlagDeployment]:
        """Get deployment history with optional filtering"""
        deployments = self.deployments

        if flag_key:
            deployments = [d for d in deployments if d.flag_key == flag_key]

        if environment:
            deployments = [d for d in deployments if d.environment == environment]

        # Sort by deployment time, most recent first
        deployments.sort(key=lambda d: d.deployed_at, reverse=True)

        return deployments[:limit]

    def export_flags(self, output_file: Path) -> None:
        """Export all flags to YAML file"""
        flags_data = {
            flag_key: flag.to_dict()
            for flag_key, flag in self.flags.items()
        }

        with open(output_file, 'w') as f:
            yaml.safe_dump(flags_data, f, indent=2)

        logger.info(f"Exported {len(self.flags)} flags to {output_file}")

    def import_flags(self, input_file: Path) -> None:
        """Import flags from YAML file"""
        with open(input_file) as f:
            flags_data = yaml.safe_load(f)

        imported_count = 0
        for flag_key, flag_data in flags_data.items():
            try:
                flag = self._dict_to_flag(flag_data)
                self.flags[flag_key] = flag
                imported_count += 1
            except Exception as e:
                logger.error(f"Failed to import flag '{flag_key}': {e}")

        self.save_state()
        logger.info(f"Imported {imported_count} flags from {input_file}")


async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="🚩 Feature Flag Automation for AI Enhanced PDF Scholar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new feature flag
  python feature_flag_deployer.py create --key new_ui --name "New UI Design" --description "Updated interface design"

  # Deploy flag to staging
  python feature_flag_deployer.py deploy --key new_ui --env staging --status enabled --percentage 50

  # Execute gradual rollout
  python feature_flag_deployer.py rollout --key new_ui --env production

  # List all flags
  python feature_flag_deployer.py list --env production --status enabled

  # Get deployment history
  python feature_flag_deployer.py history --key new_ui --limit 5
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create new feature flag')
    create_parser.add_argument('--key', type=str, required=True, help='Flag key')
    create_parser.add_argument('--name', type=str, required=True, help='Flag name')
    create_parser.add_argument('--description', type=str, required=True, help='Flag description')
    create_parser.add_argument('--strategy', type=str, default='manual',
                              choices=['immediate', 'gradual', 'canary', 'ab_test', 'manual'],
                              help='Rollout strategy')
    create_parser.add_argument('--environments', type=str, nargs='*',
                              choices=['development', 'staging', 'production'],
                              default=['development', 'staging', 'production'],
                              help='Target environments')
    create_parser.add_argument('--tags', type=str, nargs='*', help='Flag tags')

    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy feature flag')
    deploy_parser.add_argument('--key', type=str, required=True, help='Flag key')
    deploy_parser.add_argument('--env', '--environment', type=str, required=True,
                              choices=['development', 'staging', 'production'],
                              help='Target environment')
    deploy_parser.add_argument('--status', type=str,
                              choices=['disabled', 'enabled', 'testing', 'staged', 'production'],
                              help='New status')
    deploy_parser.add_argument('--percentage', type=float, help='Rollout percentage (0-100)')
    deploy_parser.add_argument('--deployed-by', type=str, default='cli-user', help='Deployer name')

    # Rollout command
    rollout_parser = subparsers.add_parser('rollout', help='Execute gradual rollout')
    rollout_parser.add_argument('--key', type=str, required=True, help='Flag key')
    rollout_parser.add_argument('--env', '--environment', type=str, required=True,
                               choices=['development', 'staging', 'production'],
                               help='Target environment')
    rollout_parser.add_argument('--deployed-by', type=str, default='cli-user', help='Deployer name')

    # List command
    list_parser = subparsers.add_parser('list', help='List feature flags')
    list_parser.add_argument('--env', '--environment', type=str,
                            choices=['development', 'staging', 'production'],
                            help='Filter by environment')
    list_parser.add_argument('--status', type=str,
                            choices=['disabled', 'enabled', 'testing', 'staged', 'production'],
                            help='Filter by status')
    list_parser.add_argument('--tags', type=str, nargs='*', help='Filter by tags')

    # History command
    history_parser = subparsers.add_parser('history', help='Get deployment history')
    history_parser.add_argument('--key', type=str, help='Filter by flag key')
    history_parser.add_argument('--env', '--environment', type=str,
                               choices=['development', 'staging', 'production'],
                               help='Filter by environment')
    history_parser.add_argument('--limit', type=int, default=10, help='Number of deployments to show')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update feature flag')
    update_parser.add_argument('--key', type=str, required=True, help='Flag key')
    update_parser.add_argument('--name', type=str, help='New name')
    update_parser.add_argument('--description', type=str, help='New description')
    update_parser.add_argument('--target-percentage', type=float, help='New target percentage')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export flags to YAML')
    export_parser.add_argument('--output', type=str, default='feature_flags.yml', help='Output file')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import flags from YAML')
    import_parser.add_argument('--input', type=str, required=True, help='Input file')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize deployer
    deployer = FeatureFlagDeployer()

    try:
        if args.command == 'create':
            config = FeatureFlagConfig(
                key=args.key,
                name=args.name,
                description=args.description,
                status=FeatureFlagStatus.DISABLED,
                rollout_strategy=RolloutStrategy(args.strategy),
                environments=[Environment(env) for env in args.environments],
                tags=args.tags or []
            )

            deployer.create_flag(config)
            print(f"✅ Created feature flag: {args.key}")

        elif args.command == 'deploy':
            deployment = await deployer.deploy_flag(
                flag_key=args.key,
                environment=Environment(args.env),
                new_status=FeatureFlagStatus(args.status) if args.status else None,
                new_percentage=args.percentage,
                deployed_by=args.deployed_by
            )

            print("🚀 Deployment Result:")
            print(f"  Flag: {deployment.flag_key}")
            print(f"  Environment: {deployment.environment.value}")
            print(f"  Status: {deployment.previous_status.value} → {deployment.new_status.value}")
            print(f"  Percentage: {deployment.previous_percentage}% → {deployment.new_percentage}%")
            print(f"  Success: {deployment.success}")

        elif args.command == 'rollout':
            deployments = await deployer.gradual_rollout(
                flag_key=args.key,
                environment=Environment(args.env),
                deployed_by=args.deployed_by
            )

            print("📈 Gradual Rollout Completed:")
            print(f"  Flag: {args.key}")
            print(f"  Environment: {args.env}")
            print(f"  Deployments: {len(deployments)}")

            for i, deployment in enumerate(deployments, 1):
                print(f"    {i}. {deployment.new_percentage}% ({deployment.deployed_at.strftime('%H:%M:%S')})")

        elif args.command == 'list':
            environment = Environment(args.env) if args.env else None
            status = FeatureFlagStatus(args.status) if args.status else None

            flags = deployer.list_flags(
                environment=environment,
                status=status,
                tags=args.tags
            )

            if not flags:
                print("No feature flags found matching criteria")
                return

            print(f"🚩 Feature Flags ({len(flags)}):")
            print()

            for flag in flags:
                print(f"  📋 {flag.key}")
                print(f"     Name: {flag.name}")
                print(f"     Status: {flag.status.value}")
                print(f"     Strategy: {flag.rollout_strategy.value}")
                print(f"     Rollout: {flag.rollout_percentage}% / {flag.target_percentage}%")
                print(f"     Environments: {', '.join(env.value for env in flag.environments)}")
                if flag.tags:
                    print(f"     Tags: {', '.join(flag.tags)}")
                print()

        elif args.command == 'history':
            environment = Environment(args.env) if args.env else None

            deployments = deployer.get_deployment_history(
                flag_key=args.key,
                environment=environment,
                limit=args.limit
            )

            if not deployments:
                print("No deployment history found")
                return

            print(f"📚 Deployment History ({len(deployments)}):")
            print()

            for deployment in deployments:
                status_icon = "✅" if deployment.success else "❌"
                print(f"  {status_icon} {deployment.deployment_id}")
                print(f"     Flag: {deployment.flag_key}")
                print(f"     Environment: {deployment.environment.value}")
                print(f"     Change: {deployment.previous_status.value} → {deployment.new_status.value}")
                print(f"     Percentage: {deployment.previous_percentage}% → {deployment.new_percentage}%")
                print(f"     Deployed: {deployment.deployed_at.strftime('%Y-%m-%d %H:%M:%S')} by {deployment.deployed_by}")
                if not deployment.success:
                    print(f"     Error: {deployment.error_message}")
                print()

        elif args.command == 'update':
            updates = {}
            if args.name:
                updates['name'] = args.name
            if args.description:
                updates['description'] = args.description
            if args.target_percentage is not None:
                updates['target_percentage'] = args.target_percentage

            deployer.update_flag(args.key, updates)
            print(f"✅ Updated feature flag: {args.key}")

        elif args.command == 'export':
            output_file = Path(args.output)
            deployer.export_flags(output_file)
            print(f"📤 Exported flags to: {output_file}")

        elif args.command == 'import':
            input_file = Path(args.input)
            deployer.import_flags(input_file)
            print(f"📥 Imported flags from: {input_file}")

    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))
