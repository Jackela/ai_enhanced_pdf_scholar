"""
Secrets Integration Module
Provides integration points for existing services to use the new secrets management system.
"""

import logging
from pathlib import Path
from typing import Any

from backend.api.auth.jwt_handler import JWTConfig as OldJWTConfig
from backend.core.enhanced_config import get_config
from backend.core.secrets import (
    SecretConfig,
    SecretProvider,
    SecretsManager,
    SecretType,
    get_secrets_manager,
)

logger = logging.getLogger(__name__)


class JWTSecretsAdapter:
    """
    Adapter to make JWT handler use secrets management system.
    This maintains backward compatibility while using secure storage.
    """

    def __init__(self, secrets_manager: SecretsManager | None = None) -> None:
        """Initialize JWT secrets adapter."""
        self.secrets_manager = secrets_manager or get_secrets_manager()
        self.config = get_config()

    def ensure_keys_exist(self) -> tuple[bytes, bytes]:
        """
        Ensure RSA key pair exists in secrets management.
        Replaces the file-based key storage.

        Returns:
            Tuple of (private_key_bytes, public_key_bytes)
        """
        # Try to get existing keys from secrets
        private_key = self.secrets_manager.get_secret(
            "jwt_private_key", SecretType.JWT_PRIVATE_KEY
        )
        public_key = self.secrets_manager.get_secret(
            "jwt_public_key", SecretType.JWT_PUBLIC_KEY
        )

        if private_key and public_key:
            return private_key.encode(), public_key.encode()

        # Generate new keys if not found
        logger.info("JWT keys not found in secrets, generating new RSA key pair...")

        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Generate RSA key pair
        private_key_obj = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,  # Use 4096 for production
            backend=default_backend(),
        )

        # Serialize private key
        private_key_bytes = private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        # Get public key
        public_key_obj = private_key_obj.public_key()
        public_key_bytes = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Store in secrets management
        success = self.secrets_manager.set_secret(
            key="jwt_private_key",
            value=private_key_bytes.decode(),
            secret_type=SecretType.JWT_PRIVATE_KEY,
            rotation_interval_days=365,  # Rotate yearly
            description="JWT RSA private key for token signing",
        )

        if success:
            self.secrets_manager.set_secret(
                key="jwt_public_key",
                value=public_key_bytes.decode(),
                secret_type=SecretType.JWT_PUBLIC_KEY,
                rotation_interval_days=365,
                description="JWT RSA public key for token verification",
            )
            logger.info("Successfully stored JWT keys in secrets management")
        else:
            logger.error("Failed to store JWT keys in secrets management")
            raise RuntimeError("Could not store JWT keys")

        return private_key_bytes, public_key_bytes

    def rotate_keys(self) -> bool:
        """
        Rotate JWT keys (generate new pair and update secrets).
        Old tokens will become invalid.

        Returns:
            True if successful
        """
        logger.info("Rotating JWT RSA key pair...")

        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Generate new RSA key pair
        private_key_obj = rsa.generate_private_key(
            public_exponent=65537, key_size=4096, backend=default_backend()
        )

        # Serialize keys
        private_key_bytes = private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_key_obj = private_key_obj.public_key()
        public_key_bytes = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Rotate in secrets management
        success = self.secrets_manager.rotate_secret(
            "jwt_private_key", private_key_bytes.decode()
        )

        if success:
            self.secrets_manager.rotate_secret(
                "jwt_public_key", public_key_bytes.decode()
            )
            logger.info("Successfully rotated JWT keys")
            return True
        else:
            logger.error("Failed to rotate JWT keys")
            return False


