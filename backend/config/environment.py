"""
Environment Detection and Management

Provides unified environment detection across all configuration modules.
"""

import os
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Application environment types with validation."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

    @classmethod
    def from_string(cls, env_str: str) -> 'Environment':
        """Convert string to Environment enum with validation."""
        if not env_str:
            return cls.DEVELOPMENT

        env_value = env_str.lower().strip()

        # Handle common variations
        env_mapping = {
            "dev": cls.DEVELOPMENT,
            "develop": cls.DEVELOPMENT,
            "development": cls.DEVELOPMENT,
            "test": cls.TESTING,
            "testing": cls.TESTING,
            "stage": cls.STAGING,
            "staging": cls.STAGING,
            "prod": cls.PRODUCTION,
            "production": cls.PRODUCTION,
        }

        return env_mapping.get(env_value, cls.DEVELOPMENT)

    def is_production(self) -> bool:
        """Check if current environment is production."""
        return self == self.PRODUCTION

    def is_development(self) -> bool:
        """Check if current environment is development."""
        return self == self.DEVELOPMENT

    def is_testing(self) -> bool:
        """Check if current environment is testing."""
        return self == self.TESTING

    def requires_strict_security(self) -> bool:
        """Check if environment requires strict security settings."""
        return self in {self.STAGING, self.PRODUCTION}


def get_current_environment() -> Environment:
    """
    Detect current environment from various sources.

    Checks multiple environment variables in order of precedence:
    1. ENVIRONMENT
    2. ENV
    3. FLASK_ENV (legacy)
    4. DJANGO_SETTINGS_MODULE (if applicable)

    Returns:
        Environment enum value
    """
    # Check multiple possible environment variables
    for env_var in ["ENVIRONMENT", "ENV", "FLASK_ENV", "APP_ENV"]:
        env_value = os.getenv(env_var)
        if env_value:
            environment = Environment.from_string(env_value)
            logger.debug(f"Environment detected from {env_var}: {environment.value}")
            return environment

    # Special case: GitHub Actions
    if os.getenv("GITHUB_ACTIONS"):
        logger.debug("Environment detected from GitHub Actions: testing")
        return Environment.TESTING

    # Special case: CI environments
    if any(os.getenv(ci_var) for ci_var in ["CI", "CONTINUOUS_INTEGRATION", "BUILD_ID"]):
        logger.debug("Environment detected from CI variables: testing")
        return Environment.TESTING

    # Default to development
    logger.debug("Environment defaulted to: development")
    return Environment.DEVELOPMENT


def validate_environment_consistency() -> Optional[str]:
    """
    Validate that environment configuration is consistent.

    Returns:
        Error message if inconsistency found, None if consistent
    """
    current_env = get_current_environment()

    # Check for common configuration mismatches
    issues = []

    # Production environment checks
    if current_env.is_production():
        # Check for debug flags in production
        if os.getenv("DEBUG", "").lower() in {"true", "1", "yes"}:
            issues.append("DEBUG should not be enabled in production")

        # Check for development-specific configurations
        dev_indicators = ["localhost", "127.0.0.1", "dev", "debug"]
        cors_origins = os.getenv("CORS_ORIGINS", "")

        for indicator in dev_indicators:
            if indicator in cors_origins.lower():
                issues.append(f"CORS origins contain development indicator '{indicator}' in production")

    # Development environment checks
    elif current_env.is_development():
        # Warn about missing development tools
        if not os.getenv("DEBUG"):
            issues.append("DEBUG not set in development environment (consider setting for better debugging)")

    if issues:
        return "; ".join(issues)

    return None