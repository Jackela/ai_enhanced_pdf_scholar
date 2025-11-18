"""
Secrets Migration Script
Migrates existing secrets from config files and environment to the new secrets management system.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from backend.core.secrets import (
    SecretConfig,
    SecretProvider,
    SecretsManager,
    SecretType,
    initialize_secrets_manager,
)

logger = logging.getLogger(__name__)


class SecretsMigration:
    """Handles migration of secrets to the new management system."""

    def __init__(self, dry_run: bool = True):
        """
        Initialize migration tool.

        Args:
            dry_run: If True, only simulate migration without making changes
        """
        self.dry_run = dry_run
        self.secrets_manager = None
        self.migration_report = {
            "migrated": [],
            "failed": [],
            "skipped": [],
            "warnings": [],
        }

    def initialize_manager(
        self, provider: SecretProvider = SecretProvider.LOCAL_ENCRYPTED
    ) -> SecretsManager:
        """Initialize the secrets manager with specified provider."""
        config = SecretConfig(
            primary_provider=provider,
            environment=os.getenv("ENVIRONMENT", "development"),
        )
        self.secrets_manager = initialize_secrets_manager(config)
        return self.secrets_manager

    def find_existing_secrets(self) -> dict[str, tuple[str, str]]:
        """
        Find secrets in existing configuration files and environment.

        Returns:
            Dictionary of secret_key -> (value, source)
        """
        secrets = {}

        # Check environment variables
        env_secrets = self._find_env_secrets()
        secrets.update(env_secrets)

        # Check config files
        config_secrets = self._find_config_secrets()
        secrets.update(config_secrets)

        # Check JWT keys
        jwt_secrets = self._find_jwt_keys()
        secrets.update(jwt_secrets)

        # Check settings.json
        settings_secrets = self._find_settings_secrets()
        secrets.update(settings_secrets)

        return secrets

    def _find_env_secrets(self) -> dict[str, tuple[str, str]]:
        """Find secrets in environment variables."""
        secrets = {}

        # Known secret environment variables
        secret_env_vars = [
            ("GEMINI_API_KEY", "api_key_gemini", SecretType.API_KEY),
            ("OPENAI_API_KEY", "api_key_openai", SecretType.API_KEY),
            ("DATABASE_URL", "database_url", SecretType.DATABASE_URL),
            ("REDIS_URL", "redis_url", SecretType.REDIS_URL),
            ("SMTP_PASSWORD", "smtp_password", SecretType.SMTP_PASSWORD),
            ("SECRET_KEY", "app_secret_key", SecretType.SIGNING_KEY),
            ("JWT_SECRET", "jwt_secret", SecretType.SIGNING_KEY),
            ("ENCRYPTION_KEY", "encryption_key", SecretType.ENCRYPTION_KEY),
            ("VAULT_TOKEN", "vault_token", SecretType.API_KEY),
            ("AWS_ACCESS_KEY_ID", "aws_access_key", SecretType.API_KEY),
            ("AWS_SECRET_ACCESS_KEY", "aws_secret_key", SecretType.API_KEY),
        ]

        for env_var, secret_key, secret_type in secret_env_vars:
            value = os.getenv(env_var)
            if value:
                secrets[secret_key] = (value, f"env:{env_var}")
                logger.info(f"Found secret in environment: {env_var}")

        return secrets

    def _find_config_secrets(self) -> dict[str, tuple[str, str]]:
        """Find secrets in config.py file."""
        secrets = {}

        try:
            # Import config module
            import sys

            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from config import Config

            # Check for Gemini API key
            gemini_key = Config.get_gemini_api_key()
            if gemini_key:
                secrets["api_key_gemini"] = (
                    gemini_key,
                    "config:Config.get_gemini_api_key()",
                )
                logger.info("Found Gemini API key in config")
        except Exception as e:
            logger.warning(f"Could not import config module: {e}")

        return secrets

    def _find_jwt_keys(self) -> dict[str, tuple[str, str]]:
        """Find JWT RSA keys."""
        secrets = {}

        jwt_keys_dir = Path.home() / ".ai_pdf_scholar" / "jwt_keys"

        if jwt_keys_dir.exists():
            private_key_path = jwt_keys_dir / "private_key.pem"
            public_key_path = jwt_keys_dir / "public_key.pem"

            if private_key_path.exists():
                with open(private_key_path) as f:
                    private_key = f.read()
                    secrets["jwt_private_key"] = (
                        private_key,
                        f"file:{private_key_path}",
                    )
                    logger.info(f"Found JWT private key at {private_key_path}")

            if public_key_path.exists():
                with open(public_key_path) as f:
                    public_key = f.read()
                    secrets["jwt_public_key"] = (public_key, f"file:{public_key_path}")
                    logger.info(f"Found JWT public key at {public_key_path}")

        return secrets

    def _find_settings_secrets(self) -> dict[str, tuple[str, str]]:
        """Find secrets in settings.json file."""
        secrets = {}

        settings_file = Path.home() / ".ai_pdf_scholar" / "settings.json"

        if settings_file.exists():
            try:
                with open(settings_file) as f:
                    settings = json.load(f)

                # Check for API keys
                if "gemini_api_key" in settings:
                    secrets["api_key_gemini"] = (
                        settings["gemini_api_key"],
                        f"file:{settings_file}",
                    )
                    logger.info("Found Gemini API key in settings.json")

                if "openai_api_key" in settings:
                    secrets["api_key_openai"] = (
                        settings["openai_api_key"],
                        f"file:{settings_file}",
                    )
                    logger.info("Found OpenAI API key in settings.json")

            except Exception as e:
                logger.warning(f"Could not read settings file: {e}")

        return secrets

    def migrate_secrets(
        self, secrets: dict[str, tuple[str, str]], rotation_days: int | None = 90
    ) -> dict[str, bool]:
        """
        Migrate secrets to the new management system.

        Args:
            secrets: Dictionary of secret_key -> (value, source)
            rotation_days: Default rotation interval in days

        Returns:
            Dictionary of secret_key -> success status
        """
        if not self.secrets_manager:
            raise RuntimeError("Secrets manager not initialized")

        results = {}

        for secret_key, (value, source) in secrets.items():
            try:
                # Determine secret type
                secret_type = self._determine_secret_type(secret_key)

                # Skip if already exists (unless forcing)
                existing = self.secrets_manager.get_secret(secret_key, use_cache=False)
                if existing:
                    logger.info(f"Secret {secret_key} already exists, skipping")
                    self.migration_report["skipped"].append(
                        {
                            "key": secret_key,
                            "source": source,
                            "reason": "already_exists",
                        }
                    )
                    results[secret_key] = True
                    continue

                if self.dry_run:
                    logger.info(f"[DRY RUN] Would migrate {secret_key} from {source}")
                    results[secret_key] = True
                else:
                    # Store secret in new system
                    success = self.secrets_manager.set_secret(
                        key=secret_key,
                        value=value,
                        secret_type=secret_type,
                        rotation_interval_days=rotation_days,
                        tags={
                            "migrated_from": source,
                            "migration_date": datetime.utcnow().isoformat(),
                        },
                        description=f"Migrated from {source}",
                    )

                    if success:
                        logger.info(f"Successfully migrated {secret_key} from {source}")
                        self.migration_report["migrated"].append(
                            {
                                "key": secret_key,
                                "source": source,
                                "type": secret_type.value,
                            }
                        )
                    else:
                        logger.error(f"Failed to migrate {secret_key}")
                        self.migration_report["failed"].append(
                            {
                                "key": secret_key,
                                "source": source,
                                "error": "storage_failed",
                            }
                        )

                    results[secret_key] = success

            except Exception as e:
                logger.error(f"Error migrating {secret_key}: {e}")
                self.migration_report["failed"].append(
                    {"key": secret_key, "source": source, "error": str(e)}
                )
                results[secret_key] = False

        return results

    def _determine_secret_type(self, key: str) -> SecretType:
        """Determine the type of secret based on the key name."""
        key_lower = key.lower()

        if "api_key" in key_lower or "apikey" in key_lower:
            return SecretType.API_KEY
        elif "database" in key_lower or "db_" in key_lower:
            return SecretType.DATABASE_URL
        elif "jwt" in key_lower and "private" in key_lower:
            return SecretType.JWT_PRIVATE_KEY
        elif "jwt" in key_lower and "public" in key_lower:
            return SecretType.JWT_PUBLIC_KEY
        elif "redis" in key_lower:
            return SecretType.REDIS_URL
        elif "smtp" in key_lower and "password" in key_lower:
            return SecretType.SMTP_PASSWORD
        elif "encryption" in key_lower or "encrypt" in key_lower:
            return SecretType.ENCRYPTION_KEY
        elif "oauth" in key_lower:
            return SecretType.OAUTH_SECRET
        elif "webhook" in key_lower:
            return SecretType.WEBHOOK_SECRET
        elif "sign" in key_lower or "secret" in key_lower:
            return SecretType.SIGNING_KEY
        else:
            return SecretType.API_KEY  # Default

    def cleanup_old_secrets(self, secrets: dict[str, tuple[str, str]]) -> None:
        """
        Clean up old secret storage locations after successful migration.

        Args:
            secrets: Dictionary of migrated secrets
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would clean up old secret locations")
            return

        # Create backup first
        backup_dir = (
            Path.home()
            / ".ai_pdf_scholar"
            / "backup"
            / datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        backup_dir.mkdir(parents=True, exist_ok=True)

        cleaned = []

        for secret_key, (value, source) in secrets.items():
            # Only clean up if successfully migrated
            if secret_key not in [m["key"] for m in self.migration_report["migrated"]]:
                continue

            try:
                if source.startswith("file:"):
                    file_path = Path(source.replace("file:", ""))

                    # Special handling for settings.json (don't delete entire file)
                    if file_path.name == "settings.json":
                        with open(file_path) as f:
                            settings = json.load(f)

                        # Backup original
                        backup_path = backup_dir / "settings.json"
                        with open(backup_path, "w") as f:
                            json.dump(settings, f, indent=2)

                        # Remove secret keys
                        if "gemini_api_key" in settings:
                            del settings["gemini_api_key"]
                        if "openai_api_key" in settings:
                            del settings["openai_api_key"]

                        # Write back
                        with open(file_path, "w") as f:
                            json.dump(settings, f, indent=2)

                        cleaned.append(f"Removed keys from {file_path}")

                    # Don't delete JWT keys automatically (user should do this manually)
                    elif "jwt" in str(file_path):
                        self.migration_report["warnings"].append(
                            f"JWT keys at {file_path} should be manually removed after verifying migration"
                        )

                elif source.startswith("env:"):
                    env_var = source.replace("env:", "")
                    self.migration_report["warnings"].append(
                        f"Environment variable {env_var} should be removed from .env file or shell configuration"
                    )

            except Exception as e:
                logger.error(f"Error cleaning up {source}: {e}")

        if cleaned:
            logger.info(f"Cleaned up {len(cleaned)} old secret locations")
            logger.info(f"Backup created at {backup_dir}")

    def generate_report(self) -> str:
        """Generate a migration report."""
        report = []
        report.append("=" * 60)
        report.append("SECRETS MIGRATION REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {datetime.utcnow().isoformat()}")
        report.append(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        report.append("")

        # Summary
        report.append("SUMMARY")
        report.append("-" * 30)
        report.append(f"Migrated: {len(self.migration_report['migrated'])}")
        report.append(f"Failed: {len(self.migration_report['failed'])}")
        report.append(f"Skipped: {len(self.migration_report['skipped'])}")
        report.append(f"Warnings: {len(self.migration_report['warnings'])}")
        report.append("")

        # Details
        if self.migration_report["migrated"]:
            report.append("MIGRATED SECRETS")
            report.append("-" * 30)
            for item in self.migration_report["migrated"]:
                report.append(
                    f"  ✓ {item['key']} ({item['type']}) from {item['source']}"
                )
            report.append("")

        if self.migration_report["failed"]:
            report.append("FAILED MIGRATIONS")
            report.append("-" * 30)
            for item in self.migration_report["failed"]:
                report.append(
                    f"  ✗ {item['key']} from {item['source']}: {item['error']}"
                )
            report.append("")

        if self.migration_report["skipped"]:
            report.append("SKIPPED SECRETS")
            report.append("-" * 30)
            for item in self.migration_report["skipped"]:
                report.append(
                    f"  - {item['key']} from {item['source']}: {item['reason']}"
                )
            report.append("")

        if self.migration_report["warnings"]:
            report.append("WARNINGS")
            report.append("-" * 30)
            for warning in self.migration_report["warnings"]:
                report.append(f"  ⚠ {warning}")
            report.append("")

        # Next steps
        report.append("NEXT STEPS")
        report.append("-" * 30)
        report.append("1. Review the migration report above")
        report.append("2. Update application code to use SecretsManager")
        report.append("3. Remove old secret storage locations")
        report.append("4. Update deployment scripts and CI/CD")
        report.append("5. Test the application thoroughly")
        report.append("")

        if self.dry_run:
            report.append("NOTE: This was a dry run. No changes were made.")
            report.append("Run with --live flag to perform actual migration.")

        report.append("=" * 60)

        return "\n".join(report)


def main():
    """Main migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate secrets to new management system"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["vault", "aws", "local"],
        default="local",
        help="Target secret provider",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Perform actual migration (default is dry run)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up old secret locations after migration",
    )
    parser.add_argument(
        "--rotation-days",
        type=int,
        default=90,
        help="Default rotation interval in days",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Map provider choice
    provider_map = {
        "vault": SecretProvider.VAULT,
        "aws": SecretProvider.AWS_SECRETS_MANAGER,
        "local": SecretProvider.LOCAL_ENCRYPTED,
    }
    provider = provider_map[args.provider]

    # Create migration instance
    migration = SecretsMigration(dry_run=not args.live)

    try:
        # Initialize secrets manager
        logger.info(f"Initializing secrets manager with {provider.value} provider...")
        migration.initialize_manager(provider)

        # Find existing secrets
        logger.info("Searching for existing secrets...")
        existing_secrets = migration.find_existing_secrets()
        logger.info(f"Found {len(existing_secrets)} secrets")

        if not existing_secrets:
            logger.warning("No secrets found to migrate")
            return

        # Migrate secrets
        logger.info("Starting migration...")
        _ = migration.migrate_secrets(existing_secrets, args.rotation_days)

        # Clean up if requested
        if args.cleanup and not migration.dry_run:
            logger.info("Cleaning up old secret locations...")
            migration.cleanup_old_secrets(existing_secrets)

        # Generate and print report
        report = migration.generate_report()
        print("\n" + report)

        # Save report to file
        report_file = (
            Path.home()
            / ".ai_pdf_scholar"
            / f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_file}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