class ConfigSecretsAdapter:
    """
    Adapter to make the old Config class use secrets management.
    Provides backward compatibility for existing code.
    """

    def __init__(self, secrets_manager: SecretsManager | None = None) -> None:
        """Initialize config secrets adapter."""
        self.secrets_manager = secrets_manager or get_secrets_manager()
        self.app_config = get_config()

    @staticmethod
    def get_gemini_api_key() -> str | None:
        """
        Get Gemini API key from secrets management.
        Maintains compatibility with Config.get_gemini_api_key()
        """
        config = get_config()
        return config.get_api_key("gemini")

    @staticmethod
    def is_api_key_configured() -> bool:
        """
        Check if any API key is configured.
        Maintains compatibility with Config.is_api_key_configured()
        """
        config = get_config()
        return any(
            [config.api_keys.gemini, config.api_keys.openai, config.api_keys.anthropic]
        )

    def migrate_settings_file(self) -> bool:
        """
        Migrate settings from settings.json to secrets management.

        Returns:
            True if successful
        """
        settings_file = Path.home() / ".ai_pdf_scholar" / "settings.json"

        if not settings_file.exists():
            return True  # Nothing to migrate

        try:
            import json

            with open(settings_file) as f:
                settings = json.load(f)

            migrated = []

            # Migrate API keys
            if "gemini_api_key" in settings:
                success = self.secrets_manager.set_secret(
                    key="api_key_gemini",
                    value=settings["gemini_api_key"],
                    secret_type=SecretType.API_KEY,
                    description="Gemini API key migrated from settings.json",
                )
                if success:
                    migrated.append("gemini_api_key")
                    del settings["gemini_api_key"]

            if "openai_api_key" in settings:
                success = self.secrets_manager.set_secret(
                    key="api_key_openai",
                    value=settings["openai_api_key"],
                    secret_type=SecretType.API_KEY,
                    description="OpenAI API key migrated from settings.json",
                )
                if success:
                    migrated.append("openai_api_key")
                    del settings["openai_api_key"]

            # Write back settings without secrets
            if migrated:
                with open(settings_file, "w") as f:
                    json.dump(settings, f, indent=2)

                logger.info(f"Migrated {len(migrated)} secrets from settings.json")

            return True

        except Exception as e:
            logger.error(f"Failed to migrate settings file: {e}")
            return False


def monkey_patch_jwt_config() -> None:
    """
    Monkey-patch the JWT configuration to use secrets management.
    This allows existing code to work without modification.
    """
    adapter = JWTSecretsAdapter()

    # Replace the ensure_keys_exist method
    OldJWTConfig.ensure_keys_exist = classmethod(
        lambda cls: adapter.ensure_keys_exist()
    )

    logger.info("JWT configuration patched to use secrets management")


def monkey_patch_config() -> None:
    """
    Monkey-patch the Config class to use secrets management.
    This allows existing code to work without modification.
    """
    import sys

    # Import the old Config module
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    try:
        from config import Config

        adapter = ConfigSecretsAdapter()

        # Replace methods
        Config.get_gemini_api_key = staticmethod(adapter.get_gemini_api_key)
        Config.is_api_key_configured = staticmethod(adapter.is_api_key_configured)

        logger.info("Config class patched to use secrets management")

    except ImportError:
        logger.warning("Could not import Config class for patching")


def update_dependencies_to_use_secrets() -> Any:
    """
    Update the API dependencies to use secrets management.
    This should be called during application startup.
    """
    from backend.api import dependencies
    from backend.core.enhanced_config import get_config

    config = get_config()

    # Override the get_enhanced_rag function to use secrets

    def get_enhanced_rag_with_secrets(db=None) -> Any:
        """Enhanced RAG service using secrets management."""
        global _enhanced_rag_service

        # Import here to avoid circular imports
        from src.services.enhanced_rag_service import EnhancedRAGService

        if dependencies._enhanced_rag_service is None:
            try:
                # Get API key from secrets
                api_key = config.get_api_key("gemini")
                if not api_key:
                    # Try other providers
                    api_key = config.get_api_key("openai")

                if not api_key:
                    logger.warning("No AI API key configured in secrets")
                    return None

                # Initialize enhanced RAG service
                vector_storage_dir = Path.home() / ".ai_pdf_scholar" / "vector_indexes"
                dependencies._enhanced_rag_service = EnhancedRAGService(
                    api_key=api_key,
                    db_connection=db,
                    vector_storage_dir=str(vector_storage_dir),
                )
                logger.info("Enhanced RAG service initialized with secrets")

            except Exception as e:
                logger.error(f"Failed to initialize enhanced RAG service: {e}")
                return None

        return dependencies._enhanced_rag_service

    # Replace the function
    dependencies.get_enhanced_rag = get_enhanced_rag_with_secrets

    logger.info("Dependencies updated to use secrets management")


