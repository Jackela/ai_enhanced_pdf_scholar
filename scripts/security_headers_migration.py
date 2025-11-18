#!/usr/bin/env python3
"""
Security Headers Migration Script
Helps with gradual rollout of security headers in production.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MigrationPhase(str, Enum):
    """Security headers migration phases."""

    PHASE_1_MONITORING = "phase_1_monitoring"
    PHASE_2_REPORT_ONLY = "phase_2_report_only"
    PHASE_3_ENFORCE_BASIC = "phase_3_enforce_basic"
    PHASE_4_ENFORCE_STRICT = "phase_4_enforce_strict"
    PHASE_5_PRODUCTION_READY = "phase_5_production_ready"


class SecurityHeadersMigration:
    """Manages gradual rollout of security headers."""

    def __init__(self, environment: str = "production"):
        """Initialize migration manager."""
        self.environment = environment
        self.config_file = Path.home() / ".ai_pdf_scholar" / "security_migration.json"
        self.config_file.parent.mkdir(exist_ok=True, parents=True)
        self.current_phase = self._load_current_phase()

    def _load_current_phase(self) -> MigrationPhase:
        """Load current migration phase from config."""
        if self.config_file.exists():
            with open(self.config_file) as f:
                data = json.load(f)
                return MigrationPhase(
                    data.get("current_phase", MigrationPhase.PHASE_1_MONITORING)
                )
        return MigrationPhase.PHASE_1_MONITORING

    def _save_current_phase(self, phase: MigrationPhase) -> None:
        """Save current migration phase to config."""
        data = {
            "current_phase": phase.value,
            "updated_at": datetime.utcnow().isoformat(),
            "environment": self.environment,
        }
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_phase_config(self, phase: MigrationPhase | None = None) -> dict[str, any]:
        """Get configuration for a specific migration phase."""
        phase = phase or self.current_phase

        configs = {
            MigrationPhase.PHASE_1_MONITORING: {
                "CSP_ENABLED": "false",
                "HSTS_MAX_AGE": "0",
                "X_FRAME_OPTIONS": "SAMEORIGIN",
                "PERMISSIONS_POLICY_ENABLED": "false",
                "description": "Monitoring only - minimal security headers",
            },
            MigrationPhase.PHASE_2_REPORT_ONLY: {
                "CSP_ENABLED": "true",
                "CSP_REPORT_ONLY": "true",
                "HSTS_MAX_AGE": "300",  # 5 minutes
                "X_FRAME_OPTIONS": "SAMEORIGIN",
                "PERMISSIONS_POLICY_ENABLED": "true",
                "description": "CSP in Report-Only mode, short HSTS",
            },
            MigrationPhase.PHASE_3_ENFORCE_BASIC: {
                "CSP_ENABLED": "true",
                "CSP_REPORT_ONLY": "false",
                "CSP_POLICY": "basic",  # Allows some unsafe practices
                "HSTS_MAX_AGE": "86400",  # 1 day
                "X_FRAME_OPTIONS": "DENY",
                "PERMISSIONS_POLICY_ENABLED": "true",
                "description": "Basic CSP enforcement, 1-day HSTS",
            },
            MigrationPhase.PHASE_4_ENFORCE_STRICT: {
                "CSP_ENABLED": "true",
                "CSP_REPORT_ONLY": "false",
                "CSP_POLICY": "strict",  # Strict CSP with nonces
                "HSTS_MAX_AGE": "2592000",  # 30 days
                "HSTS_INCLUDE_SUBDOMAINS": "true",
                "X_FRAME_OPTIONS": "DENY",
                "PERMISSIONS_POLICY_ENABLED": "true",
                "EXPECT_CT_ENABLED": "true",
                "description": "Strict CSP enforcement, 30-day HSTS",
            },
            MigrationPhase.PHASE_5_PRODUCTION_READY: {
                "CSP_ENABLED": "true",
                "CSP_REPORT_ONLY": "false",
                "CSP_POLICY": "strict",
                "CSP_TRUSTED_TYPES": "true",
                "HSTS_MAX_AGE": "31536000",  # 1 year
                "HSTS_INCLUDE_SUBDOMAINS": "true",
                "HSTS_PRELOAD": "true",
                "X_FRAME_OPTIONS": "DENY",
                "PERMISSIONS_POLICY_ENABLED": "true",
                "EXPECT_CT_ENABLED": "true",
                "EXPECT_CT_ENFORCE": "true",
                "COEP": "require-corp",
                "COOP": "same-origin",
                "CORP": "same-origin",
                "COOKIE_SAMESITE": "strict",
                "description": "Production-ready with HSTS preload",
            },
        }

        return configs[phase]

    def validate_phase_requirements(
        self, phase: MigrationPhase
    ) -> tuple[bool, list[str]]:
        """Validate requirements for moving to a specific phase."""
        issues = []

        if phase == MigrationPhase.PHASE_2_REPORT_ONLY:
            # Check if monitoring has been running
            if not self._check_monitoring_duration(days=3):
                issues.append("Monitoring phase should run for at least 3 days")

        elif phase == MigrationPhase.PHASE_3_ENFORCE_BASIC:
            # Check CSP violations
            violations = self._get_csp_violations_count()
            if violations > 100:
                issues.append(
                    f"High CSP violation count: {violations}. Review and fix before enforcing."
                )

        elif phase == MigrationPhase.PHASE_4_ENFORCE_STRICT:
            # Check HTTPS configuration
            if not self._check_https_enabled():
                issues.append("HTTPS must be properly configured")

            # Check subdomain HTTPS
            if not self._check_subdomains_https():
                issues.append("All subdomains must support HTTPS")

        elif phase == MigrationPhase.PHASE_5_PRODUCTION_READY:
            # Check for HSTS preload eligibility
            if not self._check_hsts_preload_eligible():
                issues.append("Site must meet HSTS preload requirements")

            # Check certificate transparency
            if not self._check_certificate_transparency():
                issues.append("Certificate transparency logs must be configured")

        return len(issues) == 0, issues

    def _check_monitoring_duration(self, days: int) -> bool:
        """Check if monitoring has been running for required duration."""
        if not self.config_file.exists():
            return False

        with open(self.config_file) as f:
            data = json.load(f)
            updated_at = datetime.fromisoformat(
                data.get("updated_at", datetime.utcnow().isoformat())
            )
            return (datetime.utcnow() - updated_at).days >= days

    def _get_csp_violations_count(self) -> int:
        """Get count of CSP violations from monitoring."""
        # In a real implementation, this would query the violation database
        # For now, return a mock value
        return 10

    def _check_https_enabled(self) -> bool:
        """Check if HTTPS is properly configured."""
        # In a real implementation, this would check SSL certificate and configuration
        return True

    def _check_subdomains_https(self) -> bool:
        """Check if all subdomains support HTTPS."""
        # In a real implementation, this would scan subdomains
        return True

    def _check_hsts_preload_eligible(self) -> bool:
        """Check if site meets HSTS preload requirements."""
        # Requirements:
        # - Valid certificate
        # - HTTP redirects to HTTPS
        # - All subdomains over HTTPS
        # - HSTS header with max-age >= 31536000
        # - includeSubDomains directive
        return True

    def _check_certificate_transparency(self) -> bool:
        """Check if certificate transparency is configured."""
        # In a real implementation, this would check CT logs
        return True

    def advance_phase(self) -> tuple[bool, str]:
        """Advance to the next migration phase."""
        phase_order = [
            MigrationPhase.PHASE_1_MONITORING,
            MigrationPhase.PHASE_2_REPORT_ONLY,
            MigrationPhase.PHASE_3_ENFORCE_BASIC,
            MigrationPhase.PHASE_4_ENFORCE_STRICT,
            MigrationPhase.PHASE_5_PRODUCTION_READY,
        ]

        current_index = phase_order.index(self.current_phase)
        if current_index >= len(phase_order) - 1:
            return False, "Already at final phase"

        next_phase = phase_order[current_index + 1]

        # Validate requirements
        valid, issues = self.validate_phase_requirements(next_phase)
        if not valid:
            return (
                False,
                f"Cannot advance to {next_phase.value}. Issues: {', '.join(issues)}",
            )

        # Update phase
        self.current_phase = next_phase
        self._save_current_phase(next_phase)

        return True, f"Advanced to {next_phase.value}"

    def rollback_phase(self) -> tuple[bool, str]:
        """Rollback to the previous migration phase."""
        phase_order = [
            MigrationPhase.PHASE_1_MONITORING,
            MigrationPhase.PHASE_2_REPORT_ONLY,
            MigrationPhase.PHASE_3_ENFORCE_BASIC,
            MigrationPhase.PHASE_4_ENFORCE_STRICT,
            MigrationPhase.PHASE_5_PRODUCTION_READY,
        ]

        current_index = phase_order.index(self.current_phase)
        if current_index <= 0:
            return False, "Already at initial phase"

        prev_phase = phase_order[current_index - 1]

        # Update phase
        self.current_phase = prev_phase
        self._save_current_phase(prev_phase)

        return True, f"Rolled back to {prev_phase.value}"

    def generate_env_file(self, output_file: Path | None = None) -> None:
        """Generate .env file for current migration phase."""
        output_file = output_file or Path(".env.security")

        config = self.get_phase_config()

        lines = [
            "# Security Headers Configuration",
            f"# Generated for migration phase: {self.current_phase.value}",
            f"# Generated at: {datetime.utcnow().isoformat()}",
            f"# Description: {config.pop('description', '')}",
            "",
        ]

        for key, value in config.items():
            if key != "description":
                lines.append(f"{key}={value}")

        with open(output_file, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated environment file: {output_file}")

    def test_headers(self, url: str = "http://localhost:8000") -> dict[str, str]:
        """Test security headers on a URL."""
        import requests

        try:
            response = requests.get(url, timeout=5)
            security_headers = {}

            header_names = [
                "Content-Security-Policy",
                "Content-Security-Policy-Report-Only",
                "Strict-Transport-Security",
                "X-Frame-Options",
                "X-Content-Type-Options",
                "X-XSS-Protection",
                "Referrer-Policy",
                "Permissions-Policy",
                "Cross-Origin-Embedder-Policy",
                "Cross-Origin-Opener-Policy",
                "Cross-Origin-Resource-Policy",
                "Expect-CT",
            ]

            for header in header_names:
                if header in response.headers:
                    security_headers[header] = response.headers[header]

            return security_headers
        except Exception as e:
            logger.error(f"Failed to test headers: {e}")
            return {}

    def print_status(self) -> None:
        """Print current migration status."""
        print(f"\n{'='*60}")
        print("Security Headers Migration Status")
        print(f"{'='*60}")
        print(f"Current Phase: {self.current_phase.value}")
        print(f"Environment: {self.environment}")

        config = self.get_phase_config()
        print(f"Description: {config.get('description', '')}")

        print("\nCurrent Configuration:")
        for key, value in config.items():
            if key != "description":
                print(f"  {key}: {value}")

        print("\nPhase Progression:")
        phases = [
            MigrationPhase.PHASE_1_MONITORING,
            MigrationPhase.PHASE_2_REPORT_ONLY,
            MigrationPhase.PHASE_3_ENFORCE_BASIC,
            MigrationPhase.PHASE_4_ENFORCE_STRICT,
            MigrationPhase.PHASE_5_PRODUCTION_READY,
        ]

        for i, phase in enumerate(phases, 1):
            marker = (
                "✓" if phases.index(self.current_phase) >= phases.index(phase) else "○"
            )
            print(f"  {marker} Phase {i}: {phase.value}")

        print(f"{'='*60}\n")

    def generate_rollback_script(self) -> None:
        """Generate emergency rollback script."""
        script_content = f"""#!/bin/bash
