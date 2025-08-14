"""
Enhanced Configuration Module
Integrates with the secrets management system for secure configuration.
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, SecretStr, field_validator

from backend.core.secrets import (
    SecretType,
    SecretsManager,
    get_secrets_manager,
)

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Application environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class DatabaseConfig(BaseModel):
    """Database configuration."""
    url: Optional[SecretStr] = None
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    database: str = Field(default="ai_pdf_scholar")
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    pool_timeout: int = Field(default=30)
    echo: bool = Field(default=False)

    @classmethod
    def from_secrets(cls, secrets_manager: SecretsManager) -> "DatabaseConfig":
        """Create database config from secrets manager."""
        config = {}

        # Try to get full database URL first
        if db_url := secrets_manager.get_database_url():
            config["url"] = SecretStr(db_url)
        else:
            # Build from components
            if host := secrets_manager.get_secret("db_host"):
                config["host"] = host
            if port := secrets_manager.get_secret("db_port"):
                config["port"] = int(port)
            if database := secrets_manager.get_secret("db_name"):
                config["database"] = database
            if username := secrets_manager.get_secret("db_username"):
                config["username"] = username
            if password := secrets_manager.get_secret("db_password"):
                config["password"] = SecretStr(password)

        return cls(**config)

    def get_connection_string(self) -> str:
        """Get database connection string."""
        if self.url:
            return self.url.get_secret_value()

        # Build connection string
        if self.username and self.password:
            auth = f"{self.username}:{self.password.get_secret_value()}"
        elif self.username:
            auth = self.username
        else:
            auth = ""

        if auth:
            return f"postgresql://{auth}@{self.host}:{self.port}/{self.database}"
        else:
            return f"postgresql://{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseModel):
    """Redis configuration."""
    url: Optional[SecretStr] = None
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    database: int = Field(default=0)
    password: Optional[SecretStr] = None
    ssl: bool = Field(default=False)
    connection_pool_max_connections: int = Field(default=50)

    @classmethod
    def from_secrets(cls, secrets_manager: SecretsManager) -> "RedisConfig":
        """Create Redis config from secrets manager."""
        config = {}

        # Try to get full Redis URL first
        if redis_url := secrets_manager.get_redis_url():
            config["url"] = SecretStr(redis_url)
        else:
            # Build from components
            if host := secrets_manager.get_secret("redis_host"):
                config["host"] = host
            if port := secrets_manager.get_secret("redis_port"):
                config["port"] = int(port)
            if password := secrets_manager.get_secret("redis_password"):
                config["password"] = SecretStr(password)
            if database := secrets_manager.get_secret("redis_database"):
                config["database"] = int(database)

        return cls(**config)

    def get_connection_string(self) -> str:
        """Get Redis connection string."""
        if self.url:
            return self.url.get_secret_value()

        # Build connection string
        scheme = "rediss" if self.ssl else "redis"

        if self.password:
            auth = f":{self.password.get_secret_value()}@"
        else:
            auth = ""

        return f"{scheme}://{auth}{self.host}:{self.port}/{self.database}"


class JWTConfig(BaseModel):
    """JWT configuration."""
    private_key: Optional[SecretStr] = None
    public_key: Optional[SecretStr] = None
    algorithm: str = Field(default="RS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)
    issuer: str = Field(default="ai-pdf-scholar")
    audience: str = Field(default="ai-pdf-scholar-api")

    @classmethod
    def from_secrets(cls, secrets_manager: SecretsManager) -> "JWTConfig":
        """Create JWT config from secrets manager."""
        config = {}

        private_key, public_key = secrets_manager.get_jwt_keys()
        if private_key:
            config["private_key"] = SecretStr(private_key)
        if public_key:
            config["public_key"] = SecretStr(public_key)

        # Get other JWT settings
        if algorithm := secrets_manager.get_secret("jwt_algorithm"):
            config["algorithm"] = algorithm
        if expire_minutes := secrets_manager.get_secret("jwt_access_expire_minutes"):
            config["access_token_expire_minutes"] = int(expire_minutes)
        if expire_days := secrets_manager.get_secret("jwt_refresh_expire_days"):
            config["refresh_token_expire_days"] = int(expire_days)

        return cls(**config)


class APIKeysConfig(BaseModel):
    """API keys configuration."""
    gemini: Optional[SecretStr] = None
    openai: Optional[SecretStr] = None
    anthropic: Optional[SecretStr] = None
    cohere: Optional[SecretStr] = None
    huggingface: Optional[SecretStr] = None

    @classmethod
    def from_secrets(cls, secrets_manager: SecretsManager) -> "APIKeysConfig":
        """Create API keys config from secrets manager."""
        config = {}

        # Get all API keys
        api_services = ['gemini', 'openai', 'anthropic', 'cohere', 'huggingface']
        for service in api_services:
            if api_key := secrets_manager.get_api_key(service):
                config[service] = SecretStr(api_key)

        return cls(**config)

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a specific service."""
        key = getattr(self, service, None)
        return key.get_secret_value() if key else None


