"""
Production CORS Configuration with Advanced Security
Enhanced CORS configuration for production deployment with strict validation,
origin verification, and security hardening.
"""

import ipaddress
import logging
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from ..config.production import ProductionConfig

logger = logging.getLogger(__name__)


@dataclass
class OriginValidationRule:
    """Rule for validating CORS origins."""

    pattern: str
    allowed: bool
    reason: str
    priority: int = 1000  # Lower number = higher priority


@dataclass
class CORSSecurityPolicy:
    """CORS security policy configuration."""

    # Origin validation
    strict_origin_validation: bool = True
    require_https_in_production: bool = True
    block_private_ips: bool = True
    block_localhost_in_production: bool = True

    # Domain validation
    allowed_domain_patterns: list[str] = field(default_factory=list)
    blocked_domain_patterns: list[str] = field(default_factory=list)
    require_valid_tld: bool = True
    max_subdomain_depth: int = 3

    # Security headers
    enforce_strict_headers: bool = True
    allowed_custom_headers: set[str] = field(default_factory=set)

    # Rate limiting
    enable_preflight_caching: bool = True
    max_age_seconds: int = 3600

    # Monitoring
    log_blocked_origins: bool = True
    alert_on_blocked_attempts: bool = True


class ProductionCORSValidator:
    """
    Advanced CORS origin validator with security policies
    and threat detection for production environments.
    """

    def __init__(self, security_policy: CORSSecurityPolicy | None = None) -> None:
        """Initialize CORS validator."""
        self.security_policy = security_policy or CORSSecurityPolicy()
        self.validation_rules: list[OriginValidationRule] = []
        self.blocked_origins: set[str] = set()
        self.validation_cache: dict[str, bool] = {}
        self.blocked_attempts: dict[str, list[float]] = {}

        self._initialize_default_rules()
        logger.info("Production CORS validator initialized")

    def _initialize_default_rules(self) -> None:
        """Initialize default validation rules."""
        rules = [
            # High priority security rules
            OriginValidationRule("*", False, "Wildcard origins not allowed", 1),
            OriginValidationRule(r"^null$", False, "Null origin not allowed", 2),
            OriginValidationRule(r"^file://", False, "File protocol not allowed", 3),
            OriginValidationRule(r"^data:", False, "Data URIs not allowed", 4),
            # Network security rules
            OriginValidationRule(
                r"^https?://localhost", False, "Localhost not allowed in production", 10
            ),
            OriginValidationRule(
                r"^https?://127\.0\.0\.1", False, "Loopback IP not allowed", 11
            ),
            OriginValidationRule(
                r"^https?://0\.0\.0\.0", False, "Unspecified IP not allowed", 12
            ),
            OriginValidationRule(
                r"^https?://10\.", False, "Private IP range not allowed", 13
            ),
            OriginValidationRule(
                r"^https?://192\.168\.", False, "Private IP range not allowed", 14
            ),
            OriginValidationRule(
                r"^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.",
                False,
                "Private IP range not allowed",
                15,
            ),
            # Protocol security
            OriginValidationRule(
                r"^http://[^/]+$", False, "HTTP not allowed in production", 20
            ),
            OriginValidationRule(r"^https://[^/]+$", True, "HTTPS allowed", 1000),
        ]

        self.validation_rules.extend(rules)
        self.validation_rules.sort(key=lambda r: r.priority)

    def add_validation_rule(self, rule: OriginValidationRule) -> None:
        """Add custom validation rule."""
        self.validation_rules.append(rule)
        self.validation_rules.sort(key=lambda r: r.priority)
        # Clear cache when rules change
        self.validation_cache.clear()

    @lru_cache(maxsize=1000)
    def validate_origin(self, origin: str) -> tuple[bool, str]:
        """
        Validate origin against security policy.

        Args:
            origin: Origin to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        if not origin:
            return False, "Empty origin"

        # Check against validation rules
        for rule in self.validation_rules:
            if re.match(rule.pattern, origin, re.IGNORECASE):
                if not rule.allowed:
                    self._log_blocked_origin(origin, rule.reason)
                    return False, rule.reason
                else:
                    return True, "Allowed by rule"

        # Additional security checks
        return self._perform_advanced_validation(origin)

    def _perform_advanced_validation(self, origin: str) -> tuple[bool, str]:
        """Perform advanced origin validation."""
        try:
            parsed = urlparse(origin)

            # Validate URL structure
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL structure"

            if parsed.scheme not in ["http", "https"]:
                return False, f"Unsupported scheme: {parsed.scheme}"

            # Check domain validation
            domain_valid, domain_reason = self._validate_domain(parsed.netloc)
            if not domain_valid:
                return False, domain_reason

            # Check IP address validation
            ip_valid, ip_reason = self._validate_ip_address(parsed.netloc)
            if not ip_valid:
                return False, ip_reason

            # Check against allowed patterns
            if self.security_policy.allowed_domain_patterns:
                pattern_valid = self._check_domain_patterns(
                    parsed.netloc,
                    self.security_policy.allowed_domain_patterns,
                    allow=True,
                )
                if not pattern_valid:
                    return False, "Domain not in allowed patterns"

            # Check against blocked patterns
            if self.security_policy.blocked_domain_patterns:
                pattern_valid = self._check_domain_patterns(
                    parsed.netloc,
                    self.security_policy.blocked_domain_patterns,
                    allow=False,
                )
                if not pattern_valid:
                    return False, "Domain matches blocked pattern"

            return True, "Advanced validation passed"

        except Exception as e:
            logger.error(f"Origin validation error: {e}")
            return False, f"Validation error: {str(e)}"

    def _validate_domain(self, netloc: str) -> tuple[bool, str]:
        """Validate domain name."""
        # Extract hostname (remove port if present)
        hostname = netloc.split(":")[0].lower()

        # Check subdomain depth
        parts = hostname.split(".")
        if (
            len(parts) > self.security_policy.max_subdomain_depth + 2
        ):  # +2 for domain.tld
            return False, f"Subdomain depth exceeds limit: {len(parts) - 2}"

        # Check for valid TLD if required
        if self.security_policy.require_valid_tld and len(parts) >= 2:
            tld = parts[-1]
            if not self._is_valid_tld(tld):
                return False, f"Invalid or suspicious TLD: {tld}"

        # Basic domain format validation
        domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
        for part in parts:
            if not re.match(domain_pattern, part):
                return False, f"Invalid domain part: {part}"

        return True, "Domain validation passed"

    def _validate_ip_address(self, netloc: str) -> tuple[bool, str]:
        """Validate IP address in origin."""
        # Extract IP (remove port if present)
        ip_str = netloc.split(":")[0]

        try:
            ip = ipaddress.ip_address(ip_str)

            if self.security_policy.block_private_ips:
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return False, f"Private/loopback IP not allowed: {ip}"

            # Block specific dangerous IPs
            if ip.is_unspecified or ip.is_multicast:
                return False, f"Invalid IP address type: {ip}"

            return True, "IP validation passed"

        except ValueError:
            # Not an IP address, continue with domain validation
            return True, "Not an IP address"

    def _check_domain_patterns(
        self, domain: str, patterns: list[str], allow: bool
    ) -> bool:
        """Check domain against patterns."""
        for pattern in patterns:
            if re.match(pattern, domain, re.IGNORECASE):
                return allow
        return not allow  # If no pattern matched and we're checking allow, return False

    def _is_valid_tld(self, tld: str) -> bool:
        """Check if TLD is valid (simplified check)."""
        # This is a simplified check. In production, you'd want a comprehensive TLD list
        suspicious_tlds = {"tk", "ml", "ga", "cf", "top", "work", "party"}
        return len(tld) >= 2 and tld.lower() not in suspicious_tlds

    def _log_blocked_origin(self, origin: str, reason: str) -> None:
        """Log blocked origin attempt."""
        if self.security_policy.log_blocked_origins:
            logger.warning(f"Blocked CORS origin '{origin}': {reason}")

        # Track blocked attempts for rate limiting/alerting
        current_time = time.time()
        if origin not in self.blocked_attempts:
            self.blocked_attempts[origin] = []

        self.blocked_attempts[origin].append(current_time)

        # Keep only recent attempts (last hour)
        cutoff = current_time - 3600
        self.blocked_attempts[origin] = [
            t for t in self.blocked_attempts[origin] if t > cutoff
        ]

        # Alert if too many attempts
        if (
            len(self.blocked_attempts[origin]) > 10
            and self.security_policy.alert_on_blocked_attempts
        ):
            logger.error(f"High frequency blocked attempts from origin: {origin}")

    def get_blocked_statistics(self) -> dict[str, Any]:
        """Get statistics about blocked origins."""
        return {
            "total_blocked_origins": len(self.blocked_origins),
            "recent_blocked_attempts": {
                origin: len(attempts)
                for origin, attempts in self.blocked_attempts.items()
                if attempts
            },
            "validation_cache_size": len(self.validation_cache),
        }


class ProductionCORSConfig:
    """
    Production CORS configuration with advanced security features.
    """

    def __init__(self, production_config: ProductionConfig | None = None) -> None:
        """Initialize production CORS configuration."""
        self.production_config = production_config
        self.validator = ProductionCORSValidator()
        self._validated_origins: list[str] = []
        self._cors_config: dict[str, Any] = {}

        # Initialize configuration
        self._initialize_configuration()
        logger.info("Production CORS configuration initialized")

    def _initialize_configuration(self) -> None:
        """Initialize CORS configuration based on production settings."""
        if self.production_config:
            security_config = self.production_config.security
            allowed_origins = security_config.allowed_origins
        else:
            import os

            origins_str = os.getenv("PROD_CORS_ORIGINS", "")
            allowed_origins = origins_str.split(",") if origins_str else []

        # Validate all configured origins
        validated_origins = []
        for origin in allowed_origins:
            origin = origin.strip()
            if origin:
                is_valid, reason = self.validator.validate_origin(origin)
                if is_valid:
                    validated_origins.append(origin)
                else:
                    logger.error(f"Invalid CORS origin '{origin}': {reason}")

        if not validated_origins:
            logger.error("No valid CORS origins configured for production")
            raise ValueError("At least one valid CORS origin must be configured")

        self._validated_origins = validated_origins
        self._cors_config = self._build_cors_config()

    def _build_cors_config(self) -> dict[str, Any]:
        """Build CORS configuration dictionary."""
        return {
            "allow_origins": self._validated_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Accept",
                "Accept-Language",
                "Content-Language",
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-CSRF-Token",
                "X-Request-ID",
            ],
            "expose_headers": [
                "X-Request-ID",
                "X-Total-Count",
                "X-Rate-Limit-Remaining",
                "X-Rate-Limit-Reset",
            ],
            "max_age": 3600,  # 1 hour
        }

    def validate_request_origin(self, origin: str | None) -> bool:
        """
        Validate origin from incoming request.

        Args:
            origin: Origin header from request

        Returns:
            True if origin is allowed
        """
        if not origin:
            # Allow requests without Origin header (same-origin or non-browser)
            return True

        is_valid, reason = self.validator.validate_origin(origin)
        if not is_valid:
            logger.warning(f"Rejected CORS request from origin '{origin}': {reason}")
            return False

        # Check if origin is in allowed list
        if origin in self._validated_origins:
            return True

        logger.warning(f"CORS request from non-allowed origin: {origin}")
        return False

    def get_cors_config(self) -> dict[str, Any]:
        """Get CORS configuration for FastAPI middleware."""
        return self._cors_config.copy()

    def add_allowed_origin(self, origin: str) -> bool:
        """
        Add new allowed origin with validation.

        Args:
            origin: Origin to add

        Returns:
            True if origin was added successfully
        """
        is_valid, reason = self.validator.validate_origin(origin)
        if not is_valid:
            logger.error(f"Cannot add invalid origin '{origin}': {reason}")
            return False

        if origin not in self._validated_origins:
            self._validated_origins.append(origin)
            self._cors_config["allow_origins"] = self._validated_origins.copy()
            logger.info(f"Added CORS origin: {origin}")

        return True

    def remove_allowed_origin(self, origin: str) -> bool:
        """
        Remove allowed origin.

        Args:
            origin: Origin to remove

        Returns:
            True if origin was removed
        """
        if origin in self._validated_origins:
            self._validated_origins.remove(origin)
            self._cors_config["allow_origins"] = self._validated_origins.copy()
            logger.info(f"Removed CORS origin: {origin}")
            return True

        return False

    def get_security_report(self) -> dict[str, Any]:
        """Get security report for CORS configuration."""
        return {
            "environment": "production",
            "total_allowed_origins": len(self._validated_origins),
            "https_only": all(
                origin.startswith("https://") for origin in self._validated_origins
            ),
            "no_wildcards": "*" not in self._validated_origins,
            "no_localhost": not any(
                "localhost" in origin for origin in self._validated_origins
            ),
            "validator_stats": self.validator.get_blocked_statistics(),
            "config": {
                "allow_credentials": self._cors_config["allow_credentials"],
                "max_age": self._cors_config["max_age"],
                "methods_count": len(self._cors_config["allow_methods"]),
                "headers_count": len(self._cors_config["allow_headers"]),
            },
        }

    def update_security_policy(self, policy: CORSSecurityPolicy) -> None:
        """Update security policy and re-validate origins."""
        self.validator.security_policy = policy
        self.validator.validation_cache.clear()

        # Re-validate all origins
        self._initialize_configuration()
        logger.info("Updated CORS security policy and re-validated origins")


def create_production_cors_middleware(
    app, production_config: ProductionConfig | None = None
) -> Any:
    """
    Create and configure CORS middleware for production.

    Args:
        app: FastAPI application instance
        production_config: Production configuration

    Returns:
        Configured CORS middleware
    """
    from fastapi.middleware.cors import CORSMiddleware

    # Create production CORS config
    cors_config = ProductionCORSConfig(production_config)

    # Add CORS middleware with production configuration
    app.add_middleware(CORSMiddleware, **cors_config.get_cors_config())

    logger.info("Production CORS middleware configured")
    logger.info(f"Allowed origins: {len(cors_config._validated_origins)}")

    return cors_config


class CORSSecurityMiddleware:
    """
    Custom CORS security middleware with advanced validation.
    """

    def __init__(self, cors_config: ProductionCORSConfig) -> None:
        """Initialize CORS security middleware."""
        self.cors_config = cors_config

    async def __call__(self, request, call_next) -> Any:
        """Process request with CORS security validation."""
        # Get origin from request
        origin = request.headers.get("origin")

        if origin and not self.cors_config.validate_request_origin(origin):
            # Block invalid origin
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=403, content={"error": "Origin not allowed by CORS policy"}
            )

        # Continue with request processing
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


def get_production_cors_config(
    production_config: ProductionConfig | None = None,
) -> ProductionCORSConfig:
    """Get production CORS configuration instance."""
    return ProductionCORSConfig(production_config)
