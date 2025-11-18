"""
CORS Security Configuration Module

Provides environment-specific CORS configuration with security best practices.
Replaces the vulnerable wildcard origins configuration with proper environment-based settings.
"""

import logging
import os
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class CORSConfig:
    """Secure CORS configuration manager."""

    def __init__(self) -> None:
        """Initialize CORS configuration based on environment."""
        self.environment = self._detect_environment()
        self.config = self._get_cors_config()
        self._validate_production_security()

    def _detect_environment(self) -> Environment:
        """Detect current environment from environment variables."""
        env_value = os.getenv("ENVIRONMENT", "development").lower()

        # Map common environment variable values
        env_mapping = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "test": Environment.TESTING,
            "testing": Environment.TESTING,
            "stage": Environment.STAGING,
            "staging": Environment.STAGING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION,
        }

        return env_mapping.get(env_value, Environment.DEVELOPMENT)

    def _parse_origins(self, origins_str: str) -> list[str]:
        """Parse CORS origins from environment variable string."""
        if not origins_str:
            return []

        # Split by comma and clean whitespace
        origins = [origin.strip() for origin in origins_str.split(",")]
        # Filter out empty strings
        origins = [origin for origin in origins if origin]

        return origins

    def _get_development_config(self) -> dict[str, Any]:
        """Get CORS configuration for development environment."""
        # Parse origins from environment or use safe defaults
        origins_str = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000",
        )
        origins = self._parse_origins(origins_str)

        return {
            "allow_origins": origins,
            "allow_credentials": True,
            "allow_methods": [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "OPTIONS",
                "HEAD",
                "PATCH",
            ],
            "allow_headers": [
                "Accept",
                "Accept-Language",
                "Content-Language",
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-CSRF-Token",
            ],
            "expose_headers": ["X-Total-Count", "X-Request-ID"],
            "max_age": 86400,  # 24 hours
        }

    def _get_testing_config(self) -> dict[str, Any]:
        """Get CORS configuration for testing environment."""
        # Testing should be restrictive but allow test origins
        origins_str = os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        )
        origins = self._parse_origins(origins_str)

        return {
            "allow_origins": origins,
            "allow_credentials": False,  # More restrictive for testing
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Accept",
                "Content-Type",
                "Authorization",
                "X-Requested-With",
            ],
            "expose_headers": ["X-Request-ID"],
            "max_age": 3600,  # 1 hour
        }

    def _get_staging_config(self) -> dict[str, Any]:
        """Get CORS configuration for staging environment."""
        # Staging should mirror production security but allow staging domains
        origins_str = os.getenv("CORS_ORIGINS", "")
        origins = self._parse_origins(origins_str)

        if not origins:
            logger.warning("No CORS origins configured for staging environment")

        return {
            "allow_origins": origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Accept",
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-CSRF-Token",
            ],
            "expose_headers": ["X-Request-ID"],
            "max_age": 3600,  # 1 hour
        }

    def _get_production_config(self) -> dict[str, Any]:
        """Get CORS configuration for production environment."""
        # Production must be explicitly configured - no defaults
        origins_str = os.getenv("CORS_ORIGINS", "")
        origins = self._parse_origins(origins_str)

        if not origins:
            logger.error("CORS_ORIGINS must be explicitly set in production")
            raise ValueError(
                "CORS_ORIGINS environment variable is required in production"
            )

        return {
            "allow_origins": origins,
            "allow_credentials": True,
            "allow_methods": [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "OPTIONS",
            ],  # Minimal necessary methods
            "allow_headers": [
                "Accept",
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-CSRF-Token",
            ],
            "expose_headers": ["X-Request-ID"],
            "max_age": 3600,  # 1 hour
        }

    def _get_cors_config(self) -> dict[str, Any]:
        """Get CORS configuration for current environment."""
        config_methods = {
            Environment.DEVELOPMENT: self._get_development_config,
            Environment.TESTING: self._get_testing_config,
            Environment.STAGING: self._get_staging_config,
            Environment.PRODUCTION: self._get_production_config,
        }

        config = config_methods[self.environment]()
        logger.info(f"Loaded CORS config for {self.environment.value} environment")

        # Log configuration (safely - don't log sensitive data)
        origins_count = len(config.get("allow_origins", []))
        logger.info(f"CORS configured with {origins_count} allowed origins")

        return config

    def _validate_production_security(self) -> None:
        """Validate that production configuration meets security requirements."""
        if self.environment != Environment.PRODUCTION:
            return

        origins = self.config.get("allow_origins", [])

        # Check for security violations
        security_issues = []

        # No wildcard origins in production
        if "*" in origins:
            security_issues.append("Wildcard (*) origins are not allowed in production")

        # No localhost or 127.0.0.1 in production
        localhost_patterns = ["localhost", "127.0.0.1"]
        for origin in origins:
            if any(pattern in origin.lower() for pattern in localhost_patterns):
                security_issues.append(
                    f"Localhost origin '{origin}' should not be used in production"
                )

        # Must have at least one origin
        if not origins:
            security_issues.append(
                "At least one origin must be configured in production"
            )

        # All origins should use HTTPS in production
        for origin in origins:
            if origin.startswith("http://") and not origin.startswith("https://"):
                security_issues.append(
                    f"Origin '{origin}' should use HTTPS in production"
                )

        if security_issues:
            error_msg = "CORS security validation failed:\n" + "\n".join(
                f"- {issue}" for issue in security_issues
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_middleware_config(self) -> dict[str, Any]:
        """Get configuration dict for FastAPI CORS middleware."""
        return self.config.copy()

    def log_security_info(self) -> None:
        """Log security information about CORS configuration."""
        origins = self.config.get("allow_origins", [])
        methods = self.config.get("allow_methods", [])
        credentials = self.config.get("allow_credentials", False)

        logger.info("=== CORS Security Configuration ===")
        logger.info(f"Environment: {self.environment.value}")
        logger.info(f"Allowed Origins: {len(origins)} configured")
        logger.info(f"Allowed Methods: {', '.join(methods)}")
        logger.info(f"Allow Credentials: {credentials}")
        logger.info(f"Max Age: {self.config.get('max_age', 'Not set')} seconds")

        # Log origins in development only
        if self.environment == Environment.DEVELOPMENT:
            for i, origin in enumerate(origins, 1):
                logger.info(f"  Origin {i}: {origin}")
        else:
            logger.info("  (Origins not logged in non-development environments)")

        logger.info("===================================")


def get_cors_config() -> CORSConfig:
    """Get configured CORS configuration instance."""
    return CORSConfig()


def validate_origin_format(origin: str) -> bool:
    """Validate that an origin string has proper format."""
    if not origin:
        return False

    # Must start with http:// or https://
    if not (origin.startswith("http://") or origin.startswith("https://")):
        return False

    # Must not end with slash
    if origin.endswith("/"):
        return False

    # Must contain domain after protocol
    protocol_part = origin.split("://", 1)
    if len(protocol_part) != 2 or not protocol_part[1]:
        return False

    return True


def get_safe_cors_origins() -> list[str]:
    """Get list of safe CORS origins for current environment."""
    cors_config = get_cors_config()
    origins = cors_config.get_middleware_config().get("allow_origins", [])

    # Filter out any invalid origins
    valid_origins = [origin for origin in origins if validate_origin_format(origin)]

    if len(valid_origins) != len(origins):
        logger.warning(
            f"Filtered out {len(origins) - len(valid_origins)} invalid CORS origins"
        )

    return valid_origins
