"""
Production Secrets Management Integration
Comprehensive integration with Agent A1's secrets management system,
providing secure configuration loading, key rotation, and secrets monitoring.
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any

from ..core.secrets_vault import (
    ProductionSecretsManager,
    SecretEncryptionContext,
    SecretStrength,
    generate_secure_secret,
    validate_prod_secrets,
)
from ..services.metrics_service import MetricsService
from .production import ProductionConfig

logger = logging.getLogger(__name__)


class SecretType(StrEnum):
    """Classifies the different secret use-cases."""

    def _generate_next_value_(self, start, count, last_values) -> Any:
        return self.lower()

    GENERIC = auto()
    DATABASE_PASSWORD = auto()
    DATABASE_URL = auto()
    API_KEY = auto()
    JWT_SECRET = auto()
    JWT_PRIVATE_KEY = auto()
    ENCRYPTION_KEY = auto()
    WEBHOOK_SECRET = auto()


@dataclass
class SecretDefinition:
    """Definition of a required secret."""

    key: str
    description: str
    required: bool = True
    secret_type: SecretType = SecretType.GENERIC
    min_length: int = 8
    validation_pattern: str | None = None
    rotation_interval_days: int | None = None
    default_value: str | None = None


@dataclass
class ProductionSecretsConfig:
    """Production secrets configuration."""

    # Database secrets
    database_secrets: list[SecretDefinition] = field(
        default_factory=lambda: [
            SecretDefinition(
                key="DATABASE_PASSWORD",
                description="PostgreSQL database password",
                secret_type=SecretType.DATABASE_PASSWORD,
                min_length=16,
                rotation_interval_days=90,
            ),
            SecretDefinition(
                key="DATABASE_URL",
                description="Complete database connection URL",
                secret_type=SecretType.DATABASE_URL,
                min_length=20,
            ),
        ]
    )

    # API Keys
    api_secrets: list[SecretDefinition] = field(
        default_factory=lambda: [
            SecretDefinition(
                key="GOOGLE_API_KEY",
                description="Google Gemini API key",
                secret_type=SecretType.API_KEY,
                min_length=20,
            ),
            SecretDefinition(
                key="OPENAI_API_KEY",
                description="OpenAI API key",
                secret_type=SecretType.API_KEY,
                required=False,
            ),
        ]
    )

    # Security secrets
    security_secrets: list[SecretDefinition] = field(
        default_factory=lambda: [
            SecretDefinition(
                key="SECRET_KEY",
                description="Application secret key for signing",
                secret_type=SecretType.JWT_SECRET,
                min_length=32,
                rotation_interval_days=30,
            ),
            SecretDefinition(
                key="JWT_PRIVATE_KEY",
                description="JWT signing private key",
                secret_type=SecretType.JWT_PRIVATE_KEY,
                min_length=100,
            ),
            SecretDefinition(
                key="ENCRYPTION_KEY",
                description="Data encryption key",
                secret_type=SecretType.ENCRYPTION_KEY,
                min_length=32,
                rotation_interval_days=60,
            ),
        ]
    )

    # Infrastructure secrets
    infrastructure_secrets: list[SecretDefinition] = field(
        default_factory=lambda: [
            SecretDefinition(
                key="REDIS_PASSWORD",
                description="Redis cache password",
                secret_type=SecretType.DATABASE_PASSWORD,
                min_length=16,
                required=False,
            ),
            SecretDefinition(
                key="MONITORING_API_KEY",
                description="Monitoring system API key",
                secret_type=SecretType.API_KEY,
                required=False,
            ),
        ]
    )

    # Application-specific secrets
    application_secrets: list[SecretDefinition] = field(
        default_factory=lambda: [
            SecretDefinition(
                key="WEBHOOK_SECRET",
                description="Webhook signature secret",
                secret_type=SecretType.WEBHOOK_SECRET,
                min_length=24,
                required=False,
            )
        ]
    )


class ProductionSecretsIntegration:
    """
    Production secrets integration system that bridges the secrets vault
    with application configuration and provides secure secret management.
    """

    def __init__(
        self,
        secrets_manager: ProductionSecretsManager | None = None,
        production_config: ProductionConfig | None = None,
        metrics_service: MetricsService | None = None,
    ) -> None:
        """Initialize secrets integration."""
        self.secrets_manager = secrets_manager or ProductionSecretsManager()
        self.production_config = production_config
        self.metrics_service = metrics_service

        # Configuration
        self.secrets_config = ProductionSecretsConfig()

        # Secret storage and caching
        self.decrypted_secrets: dict[str, str] = {}
        self.secret_contexts: dict[str, SecretEncryptionContext] = {}
        self.secret_metadata: dict[str, dict[str, Any]] = {}

        # Rotation tracking
        self.rotation_schedule: dict[
            str, float
        ] = {}  # secret_key -> next_rotation_time
        self.rotation_in_progress: set[str] = set[str]()

        # Security monitoring
        self.access_tracking: dict[str, list[float]] = {}  # secret_key -> access_times
        self.rotation_history: list[dict[str, Any]] = []

        logger.info("Production secrets integration initialized")

    async def initialize(self) -> None:
        """Initialize secrets management system."""
        try:
            # Initialize the secrets manager
            await asyncio.to_thread(self.secrets_manager._initialize_crypto)

            # Load all production secrets
            await self.load_production_secrets()

            # Set up rotation schedules
            self._setup_rotation_schedules()

            # Start background tasks
            asyncio.create_task(self._rotation_monitor())
            asyncio.create_task(self._access_monitor())

            # Validate all secrets
            validation_result = self.validate_all_secrets()
            if validation_result["overall_status"] != "passed":
                logger.warning(f"Secret validation issues: {validation_result}")

            logger.info("Secrets integration initialization completed")

        except Exception as e:
            logger.error(f"Failed to initialize secrets integration: {e}")
            raise

    async def load_production_secrets(self) -> None:
        """Load all production secrets from various sources."""
        all_secrets = {}

        # Collect all secret definitions
        all_secret_defs = (
            self.secrets_config.database_secrets
            + self.secrets_config.api_secrets
            + self.secrets_config.security_secrets
            + self.secrets_config.infrastructure_secrets
            + self.secrets_config.application_secrets
        )

        for secret_def in all_secret_defs:
            try:
                secret_value = await self._load_single_secret(secret_def)
                if secret_value:
                    all_secrets[secret_def.key] = secret_value
                    self._track_secret_access(secret_def.key)
                elif secret_def.required:
                    logger.error(f"Required secret not found: {secret_def.key}")
                    raise ValueError(f"Required secret missing: {secret_def.key}")

            except Exception as e:
                logger.error(f"Failed to load secret {secret_def.key}: {e}")
                if secret_def.required:
                    raise

        # Store decrypted secrets (in production, keep encrypted until needed)
        self.decrypted_secrets = all_secrets

        logger.info(f"Loaded {len(all_secrets)} production secrets")

    async def _load_single_secret(self, secret_def: SecretDefinition) -> str | None:
        """Load a single secret from available sources."""
        secret_value = None

        # Try environment variables first
        secret_value = os.getenv(secret_def.key)
        if secret_value:
            logger.debug(f"Loaded secret {secret_def.key} from environment")
            return secret_value

        # Try encrypted secrets vault
        try:
            encrypted_data, context = await asyncio.to_thread(
                self.secrets_manager.encrypt_secret,
                secret_def.default_value or "placeholder",
                secret_def.key,
            )

            if encrypted_data and context:
                decrypted_value = await asyncio.to_thread(
                    self.secrets_manager.decrypt_secret,
                    encrypted_data,
                    secret_def.key,
                    context,
                )

                if decrypted_value and decrypted_value != "placeholder":
                    self.secret_contexts[secret_def.key] = context
                    logger.debug(f"Loaded secret {secret_def.key} from vault")
                    return decrypted_value

        except Exception as e:
            logger.warning(f"Failed to load {secret_def.key} from vault: {e}")

        # Generate secure secret if missing and not required
        if not secret_def.required and not secret_value:
            if secret_def.secret_type in {
                SecretType.JWT_SECRET,
                SecretType.ENCRYPTION_KEY,
                SecretType.WEBHOOK_SECRET,
            }:
                secret_value = await self._generate_secret(secret_def)
                if secret_value:
                    logger.info(f"Generated secure secret for {secret_def.key}")
                    # Store in vault for future use
                    await self._store_secret(secret_def.key, secret_value)

        return secret_value

    async def _generate_secret(self, secret_def: SecretDefinition) -> str:
        """Generate secure secret based on definition."""
        try:
            # Determine strength based on secret type
            if secret_def.secret_type in {
                SecretType.ENCRYPTION_KEY,
                SecretType.JWT_SECRET,
            }:
                strength = SecretStrength.HIGH
            elif secret_def.secret_type in {
                SecretType.DATABASE_PASSWORD,
                SecretType.WEBHOOK_SECRET,
            }:
                strength = SecretStrength.MEDIUM
            else:
                strength = SecretStrength.MEDIUM

            # Generate secret
            secret_value = await asyncio.to_thread(
                generate_secure_secret, secret_def.secret_type.value, strength
            )

            return secret_value

        except Exception as e:
            logger.error(f"Failed to generate secret for {secret_def.key}: {e}")
            return None

    async def _store_secret(self, secret_key: str, secret_value: str) -> None:
        """Store secret in encrypted vault."""
        try:
            encrypted_data, context = await asyncio.to_thread(
                self.secrets_manager.encrypt_secret, secret_value, secret_key
            )

            if encrypted_data and context:
                self.secret_contexts[secret_key] = context
                logger.debug(f"Stored secret {secret_key} in vault")

        except Exception as e:
            logger.error(f"Failed to store secret {secret_key}: {e}")

    def get_secret(self, secret_key: str, default: str | None = None) -> str | None:
        """
        Get decrypted secret value.

        Args:
            secret_key: Secret key to retrieve
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        try:
            # Track access
            self._track_secret_access(secret_key)

            # Get from cache
            if secret_key in self.decrypted_secrets:
                return self.decrypted_secrets[secret_key]

            # Try environment variable as fallback
            env_value = os.getenv(secret_key)
            if env_value:
                return env_value

            return default

        except Exception as e:
            logger.error(f"Failed to get secret {secret_key}: {e}")
            return default

    async def get_secret_async(
        self, secret_key: str, default: str | None = None
    ) -> str | None:
        """Async version of get_secret."""
        return self.get_secret(secret_key, default)

    @asynccontextmanager
    async def get_temporary_secret(
        self, secret_key: str
    ) -> AsyncGenerator[str | None, None]:
        """
        Get secret with automatic cleanup (for temporary use).

        Args:
            secret_key: Secret key to retrieve

        Yields:
            Secret value
        """
        secret_value = None
        try:
            secret_value = self.get_secret(secret_key)
            yield secret_value
        finally:
            # Clear from memory after use
            if secret_value:
                # Overwrite memory (simplified)
                secret_value = "x" * len(secret_value)
                del secret_value

    async def rotate_secret(
        self, secret_key: str, new_value: str | None = None
    ) -> bool:
        """
        Rotate a secret with the new value.

        Args:
            secret_key: Secret key to rotate
            new_value: New secret value (generated if not provided)

        Returns:
            True if rotation was successful
        """
        if secret_key in self.rotation_in_progress:
            logger.warning(f"Secret rotation already in progress: {secret_key}")
            return False

        self.rotation_in_progress.add(secret_key)

        try:
            # Find secret definition
            secret_def = self._find_secret_definition(secret_key)
            if not secret_def:
                logger.error(f"Secret definition not found: {secret_key}")
                return False

            # Generate new value if not provided
            if not new_value:
                new_value = await self._generate_secret(secret_def)
                if not new_value:
                    logger.error(f"Failed to generate new value for {secret_key}")
                    return False

            # Store old value for rollback
            old_value = self.decrypted_secrets.get(secret_key)
            old_context = self.secret_contexts.get(secret_key)

            try:
                # Store new secret
                await self._store_secret(secret_key, new_value)
                self.decrypted_secrets[secret_key] = new_value

                # Update rotation schedule
                if secret_def.rotation_interval_days:
                    next_rotation = time.time() + (
                        secret_def.rotation_interval_days * 24 * 3600
                    )
                    self.rotation_schedule[secret_key] = next_rotation

                # Record rotation
                rotation_record = {
                    "secret_key": secret_key,
                    "timestamp": time.time(),
                    "success": True,
                    "method": "automatic" if not new_value else "manual",
                }
                self.rotation_history.append(rotation_record)

                # Metrics
                if self.metrics_service:
                    self.metrics_service.record_security_event(
                        "secret_rotation", "info"
                    )

                logger.info(f"Successfully rotated secret: {secret_key}")
                return True

            except Exception as e:
                # Rollback on failure
                if old_value:
                    self.decrypted_secrets[secret_key] = old_value
                if old_context:
                    self.secret_contexts[secret_key] = old_context

                logger.error(f"Failed to rotate secret {secret_key}, rolled back: {e}")
                return False

        finally:
            self.rotation_in_progress.discard(secret_key)

    def _find_secret_definition(self, secret_key: str) -> SecretDefinition | None:
        """Find secret definition by key."""
        all_defs = (
            self.secrets_config.database_secrets
            + self.secrets_config.api_secrets
            + self.secrets_config.security_secrets
            + self.secrets_config.infrastructure_secrets
            + self.secrets_config.application_secrets
        )

        for secret_def in all_defs:
            if secret_def.key == secret_key:
                return secret_def

        return None

    def _setup_rotation_schedules(self) -> None:
        """Set up automatic secret rotation schedules."""
        current_time = time.time()

        all_defs = (
            self.secrets_config.database_secrets
            + self.secrets_config.api_secrets
            + self.secrets_config.security_secrets
            + self.secrets_config.infrastructure_secrets
            + self.secrets_config.application_secrets
        )

        for secret_def in all_defs:
            if (
                secret_def.rotation_interval_days
                and secret_def.key in self.decrypted_secrets
            ):
                next_rotation = current_time + (
                    secret_def.rotation_interval_days * 24 * 3600
                )
                self.rotation_schedule[secret_def.key] = next_rotation

        logger.info(
            f"Set up rotation schedules for {len(self.rotation_schedule)} secrets"
        )

    async def _rotation_monitor(self) -> None:
        """Background task to monitor and execute secret rotations."""
        while True:
            try:
                current_time = time.time()

                for secret_key, next_rotation_time in list[Any](
                    self.rotation_schedule.items()
                ):
                    if current_time >= next_rotation_time:
                        logger.info(
                            f"Starting automatic rotation for secret: {secret_key}"
                        )
                        success = await self.rotate_secret(secret_key)

                        if success:
                            logger.info(
                                f"Automatic rotation completed for: {secret_key}"
                            )
                        else:
                            logger.error(f"Automatic rotation failed for: {secret_key}")
                            # Reschedule for retry in 1 hour
                            self.rotation_schedule[secret_key] = current_time + 3600

                # Check every hour
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"Error in rotation monitor: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _access_monitor(self) -> None:
        """Background task to monitor secret access patterns."""
        while True:
            try:
                current_time = time.time()

                # Clean old access records (keep last 24 hours)
                cutoff_time = current_time - 86400
                for secret_key in list[Any](self.access_tracking.keys()):
                    self.access_tracking[secret_key] = [
                        access_time
                        for access_time in self.access_tracking[secret_key]
                        if access_time > cutoff_time
                    ]

                    # Remove empty entries
                    if not self.access_tracking[secret_key]:
                        del self.access_tracking[secret_key]

                # Monitor for unusual access patterns
                for secret_key, access_times in self.access_tracking.items():
                    if len(access_times) > 1000:  # More than 1000 accesses per day
                        logger.warning(
                            f"High access frequency for secret: {secret_key}"
                        )

                # Check every 10 minutes
                await asyncio.sleep(600)

            except Exception as e:
                logger.error(f"Error in access monitor: {e}")
                await asyncio.sleep(300)

    def _track_secret_access(self, secret_key: str) -> None:
        """Track secret access for monitoring."""
        current_time = time.time()

        if secret_key not in self.access_tracking:
            self.access_tracking[secret_key] = []

        self.access_tracking[secret_key].append(current_time)

    def validate_all_secrets(self) -> dict[str, Any]:
        """Validate all loaded secrets."""
        try:
            return validate_prod_secrets(self.decrypted_secrets, "production")
        except Exception as e:
            logger.error(f"Secret validation failed: {e}")
            return {"overall_status": "failed", "error": str(e)}

    def get_secrets_health(self) -> dict[str, Any]:
        """Get comprehensive secrets health report."""
        current_time = time.time()

        # Count secrets by category
        secret_counts = {
            "database": len(self.secrets_config.database_secrets),
            "api": len(self.secrets_config.api_secrets),
            "security": len(self.secrets_config.security_secrets),
            "infrastructure": len(self.secrets_config.infrastructure_secrets),
            "application": len(self.secrets_config.application_secrets),
        }

        # Rotation status
        rotation_status = {}
        for secret_key, next_rotation in self.rotation_schedule.items():
            days_until_rotation = (next_rotation - current_time) / 86400
            rotation_status[secret_key] = {
                "days_until_rotation": round(days_until_rotation, 1),
                "overdue": days_until_rotation < 0,
            }

        # Access statistics
        access_stats = {}
        for secret_key, access_times in self.access_tracking.items():
            recent_accesses = len(
                [t for t in access_times if current_time - t < 3600]
            )  # Last hour
            access_stats[secret_key] = {
                "total_accesses_today": len(access_times),
                "accesses_last_hour": recent_accesses,
            }

        return {
            "status": "healthy",
            "timestamp": current_time,
            "secrets_loaded": len(self.decrypted_secrets),
            "secrets_by_category": secret_counts,
            "rotation_status": rotation_status,
            "access_statistics": access_stats,
            "vault_health": (
                self.secrets_manager.health_check()
                if hasattr(self.secrets_manager, "health_check")
                else {}
            ),
            "recent_rotations": len(
                [
                    r
                    for r in self.rotation_history
                    if current_time - r["timestamp"] < 86400
                ]
            ),
        }

    def get_configuration_dict(self) -> dict[str, Any]:
        """Get configuration dictionary with secrets (for application setup)."""
        config = {}

        # Add secrets to configuration
        for secret_key, secret_value in self.decrypted_secrets.items():
            config[secret_key] = secret_value

        # Add derived configurations
        if "DATABASE_PASSWORD" in config:
            # Build database URL if components are available
            db_user = os.getenv("DATABASE_USER", "ai_pdf_scholar")
            db_host = os.getenv("DATABASE_HOST", "localhost")
            db_port = os.getenv("DATABASE_PORT", "5432")
            db_name = os.getenv("DATABASE_NAME", "ai_pdf_scholar")

            if "DATABASE_URL" not in config:
                config["DATABASE_URL"] = (
                    f"postgresql://{db_user}:{config['DATABASE_PASSWORD']}@{db_host}:{db_port}/{db_name}"
                )

        return config


def create_production_secrets_integration(
    production_config: ProductionConfig | None = None,
    metrics_service: MetricsService | None = None,
) -> ProductionSecretsIntegration:
    """Create production secrets integration instance."""
    secrets_manager = ProductionSecretsManager()
    return ProductionSecretsIntegration(
        secrets_manager=secrets_manager,
        production_config=production_config,
        metrics_service=metrics_service,
    )


async def initialize_production_secrets(
    production_config: ProductionConfig | None = None,
    metrics_service: MetricsService | None = None,
) -> ProductionSecretsIntegration:
    """Initialize and load all production secrets."""
    secrets_integration = create_production_secrets_integration(
        production_config, metrics_service
    )
    await secrets_integration.initialize()
    return secrets_integration
