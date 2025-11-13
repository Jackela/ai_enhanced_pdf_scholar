"""
Unified Application Configuration

Provides a centralized, type-safe configuration system that replaces
scattered configuration files with a single source of truth.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from .environment import Environment, get_current_environment
from .validation import ConfigValidationError, ConfigValidator, SecurityValidator

if TYPE_CHECKING:
    from .caching_config import CachingConfig

logger = logging.getLogger(__name__)


@dataclass
class CORSConfig:
    """CORS configuration settings."""

    allow_origins: list[str] = field(default_factory=list)
    allow_credentials: bool = True
    allow_methods: list[str] = field(
        default_factory=lambda: [
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
            "HEAD",
            "PATCH",
        ]
    )
    allow_headers: list[str] = field(
        default_factory=lambda: [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token",
        ]
    )
    expose_headers: list[str] = field(
        default_factory=lambda: ["X-Total-Count", "X-Request-ID"]
    )
    max_age: int = 3600

    def validate(self, environment: Environment) -> list[str]:
        """Validate CORS configuration for current environment."""
        issues = []

        if environment.is_production():
            if "*" in self.allow_origins:
                issues.append("Wildcard origins not allowed in production")

            for origin in self.allow_origins:
                if not ConfigValidator.validate_cors_origin(origin):
                    issues.append(f"Invalid CORS origin format: {origin}")

                if "localhost" in origin.lower() or "127.0.0.1" in origin:
                    issues.append(f"Development origin in production: {origin}")

                if origin.startswith("http://"):
                    issues.append(f"Insecure HTTP origin in production: {origin}")

        return issues


@dataclass
class RateLimitRule:
    """Rate limit rule configuration."""

    requests: int
    window_seconds: int


@dataclass
class RateLimitConfig:
    """Rate limiting configuration settings."""

    enabled: bool = True
    default_limit: RateLimitRule = field(default_factory=lambda: RateLimitRule(60, 60))
    endpoint_limits: dict[str, RateLimitRule] = field(default_factory=dict)
    global_ip_limit: RateLimitRule = field(
        default_factory=lambda: RateLimitRule(500, 3600)
    )
    redis_url: str | None = None
    redis_key_prefix: str = "rl:"
    bypass_ips: set[str] = field(default_factory=set)
    bypass_user_agents: set[str] = field(
        default_factory=lambda: {"monitor", "health-check"}
    )
    include_headers: bool = True
    block_duration: int = 300

    def validate(self, environment: Environment) -> list[str]:
        """Validate rate limiting configuration."""
        issues = []

        if self.redis_url and not ConfigValidator.validate_redis_url(self.redis_url):
            issues.append("Invalid Redis URL format")

        if environment.is_production() and not self.enabled:
            issues.append("Rate limiting should be enabled in production")

        # Validate rate limits are reasonable
        if self.default_limit.requests > 10000:
            issues.append("Default rate limit seems too high")

        return issues


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    url: str = "sqlite:///./pdf_scholar.db"
    pool_size: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False

    def validate(self, environment: Environment) -> list[str]:
        """Validate database configuration."""
        issues = []

        if environment.is_production() and self.url.startswith("sqlite"):
            issues.append("Production should use PostgreSQL, not SQLite")

        if not ConfigValidator.validate_positive_int(self.pool_size):
            issues.append("Invalid database pool size")

        return issues


@dataclass
class SecurityConfig:
    """Security configuration settings."""

    enable_https: bool = True
    secret_key: str | None = None
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    password_hash_rounds: int = 12
    enable_csrf_protection: bool = True

    def validate(self, environment: Environment) -> list[str]:
        """Validate security configuration."""
        issues = []

        if environment.is_production():
            if not self.enable_https:
                issues.append("HTTPS must be enabled in production")

            if self.secret_key and not ConfigValidator.validate_secret_key(
                self.secret_key
            ):
                issues.append("Weak secret key detected")

        if self.password_hash_rounds < 10:
            issues.append("Password hash rounds too low")

        return issues


@dataclass
class APIKeysConfig:
    """API keys configuration."""

    google_api_key: str | None = None
    openai_api_key: str | None = None

    def validate(self, environment: Environment) -> list[str]:
        """Validate API keys."""
        issues = []

        if self.google_api_key and not ConfigValidator.validate_api_key(
            self.google_api_key, "google"
        ):
            issues.append("Invalid Google API key format")

        if self.openai_api_key and not ConfigValidator.validate_api_key(
            self.openai_api_key, "openai"
        ):
            issues.append("Invalid OpenAI API key format")

        return issues


@dataclass
class FileStorageConfig:
    """File storage configuration."""

    base_path: str = "./documents"
    max_file_size_mb: int = 100
    allowed_extensions: set[str] = field(
        default_factory=lambda: {".pdf", ".txt", ".docx"}
    )
    vector_storage_dir: str = "./vector_indexes"

    def validate(self, environment: Environment) -> list[str]:
        """Validate file storage configuration."""
        issues = []

        if not ConfigValidator.validate_positive_int(self.max_file_size_mb):
            issues.append("Invalid max file size")

        # Validate paths are reasonable
        base_path = Path(self.base_path)

        if base_path.is_absolute() and environment.is_development():
            issues.append("Consider using relative paths in development")

        return issues


@dataclass
class PreviewConfig:
    """Document preview/thumbnail configuration."""

    enabled: bool = True
    cache_dir: str = str(Path.home() / ".ai_pdf_scholar" / "previews")
    max_width: int = 1024
    min_width: int = 200
    thumbnail_width: int = 256
    max_page_number: int = 500
    cache_ttl_seconds: int = 3600

    def validate(self, environment: Environment) -> list[str]:
        """Validate preview configuration."""
        issues: list[str] = []

        if self.max_width <= 0 or self.min_width <= 0:
            issues.append("preview: Width limits must be positive")
        if self.min_width > self.max_width:
            issues.append("preview: min_width cannot exceed max_width")
        if self.thumbnail_width <= 0 or self.thumbnail_width > self.max_width:
            issues.append("preview: thumbnail_width must be within configured bounds")
        if self.max_page_number <= 0:
            issues.append("preview: max_page_number must be positive")
        if self.cache_ttl_seconds <= 0:
            issues.append("preview: cache_ttl_seconds must be positive")

        cache_path = Path(self.cache_dir)
        if cache_path.is_absolute() and environment.is_development():
            issues.append(
                "preview: consider using relative preview cache paths in development"
            )

        return issues


@dataclass
class LoggingConfig:
    """Logging configuration settings."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str | None = None
    max_file_size_mb: int = 10
    backup_count: int = 5

    def validate(self, environment: Environment) -> list[str]:
        """Validate logging configuration."""
        issues = []

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.level.upper() not in valid_levels:
            issues.append(f"Invalid logging level: {self.level}")

        if environment.is_production() and self.level.upper() == "DEBUG":
            issues.append("Debug logging should not be used in production")

        return issues