class SMTPConfig(BaseModel):
    """SMTP configuration for email."""
    host: str = Field(default="localhost")
    port: int = Field(default=587)
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    use_tls: bool = Field(default=True)
    use_ssl: bool = Field(default=False)
    from_email: str = Field(default="noreply@ai-pdf-scholar.com")
    from_name: str = Field(default="AI PDF Scholar")

    @classmethod
    def from_secrets(cls, secrets_manager: SecretsManager) -> "SMTPConfig":
        """Create SMTP config from secrets manager."""
        config = {}

        # Get SMTP settings
        if host := secrets_manager.get_secret("smtp_host"):
            config["host"] = host
        if port := secrets_manager.get_secret("smtp_port"):
            config["port"] = int(port)

        username, password = secrets_manager.get_smtp_credentials()
        if username:
            config["username"] = username
        if password:
            config["password"] = SecretStr(password)

        if use_tls := secrets_manager.get_secret("smtp_use_tls"):
            config["use_tls"] = use_tls.lower() == "true"
        if use_ssl := secrets_manager.get_secret("smtp_use_ssl"):
            config["use_ssl"] = use_ssl.lower() == "true"

        if from_email := secrets_manager.get_secret("smtp_from_email"):
            config["from_email"] = from_email
        if from_name := secrets_manager.get_secret("smtp_from_name"):
            config["from_name"] = from_name

        return cls(**config)


