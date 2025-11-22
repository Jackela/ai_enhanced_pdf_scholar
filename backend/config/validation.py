"""
Configuration Validation

Provides validation utilities for configuration settings across all modules.
"""

import logging
import os
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""

    def __init__(
        self, message: str, field: str | None = None, issues: list[str] | None = None
    ):
        super().__init__(message)
        self.field = field
        self.issues = issues or []


class ConfigValidator:
    """Configuration validation utilities."""

    @staticmethod
    def validate_url(url: str, schemes: list[str] | None = None) -> bool:
        """
        Validate URL format and scheme.

        Args:
            url: URL to validate
            schemes: Allowed schemes (default: ['http', 'https'])

        Returns:
            True if URL is valid
        """
        if not url:
            return False

        try:
            parsed = urlparse(url)

            # Check scheme
            allowed_schemes = schemes or ["http", "https"]
            if parsed.scheme.lower() not in allowed_schemes:
                return False

            # Must have netloc (domain)
            return parsed.netloc

        except Exception:
            return False

    @staticmethod
    def validate_cors_origin(origin: str) -> bool:
        """
        Validate CORS origin format.

        Args:
            origin: Origin to validate

        Returns:
            True if origin is valid
        """
        if not origin or origin == "*":
            return True  # Wildcard is valid (though not secure in production)

        # Must be valid URL
        if not ConfigValidator.validate_url(origin):
            return False

        # Should not end with slash
        return not origin.endswith("/")

    @staticmethod
    def validate_redis_url(redis_url: str) -> bool:
        """
        Validate Redis connection URL.

        Args:
            redis_url: Redis URL to validate

        Returns:
            True if Redis URL is valid
        """
        if not redis_url:
            return False

        return ConfigValidator.validate_url(redis_url, schemes=["redis", "rediss"])

    @staticmethod
    def validate_port(port: int | str) -> bool:
        """
        Validate port number.

        Args:
            port: Port number to validate

        Returns:
            True if port is valid
        """
        try:
            port_int = int(port)
            return 1 <= port_int <= 65535
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_positive_int(value: int | str, min_value: int = 1) -> bool:
        """
        Validate positive integer.

        Args:
            value: Value to validate
            min_value: Minimum allowed value

        Returns:
            True if value is valid positive integer
        """
        try:
            int_value = int(value)
            return int_value >= min_value
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_file_path(path: str, must_exist: bool = False) -> bool:
        """
        Validate file path format and optionally existence.

        Args:
            path: File path to validate
            must_exist: If True, path must exist

        Returns:
            True if path is valid
        """
        if not path:
            return False

        # Check for path traversal attempts
        if ".." in path or path.startswith("/"):
            # Allow absolute paths but be cautious
            pass

        if must_exist:
            return os.path.exists(path)

        return True

    @staticmethod
    def validate_secret_key(secret: str, min_length: int = 32) -> bool:
        """
        Validate secret key strength.

        Args:
            secret: Secret key to validate
            min_length: Minimum required length

        Returns:
            True if secret is strong enough
        """
        if not secret:
            return False

        if len(secret) < min_length:
            return False

        # Check for common weak patterns
        weak_patterns = [
            "password",
            "secret",
            "key",
            "token",
            "123456",
            "abcdef",
            "default",
        ]

        secret_lower = secret.lower()
        return all(pattern not in secret_lower for pattern in weak_patterns)

    @staticmethod
    def validate_api_key(api_key: str, service: str = "generic") -> bool:
        """
        Validate API key format for specific services.

        Args:
            api_key: API key to validate
            service: Service type (e.g., 'google', 'openai')

        Returns:
            True if API key format is valid
        """
        if not api_key:
            return False

        # Service-specific validation
        if service.lower() == "google":
            # Google API keys typically start with AIza and are 39 characters
            return api_key.startswith("AIza") and len(api_key) == 39

        elif service.lower() == "openai":
            # OpenAI keys typically start with sk- and are longer
            return api_key.startswith("sk-") and len(api_key) > 20

        # Generic validation - must be reasonable length and not obviously fake
        if len(api_key) < 10:
            return False

        # Check for placeholder values
        placeholder_patterns = [
            "your_api_key",
            "placeholder",
            "example",
            "test_key",
            "fake_key",
            "dummy",
            "sample",
        ]

        api_key_lower = api_key.lower()
        return all(pattern not in api_key_lower for pattern in placeholder_patterns)


class SecurityValidator:
    """Security-focused configuration validation."""

    @staticmethod
    def validate_production_security(
        config: dict[str, Any], environment: str
    ) -> list[str]:
        """
        Validate production security settings.

        Args:
            config: Configuration dictionary
            environment: Current environment

        Returns:
            List of security issues found
        """
        issues: list[Any] = []

        if environment.lower() != "production":
            return issues

        # CORS security
        cors_origins = config.get("cors", {}).get("allow_origins", [])
        if "*" in cors_origins:
            issues.append("Wildcard CORS origins not allowed in production")

        for origin in cors_origins:
            if "localhost" in origin.lower() or "127.0.0.1" in origin:
                issues.append(f"Development origin '{origin}' found in production")

            if origin.startswith("http://"):
                issues.append(f"Insecure HTTP origin '{origin}' in production")

        # Database security
        database_config = config.get("database", {})
        db_url = database_config.get("url", "")

        if db_url and not db_url.startswith("postgresql"):
            issues.append("Production should use PostgreSQL, not SQLite")

        # API keys
        api_keys = config.get("api_keys", {})
        for service, key in api_keys.items():
            if not ConfigValidator.validate_api_key(key, service):
                issues.append(f"Invalid or placeholder API key for {service}")

        # Security headers
        security_config = config.get("security", {})
        if not security_config.get("enable_https", True):
            issues.append("HTTPS must be enabled in production")

        # Rate limiting
        rate_limit_config = config.get("rate_limiting", {})
        if not rate_limit_config.get("enabled", True):
            issues.append("Rate limiting should be enabled in production")

        return issues

    @staticmethod
    def validate_secret_management(config: dict[str, Any]) -> list[str]:
        """
        Validate secret management practices.

        Args:
            config: Configuration dictionary

        Returns:
            List of secret management issues
        """
        issues = []

        # Check for hardcoded secrets in config
        sensitive_keys = [
            "secret_key",
            "api_key",
            "password",
            "token",
            "private_key",
            "credential",
            "auth",
        ]

        def check_dict_for_secrets(d: dict[str, Any], path: str = "") -> None:
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key

                # Check if key name suggests it's sensitive and value looks hardcoded
                if (
                    any(sensitive in key.lower() for sensitive in sensitive_keys)
                    and isinstance(value, str)
                    and len(value) > 10
                    and not value.startswith("${")  # Environment variable
                    and not value.startswith("$(")  # Command substitution
                ):
                    issues.append(f"Potential hardcoded secret at {current_path}")

                # Recursively check nested dictionaries
                elif isinstance(value, dict):
                    check_dict_for_secrets(value, current_path)

        check_dict_for_secrets(config)

        return issues