def initialize_secrets_integration(
    provider: SecretProvider | None = None,
    auto_migrate: bool = True,
    monkey_patch: bool = True,
) -> bool:
    """
    Initialize secrets management integration with existing system.

    Args:
        provider: Secret provider to use (defaults to environment-based)
        auto_migrate: Automatically migrate existing secrets
        monkey_patch: Apply monkey patches for backward compatibility

    Returns:
        True if successful
    """
    try:
        # Initialize secrets manager
        if provider:
            config = SecretConfig(primary_provider=provider)
            from backend.core.secrets import initialize_secrets_manager

            initialize_secrets_manager(config)

        # Auto-migrate if requested
        if auto_migrate:
            from backend.core.secrets_migration import SecretsMigration

            migration = SecretsMigration(dry_run=False)
            migration.initialize_manager(provider or SecretProvider.LOCAL_ENCRYPTED)

            existing_secrets = migration.find_existing_secrets()
            if existing_secrets:
                logger.info(f"Found {len(existing_secrets)} secrets to migrate")
                migration.migrate_secrets(existing_secrets)

        # Apply monkey patches if requested
        if monkey_patch:
            monkey_patch_jwt_config()
            monkey_patch_config()
            update_dependencies_to_use_secrets()

        # Validate configuration
        config = get_config()
        errors = config.validate_secrets()

        if errors:
            logger.warning(f"Configuration validation warnings: {errors}")

        logger.info("Secrets management integration initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize secrets integration: {e}")
        return False


def check_and_rotate_secrets() -> dict[str, bool]:
    """
    Check for secrets that need rotation and rotate them.

    Returns:
        Dictionary of rotated secrets and their status
    """
    secrets_manager = get_secrets_manager()
    results = {}

    # Check which secrets need rotation
    secrets_to_rotate = secrets_manager.check_rotation_needed()

    for key, metadata in secrets_to_rotate:
        logger.info(
            f"Secret {key} needs rotation (last rotated: {metadata.last_rotated})"
        )

        # Handle special cases
        if key == "jwt_private_key":
            # JWT keys need special handling
            adapter = JWTSecretsAdapter(secrets_manager)
            results[key] = adapter.rotate_keys()
        else:
            # For other secrets, generate new values
            # This would typically involve calling the service to generate new keys
            # For now, we'll log a warning
            logger.warning(f"Automatic rotation for {key} not implemented yet")
            results[key] = False

    return results


def get_secret_health_status() -> dict[str, Any]:
    """
    Get comprehensive health status of secrets management.

    Returns:
        Health status dictionary
    """
    secrets_manager = get_secrets_manager()
    config = get_config()

    health = {
        "providers": secrets_manager.health_check(),
        "configuration": {
            "environment": config.environment.value,
            "primary_provider": secrets_manager.config.primary_provider.value,
            "fallback_providers": [
                p.value for p in secrets_manager.config.fallback_providers
            ],
        },
        "secrets": {
            "total": len(secrets_manager.list_secrets()),
            "api_keys_configured": config.api_keys.model_dump(
                exclude_unset=True, exclude_none=True
            ),
            "jwt_configured": bool(config.jwt.private_key and config.jwt.public_key),
            "database_configured": bool(config.database.url or config.database.host),
        },
        "validation": config.validate_secrets(),
        "rotation_needed": len(secrets_manager.check_rotation_needed()),
    }

    return health