@dataclass
class ApplicationConfig:
    """
    Unified application configuration.

    Centralizes all configuration settings in a single, type-safe class
    that replaces scattered configuration files.
    """

    environment: Environment
    cors: CORSConfig = field(default_factory=CORSConfig)
    rate_limiting: RateLimitConfig = field(default_factory=RateLimitConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    api_keys: APIKeysConfig = field(default_factory=APIKeysConfig)
    file_storage: FileStorageConfig = field(default_factory=FileStorageConfig)
    preview: PreviewConfig = field(default_factory=PreviewConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Caching configuration
    caching: Optional["CachingConfig"] = None

    # Application-specific settings
    app_name: str = "AI Enhanced PDF Scholar"
    app_version: str = "2.1.0"
    debug: bool = False

    @classmethod
    def from_environment(cls) -> "ApplicationConfig":
        """Create configuration from environment variables."""
        environment = get_current_environment()

        config = cls(environment=environment)

        # Load environment-specific configurations
        config._load_cors_config()
        config._load_rate_limiting_config()
        config._load_database_config()
        config._load_security_config()
        config._load_api_keys_config()
        config._load_file_storage_config()
        config._load_preview_config()
        config._load_logging_config()
        config._load_caching_config()
        config._load_app_config()

        return config

    def _load_cors_config(self) -> None:
        """Load CORS configuration from environment."""
        origins_str = os.getenv("CORS_ORIGINS", "")

        if self.environment.is_development():
            default_origins = (
                "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000"
            )
            origins_str = origins_str or default_origins
        elif self.environment.is_testing():
            origins_str = origins_str or "http://localhost:3000"

        # Parse origins
        origins = []
        if origins_str:
            origins = [
                origin.strip() for origin in origins_str.split(",") if origin.strip()
            ]

        self.cors = CORSConfig(
            allow_origins=origins,
            allow_credentials=not self.environment.is_testing(),
            max_age=86400 if self.environment.is_development() else 3600,
        )

    def _load_rate_limiting_config(self) -> None:
        """Load rate limiting configuration from environment."""
        enabled = os.getenv("RATE_LIMIT_DISABLE", "false").lower() != "true"
        redis_url = os.getenv("REDIS_URL")

        if self.environment.is_production():
            default_limit = RateLimitRule(60, 60)
            global_limit = RateLimitRule(500, 3600)
            endpoint_limits = {
                "/api/documents/upload": RateLimitRule(5, 60),
                "/api/rag/query": RateLimitRule(30, 60),
                "/api/documents": RateLimitRule(100, 60),
            }
            bypass_ips = set()

        elif self.environment.is_testing():
            default_limit = RateLimitRule(6000, 60)
            global_limit = RateLimitRule(50000, 3600)
            endpoint_limits = {}
            bypass_ips = {"127.0.0.1", "::1", "localhost", "testclient"}

        else:  # development
            default_limit = RateLimitRule(600, 60)
            global_limit = RateLimitRule(5000, 3600)
            endpoint_limits = {
                "/api/documents/upload": RateLimitRule(50, 60),
                "/api/rag/query": RateLimitRule(300, 60),
            }
            bypass_ips = {"127.0.0.1", "::1", "localhost"}

        self.rate_limiting = RateLimitConfig(
            enabled=enabled,
            default_limit=default_limit,
            endpoint_limits=endpoint_limits,
            global_ip_limit=global_limit,
            redis_url=redis_url,
            redis_key_prefix=f"rl:{self.environment.value}:",
            bypass_ips=bypass_ips,
            block_duration=300 if self.environment.is_production() else 60,
        )

    def _load_database_config(self) -> None:
        """Load database configuration from environment."""
        db_url = os.getenv("DATABASE_URL", "sqlite:///./pdf_scholar.db")

        # Environment-specific defaults
        if self.environment.is_testing():
            db_url = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")

        self.database = DatabaseConfig(
            url=db_url,
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
        )

    def _load_security_config(self) -> None:
        """Load security configuration from environment."""
        self.security = SecurityConfig(
            enable_https=os.getenv("ENABLE_HTTPS", "true").lower() == "true",
            secret_key=os.getenv("SECRET_KEY"),
            jwt_access_token_expire_minutes=int(
                os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "15")
            ),
            jwt_refresh_token_expire_days=int(
                os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7")
            ),
            password_hash_rounds=int(os.getenv("PASSWORD_HASH_ROUNDS", "12")),
            enable_csrf_protection=not self.environment.is_testing(),
        )

    def _load_api_keys_config(self) -> None:
        """Load API keys configuration from environment."""
        self.api_keys = APIKeysConfig(
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

    def _load_file_storage_config(self) -> None:
        """Load file storage configuration from environment."""
        self.file_storage = FileStorageConfig(
            base_path=os.getenv("DOCUMENTS_PATH", "./documents"),
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "100")),
            vector_storage_dir=os.getenv("VECTOR_STORAGE_DIR", "./vector_indexes"),
        )

    def _load_preview_config(self) -> None:
        """Load document preview configuration."""
        cache_dir = os.getenv(
            "PREVIEW_CACHE_DIR", str(Path.home() / ".ai_pdf_scholar" / "previews")
        )
        self.preview = PreviewConfig(
            enabled=os.getenv("PREVIEWS_ENABLED", "true").lower() == "true",
            cache_dir=cache_dir,
            max_width=int(os.getenv("PREVIEW_MAX_WIDTH", "1024")),
            min_width=int(os.getenv("PREVIEW_MIN_WIDTH", "200")),
            thumbnail_width=int(os.getenv("PREVIEW_THUMBNAIL_WIDTH", "256")),
            max_page_number=int(os.getenv("PREVIEW_MAX_PAGE_NUMBER", "500")),
            cache_ttl_seconds=int(os.getenv("PREVIEW_CACHE_TTL_SECONDS", "3600")),
        )

    def _load_logging_config(self) -> None:
        """Load logging configuration from environment."""
        level = "DEBUG" if self.environment.is_development() else "INFO"
        if self.environment.is_testing():
            level = "WARNING"

        self.logging = LoggingConfig(
            level=os.getenv("LOG_LEVEL", level),
            file_path=os.getenv("LOG_FILE_PATH"),
            max_file_size_mb=int(os.getenv("LOG_MAX_SIZE_MB", "10")),
        )

    def _load_caching_config(self) -> None:
        """Load caching configuration from environment."""
        try:
            from .caching_config import get_caching_config

            self.caching = get_caching_config(self.environment)
            logger.info("Caching configuration loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load caching configuration: {e}")
            self.caching = None

    def _load_app_config(self) -> None:
        """Load application-specific configuration."""
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        if self.environment.is_development():
            self.debug = self.debug or True  # Default to True in development

    def validate(self) -> None:
        """
        Validate entire configuration and raise errors for critical issues.

        Raises:
            ConfigValidationError: If critical configuration issues are found
        """
        all_issues = []

        # Validate each configuration section
        for config_name, config_obj in [
            ("cors", self.cors),
            ("rate_limiting", self.rate_limiting),
            ("database", self.database),
            ("security", self.security),
            ("api_keys", self.api_keys),
            ("file_storage", self.file_storage),
            ("preview", self.preview),
            ("logging", self.logging),
            ("caching", self.caching),
        ]:
            if config_obj is not None and hasattr(config_obj, "validate"):
                issues = config_obj.validate(self.environment)
                for issue in issues:
                    all_issues.append(f"{config_name}: {issue}")

        # Production security validation
        if self.environment.is_production():
            config_dict = self.to_dict()
            security_issues = SecurityValidator.validate_production_security(
                config_dict, self.environment.value
            )
            all_issues.extend(security_issues)

            secret_issues = SecurityValidator.validate_secret_management(config_dict)
            all_issues.extend(secret_issues)

        # Log warnings for non-critical issues
        if all_issues:
            for issue in all_issues:
                logger.warning(f"Configuration issue: {issue}")

        # Raise error for critical issues in production
        critical_keywords = ["must", "required", "invalid", "not allowed"]
        critical_issues = [
            issue
            for issue in all_issues
            if any(keyword in issue.lower() for keyword in critical_keywords)
        ]

        if critical_issues and self.environment.requires_strict_security():
            raise ConfigValidationError(
                "Critical configuration issues found", issues=critical_issues
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "environment": self.environment.value,
            "cors": {
                "allow_origins": self.cors.allow_origins,
                "allow_credentials": self.cors.allow_credentials,
                "max_age": self.cors.max_age,
            },
            "rate_limiting": {
                "enabled": self.rate_limiting.enabled,
                "default_limit": self.rate_limiting.default_limit.requests,
            },
            "database": {
                "url": "***" if "password" in self.database.url else self.database.url,
                "pool_size": self.database.pool_size,
            },
            "security": {
                "enable_https": self.security.enable_https,
                "jwt_access_expire": self.security.jwt_access_token_expire_minutes,
            },
            "api_keys": {
                "google_configured": bool(self.api_keys.google_api_key),
                "openai_configured": bool(self.api_keys.openai_api_key),
            },
            "preview": {
                "enabled": self.preview.enabled,
                "cache_dir": self.preview.cache_dir,
                "max_width": self.preview.max_width,
                "thumbnail_width": self.preview.thumbnail_width,
                "cache_ttl_seconds": self.preview.cache_ttl_seconds,
            },
            "caching": self.caching.to_dict() if self.caching else {"enabled": False},
            "app": {
                "name": self.app_name,
                "version": self.app_version,
                "debug": self.debug,
            },
        }


# Global configuration instance
_config: ApplicationConfig | None = None


def get_application_config(reload: bool = False) -> ApplicationConfig:
    """
    Get the global application configuration instance.

    Args:
        reload: If True, reload configuration from environment

    Returns:
        ApplicationConfig instance
    """
    global _config

    if _config is None or reload:
        _config = ApplicationConfig.from_environment()
        _config.validate()
        logger.info(f"Configuration loaded for {_config.environment.value} environment")

    return _config


def configure_logging(config: ApplicationConfig | None = None) -> None:
    """
    Configure logging based on application configuration.

    Args:
        config: Optional configuration instance
    """
    if config is None:
        config = get_application_config()

    log_config = config.logging

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_config.level.upper()),
        format=log_config.format,
        filename=log_config.file_path,
    )

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)

    logger.info(
        f"Logging configured: level={log_config.level}, file={log_config.file_path}"
    )


def reset_configuration() -> None:
    """Reset global configuration (useful for testing)."""
    global _config
    _config = None