class SecurityConfig(BaseModel):
    """Security configuration."""
    secret_key: Optional[SecretStr] = None
    encryption_key: Optional[SecretStr] = None
    allowed_hosts: List[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"])
    csrf_enabled: bool = Field(default=True)
    csrf_secret: Optional[SecretStr] = None

    @classmethod
    def from_secrets(cls, secrets_manager: SecretsManager, environment: Environment) -> "SecurityConfig":
        """Create security config from secrets manager."""
        config = {}

        # Get security keys
        if secret_key := secrets_manager.get_secret("app_secret_key"):
            config["secret_key"] = SecretStr(secret_key)
        if encryption_key := secrets_manager.get_secret("encryption_key"):
            config["encryption_key"] = SecretStr(encryption_key)
        if csrf_secret := secrets_manager.get_secret("csrf_secret"):
            config["csrf_secret"] = SecretStr(csrf_secret)

        # Environment-specific settings
        if environment == Environment.PRODUCTION:
            config["allowed_hosts"] = ["api.ai-pdf-scholar.com", "ai-pdf-scholar.com"]
            config["cors_origins"] = ["https://ai-pdf-scholar.com"]
        elif environment == Environment.STAGING:
            config["allowed_hosts"] = ["staging-api.ai-pdf-scholar.com", "staging.ai-pdf-scholar.com"]
            config["cors_origins"] = ["https://staging.ai-pdf-scholar.com"]

        # Get allowed hosts from secrets
        if hosts := secrets_manager.get_secret("allowed_hosts"):
            config["allowed_hosts"] = hosts.split(",")
        if origins := secrets_manager.get_secret("cors_origins"):
            config["cors_origins"] = origins.split(",")

        return cls(**config)


class ApplicationConfig(BaseModel):
    """Main application configuration."""
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    testing: bool = Field(default=False)

    # Sub-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: Optional[RedisConfig] = None
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
    smtp: Optional[SMTPConfig] = None
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # Application settings
    app_name: str = Field(default="AI Enhanced PDF Scholar")
    app_version: str = Field(default="2.1.0")
    api_prefix: str = Field(default="/api")
    docs_url: str = Field(default="/api/docs")
    redoc_url: str = Field(default="/api/redoc")

    # File handling
    max_file_size_mb: int = Field(default=100)
    allowed_file_types: List[str] = Field(default_factory=lambda: [".pdf"])
    upload_directory: Path = Field(default=Path.home() / ".ai_pdf_scholar" / "uploads")
    documents_directory: Path = Field(default=Path.home() / ".ai_pdf_scholar" / "documents")

    # Performance settings
    workers: int = Field(default=4)
    worker_class: str = Field(default="uvicorn.workers.UvicornWorker")
    worker_connections: int = Field(default=1000)
    keepalive: int = Field(default=5)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_file: Optional[Path] = None

    @field_validator('environment')
    def validate_environment(cls, v):
        if isinstance(v, str):
            return Environment(v)
        return v

    @classmethod
    def from_env(cls, secrets_manager: Optional[SecretsManager] = None) -> "ApplicationConfig":
        """Create configuration from environment and secrets."""
        if not secrets_manager:
            secrets_manager = get_secrets_manager()

        # Determine environment
        env_str = os.getenv("ENVIRONMENT", "development")
        environment = Environment(env_str)

        # Base configuration
        config = {
            "environment": environment,
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "testing": os.getenv("TESTING", "false").lower() == "true",
        }

        # Load sub-configurations from secrets
        config["database"] = DatabaseConfig.from_secrets(secrets_manager)
        config["jwt"] = JWTConfig.from_secrets(secrets_manager)
        config["api_keys"] = APIKeysConfig.from_secrets(secrets_manager)
        config["security"] = SecurityConfig.from_secrets(secrets_manager, environment)

        # Optional configurations
        if secrets_manager.get_redis_url() or secrets_manager.get_secret("redis_host"):
            config["redis"] = RedisConfig.from_secrets(secrets_manager)

        if secrets_manager.get_secret("smtp_host"):
            config["smtp"] = SMTPConfig.from_secrets(secrets_manager)

        # Application settings from environment
        if app_name := os.getenv("APP_NAME"):
            config["app_name"] = app_name
        if app_version := os.getenv("APP_VERSION"):
            config["app_version"] = app_version

        # File handling
        if max_size := os.getenv("MAX_FILE_SIZE_MB"):
            config["max_file_size_mb"] = int(max_size)
        if upload_dir := os.getenv("UPLOAD_DIRECTORY"):
            config["upload_directory"] = Path(upload_dir)
        if docs_dir := os.getenv("DOCUMENTS_DIRECTORY"):
            config["documents_directory"] = Path(docs_dir)

        # Performance settings
        if workers := os.getenv("WORKERS"):
            config["workers"] = int(workers)
        if worker_class := os.getenv("WORKER_CLASS"):
            config["worker_class"] = worker_class

        # Logging
        if log_level := os.getenv("LOG_LEVEL"):
            config["log_level"] = log_level
        if log_file := os.getenv("LOG_FILE"):
            config["log_file"] = Path(log_file)

        return cls(**config)

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT

    def get_database_url(self) -> str:
        """Get database connection URL."""
        return self.database.get_connection_string()

    def get_redis_url(self) -> Optional[str]:
        """Get Redis connection URL."""
        return self.redis.get_connection_string() if self.redis else None

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service."""
        return self.api_keys.get_api_key(service)

    def validate_secrets(self) -> List[str]:
        """
        Validate that required secrets are configured.

        Returns:
            List of validation errors
        """
        errors = []

        # Check database configuration
        if not self.database.url and not (self.database.host and self.database.database):
            errors.append("Database configuration is missing")

        # Check JWT keys in production
        if self.is_production():
            if not self.jwt.private_key or not self.jwt.public_key:
                errors.append("JWT keys are required in production")

            if not self.security.secret_key:
                errors.append("Secret key is required in production")

        # Check at least one API key is configured
        if not any([
            self.api_keys.gemini,
            self.api_keys.openai,
            self.api_keys.anthropic
        ]):
            errors.append("At least one AI API key must be configured")

        return errors

    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Args:
            include_secrets: Whether to include secret values (use with caution!)

        Returns:
            Configuration dictionary
        """
        data = self.model_dump(mode='json')

        if not include_secrets:
            # Redact secret values
            def redact_secrets(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key in ['password', 'secret_key', 'private_key', 'api_key', 'token']:
                            obj[key] = "***REDACTED***"
                        elif isinstance(value, dict):
                            redact_secrets(value)
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    redact_secrets(item)
                return obj

            redact_secrets(data)

        return data


# Global configuration instance
_config: Optional[ApplicationConfig] = None


def get_config() -> ApplicationConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = ApplicationConfig.from_env()
    return _config


def initialize_config(
    secrets_manager: Optional[SecretsManager] = None,
    override_config: Optional[Dict[str, Any]] = None
) -> ApplicationConfig:
    """
    Initialize the global configuration.

    Args:
        secrets_manager: Optional secrets manager instance
        override_config: Optional configuration overrides

    Returns:
        Initialized configuration
    """
    global _config

    # Create base config from environment and secrets
    _config = ApplicationConfig.from_env(secrets_manager)

    # Apply overrides if provided
    if override_config:
        config_dict = _config.model_dump()
        config_dict.update(override_config)
        _config = ApplicationConfig(**config_dict)

    # Validate configuration
    errors = _config.validate_secrets()
    if errors:
        logger.warning(f"Configuration validation warnings: {errors}")

    return _config


def reload_config() -> ApplicationConfig:
    """Reload configuration from environment and secrets."""
    global _config
    _config = ApplicationConfig.from_env()
    return _config