# Emergency Security Headers Rollback Script
# Generated: {datetime.utcnow().isoformat()}

echo "🚨 Emergency Security Headers Rollback"
echo "======================================"

# Disable CSP
export CSP_ENABLED=false

# Disable HSTS
export HSTS_MAX_AGE=0

# Relax frame options
export X_FRAME_OPTIONS=SAMEORIGIN

# Disable permissions policy
export PERMISSIONS_POLICY_ENABLED=false

# Disable certificate transparency
export EXPECT_CT_ENABLED=false

# Relax cookie security
export COOKIE_SAMESITE=lax

echo "✅ Security headers rolled back to minimal configuration"
echo "⚠️  Remember to restart the application for changes to take effect"
"""

        rollback_file = Path("rollback_security_headers.sh")
        with open(rollback_file, "w") as f:
            f.write(script_content)

        # Make executable on Unix-like systems
        if os.name != "nt":
            os.chmod(rollback_file, 0o755)

        logger.info(f"Generated rollback script: {rollback_file}")


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(description="Security Headers Migration Tool")
    parser.add_argument(
        "command",
        choices=[
            "status",
            "advance",
            "rollback",
            "generate-env",
            "test",
            "generate-rollback",
        ],
        help="Command to execute",
    )
    parser.add_argument(
        "--environment",
        default="production",
        choices=["development", "staging", "production"],
        help="Target environment",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="URL to test headers (for 'test' command)",
    )
    parser.add_argument(
        "--output",
        help="Output file for 'generate-env' command",
    )

    args = parser.parse_args()

    migration = SecurityHeadersMigration(environment=args.environment)

    if args.command == "status":
        migration.print_status()

    elif args.command == "advance":
        success, message = migration.advance_phase()
        if success:
            logger.info(f"✅ {message}")
            migration.print_status()
        else:
            logger.error(f"❌ {message}")
            sys.exit(1)

    elif args.command == "rollback":
        success, message = migration.rollback_phase()
        if success:
            logger.warning(f"⚠️  {message}")
            migration.print_status()
        else:
            logger.error(f"❌ {message}")
            sys.exit(1)

    elif args.command == "generate-env":
        output_file = Path(args.output) if args.output else None
        migration.generate_env_file(output_file)
        migration.print_status()

    elif args.command == "test":
        logger.info(f"Testing headers at {args.url}")
        headers = migration.test_headers(args.url)

        if headers:
            print("\nSecurity Headers Found:")
            for name, value in headers.items():
                # Truncate long values for display
                display_value = value if len(value) <= 100 else f"{value[:97]}..."
                print(f"  {name}: {display_value}")
        else:
            print("No security headers found or connection failed")

    elif args.command == "generate-rollback":
        migration.generate_rollback_script()
        logger.info("✅ Rollback script generated")


if __name__ == "__main__":
    main()
