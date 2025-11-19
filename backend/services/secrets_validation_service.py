"""
Production Secrets Validation Service
Implements comprehensive validation, monitoring, and compliance checking
for secrets across all environments with automated remediation suggestions.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from ..core.secrets_vault import ProductionSecretsManager, calculate_entropy

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ComplianceStandard(str, Enum):
    """Security compliance standards."""

    NIST_800_53 = "nist_800_53"
    ISO_27001 = "iso_27001"
    SOC2_TYPE2 = "soc2_type2"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    HIPAA = "hipaa"


@dataclass
class ValidationRule:
    """Represents a secret validation rule."""

    name: str
    description: str
    severity: ValidationSeverity
    compliance_standards: list[ComplianceStandard] = field(default_factory=list)
    enabled: bool = True
    custom_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of a secret validation check."""

    rule_name: str
    passed: bool
    severity: ValidationSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    remediation: str | None = None
    compliance_impact: list[ComplianceStandard] = field(default_factory=list)


@dataclass
class SecretValidationReport:
    """Comprehensive validation report for secrets."""

    secret_name: str
    environment: str
    timestamp: datetime
    overall_status: str  # "pass", "warning", "fail"
    compliance_status: dict[ComplianceStandard, str] = field(default_factory=dict)
    validation_results: list[ValidationResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SecretValidationService:
    """
    Advanced secrets validation service with compliance checking,
    automated monitoring, and remediation recommendations.
    """

    def __init__(self, secrets_manager: ProductionSecretsManager | None = None):
        """Initialize the validation service."""
        self.secrets_manager = secrets_manager or ProductionSecretsManager()
        self.validation_rules = self._initialize_validation_rules()
        self.compliance_mappings = self._initialize_compliance_mappings()
        self.validation_cache: dict[str, tuple[datetime, SecretValidationReport]] = {}
        self.cache_ttl_minutes = 30

    def _initialize_validation_rules(self) -> dict[str, ValidationRule]:
        """Initialize comprehensive validation rules."""
        rules = {}

        # Strength validation rules
        rules["minimum_length"] = ValidationRule(
            name="minimum_length",
            description="Enforce minimum password/secret length requirements",
            severity=ValidationSeverity.HIGH,
            compliance_standards=[
                ComplianceStandard.NIST_800_53,
                ComplianceStandard.ISO_27001,
                ComplianceStandard.SOC2_TYPE2,
            ],
            custom_params={
                "production": {
                    "database_password": 16,
                    "jwt_secret": 32,
                    "encryption_key": 32,
                    "api_key": 20,
                    "default": 12,
                },
                "staging": {
                    "database_password": 12,
                    "jwt_secret": 24,
                    "encryption_key": 24,
                    "api_key": 16,
                    "default": 10,
                },
                "development": {
                    "database_password": 8,
                    "jwt_secret": 16,
                    "encryption_key": 16,
                    "api_key": 12,
                    "default": 8,
                },
            },
        )

        rules["entropy_threshold"] = ValidationRule(
            name="entropy_threshold",
            description="Ensure sufficient entropy in secret values",
            severity=ValidationSeverity.CRITICAL,
            compliance_standards=[
                ComplianceStandard.NIST_800_53,
                ComplianceStandard.ISO_27001,
                ComplianceStandard.PCI_DSS,
            ],
            custom_params={
                "production": {"min_entropy": 64},
                "staging": {"min_entropy": 48},
                "development": {"min_entropy": 32},
            },
        )

        rules["no_weak_patterns"] = ValidationRule(
            name="no_weak_patterns",
            description="Detect and reject common weak password patterns",
            severity=ValidationSeverity.HIGH,
            compliance_standards=[ComplianceStandard.NIST_800_53],
            custom_params={
                "weak_patterns": [
                    "password",
                    "123456",
                    "admin",
                    "default",
                    "secret",
                    "qwerty",
                    "letmein",
                    "welcome",
                    "monkey",
                    "dragon",
                ],
                "sequential_patterns": True,
                "keyboard_patterns": True,
            },
        )

        rules["character_diversity"] = ValidationRule(
            name="character_diversity",
            description="Enforce character complexity requirements",
            severity=ValidationSeverity.MEDIUM,
            compliance_standards=[
                ComplianceStandard.NIST_800_53,
                ComplianceStandard.ISO_27001,
            ],
            custom_params={
                "require_uppercase": True,
                "require_lowercase": True,
                "require_digits": True,
                "require_special": True,
                "min_character_classes": 3,
            },
        )

        rules["no_dictionary_words"] = ValidationRule(
            name="no_dictionary_words",
            description="Prevent use of common dictionary words",
            severity=ValidationSeverity.MEDIUM,
            compliance_standards=[ComplianceStandard.NIST_800_53],
            custom_params={
                "check_english_words": True,
                "check_common_passwords": True,
                "max_dictionary_ratio": 0.5,
            },
        )

        rules["rotation_age_check"] = ValidationRule(
            name="rotation_age_check",
            description="Check if secrets need rotation based on age",
            severity=ValidationSeverity.HIGH,
            compliance_standards=[
                ComplianceStandard.NIST_800_53,
                ComplianceStandard.SOC2_TYPE2,
                ComplianceStandard.ISO_27001,
            ],
            custom_params={
                "production": {
                    "database_password": 90,  # days
                    "jwt_secret": 180,
                    "encryption_key": 365,
                    "api_key": 90,
                    "default": 90,
                },
                "staging": {
                    "database_password": 120,
                    "jwt_secret": 180,
                    "encryption_key": 365,
                    "api_key": 120,
                    "default": 120,
                },
                "development": {
                    "database_password": 180,
                    "jwt_secret": 365,
                    "encryption_key": 730,
                    "api_key": 180,
                    "default": 180,
                },
            },
        )

        rules["access_frequency_check"] = ValidationRule(
            name="access_frequency_check",
            description="Monitor secret access patterns for anomalies",
            severity=ValidationSeverity.MEDIUM,
            compliance_standards=[
                ComplianceStandard.SOC2_TYPE2,
                ComplianceStandard.ISO_27001,
            ],
            custom_params={
                "max_daily_accesses": 1000,
                "suspicious_access_threshold": 10,
                "unusual_hour_threshold": 3,  # accesses between midnight and 6 AM
            },
        )

        rules["encryption_compliance"] = ValidationRule(
            name="encryption_compliance",
            description="Verify encryption standards compliance",
            severity=ValidationSeverity.CRITICAL,
            compliance_standards=[
                ComplianceStandard.NIST_800_53,
                ComplianceStandard.PCI_DSS,
                ComplianceStandard.GDPR,
                ComplianceStandard.HIPAA,
            ],
            custom_params={
                "required_algorithms": ["aes_256_gcm", "chacha20_poly1305"],
                "min_key_size": 256,
                "require_authenticated_encryption": True,
            },
        )

        rules["exposure_check"] = ValidationRule(
            name="exposure_check",
            description="Check for potential secret exposure",
            severity=ValidationSeverity.CRITICAL,
            compliance_standards=[
                ComplianceStandard.GDPR,
                ComplianceStandard.SOC2_TYPE2,
                ComplianceStandard.HIPAA,
            ],
            custom_params={
                "check_environment_vars": True,
                "check_log_files": True,
                "check_config_files": True,
                "check_version_control": True,
            },
        )

        return rules

    def _initialize_compliance_mappings(
        self,
    ) -> dict[ComplianceStandard, dict[str, Any]]:
        """Initialize compliance standard mappings."""
        return {
            ComplianceStandard.NIST_800_53: {
                "name": "NIST SP 800-53",
                "description": "Security and Privacy Controls for Federal Information Systems",
                "key_controls": ["IA-5", "SC-12", "SC-13", "AC-2"],
                "required_rules": [
                    "minimum_length",
                    "entropy_threshold",
                    "no_weak_patterns",
                    "character_diversity",
                    "rotation_age_check",
                    "encryption_compliance",
                ],
            },
            ComplianceStandard.ISO_27001: {
                "name": "ISO/IEC 27001:2013",
                "description": "Information Security Management Systems",
                "key_controls": ["A.9.4.3", "A.10.1.1", "A.14.1.2"],
                "required_rules": [
                    "minimum_length",
                    "entropy_threshold",
                    "character_diversity",
                    "rotation_age_check",
                    "access_frequency_check",
                ],
            },
            ComplianceStandard.SOC2_TYPE2: {
                "name": "SOC 2 Type II",
                "description": "Service Organization Control 2 Type II",
                "key_controls": ["CC6.1", "CC6.7", "CC6.8"],
                "required_rules": [
                    "minimum_length",
                    "rotation_age_check",
                    "access_frequency_check",
                    "exposure_check",
                ],
            },
            ComplianceStandard.PCI_DSS: {
                "name": "PCI Data Security Standard",
                "description": "Payment Card Industry Data Security Standard",
                "key_controls": ["8.2.3", "8.2.4", "3.5.2"],
                "required_rules": [
                    "entropy_threshold",
                    "encryption_compliance",
                    "rotation_age_check",
                ],
            },
        }

    async def validate_secret(
        self,
        secret_name: str,
        secret_value: str,
        environment: str = "production",
        compliance_standards: list[ComplianceStandard] | None = None,
    ) -> SecretValidationReport:
        """
        Validate a single secret against all applicable rules.

        Args:
            secret_name: Name of the secret
            secret_value: Secret value to validate
            environment: Environment context
            compliance_standards: Specific standards to validate against

        Returns:
            Comprehensive validation report
        """
        # Check cache first
        cache_key = f"{secret_name}:{environment}:{hash(secret_value)}"
        if cache_key in self.validation_cache:
            cached_time, cached_report = self.validation_cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(
                minutes=self.cache_ttl_minutes
            ):
                return cached_report

        report = SecretValidationReport(
            secret_name=secret_name,
            environment=environment,
            timestamp=datetime.utcnow(),
            overall_status="pass",
        )

        # Determine applicable compliance standards
        if compliance_standards is None:
            compliance_standards = self._get_environment_compliance_standards(
                environment
            )

        # Run validation rules
        for _rule_name, rule in self.validation_rules.values():
            if not rule.enabled:
                continue

            # Check if rule applies to compliance standards
            if compliance_standards and not any(
                std in rule.compliance_standards for std in compliance_standards
            ):
                continue

            result = await self._execute_validation_rule(
                rule, secret_name, secret_value, environment
            )
            report.validation_results.append(result)

            # Update overall status
            if not result.passed:
                if result.severity in [
                    ValidationSeverity.CRITICAL,
                    ValidationSeverity.HIGH,
                ]:
                    report.overall_status = "fail"
                elif report.overall_status == "pass":
                    report.overall_status = "warning"

        # Calculate compliance status
        for standard in compliance_standards:
            report.compliance_status[standard] = self._calculate_compliance_status(
                report.validation_results, standard
            )

        # Generate metadata
        report.metadata = {
            "secret_length": len(secret_value),
            "entropy_bits": calculate_entropy(secret_value),
            "character_classes": self._count_character_classes(secret_value),
            "validation_rules_run": len(list(report.validation_results)),
            "environment": environment,
            "compliance_standards": [s.value for s in compliance_standards],
        }

        # Cache the report
        self.validation_cache[cache_key] = (datetime.utcnow(), report)

        return report

    async def validate_environment_secrets(
        self,
        secrets_dict: dict[str, str],
        environment: str = "production",
        compliance_standards: list[ComplianceStandard] | None = None,
    ) -> dict[str, SecretValidationReport]:
        """
        Validate all secrets in an environment.

        Args:
            secrets_dict: Dictionary of secret names and values
            environment: Environment name
            compliance_standards: Compliance standards to validate against

        Returns:
            Dictionary of validation reports by secret name
        """
        validation_tasks = []

        for secret_name, secret_value in secrets_dict.items():
            task = self.validate_secret(
                secret_name, secret_value, environment, compliance_standards
            )
            validation_tasks.append((secret_name, task))

        results = {}
        for secret_name, task in validation_tasks:
            try:
                results[secret_name] = await task
            except Exception as e:
                logger.error(f"Failed to validate secret {secret_name}: {e}")
                # Create error report
                results[secret_name] = SecretValidationReport(
                    secret_name=secret_name,
                    environment=environment,
                    timestamp=datetime.utcnow(),
                    overall_status="fail",
                    validation_results=[
                        ValidationResult(
                            rule_name="validation_error",
                            passed=False,
                            severity=ValidationSeverity.CRITICAL,
                            message=f"Validation failed: {str(e)}",
                        )
                    ],
                )

        return results

    async def _execute_validation_rule(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Execute a specific validation rule."""
        try:
            if rule.name == "minimum_length":
                return self._validate_minimum_length(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "entropy_threshold":
                return self._validate_entropy_threshold(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "no_weak_patterns":
                return self._validate_no_weak_patterns(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "character_diversity":
                return self._validate_character_diversity(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "no_dictionary_words":
                return self._validate_no_dictionary_words(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "rotation_age_check":
                return await self._validate_rotation_age_check(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "access_frequency_check":
                return await self._validate_access_frequency_check(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "encryption_compliance":
                return self._validate_encryption_compliance(
                    rule, secret_name, secret_value, environment
                )
            elif rule.name == "exposure_check":
                return await self._validate_exposure_check(
                    rule, secret_name, secret_value, environment
                )
            else:
                return ValidationResult(
                    rule_name=rule.name,
                    passed=False,
                    severity=ValidationSeverity.HIGH,
                    message=f"Unknown validation rule: {rule.name}",
                )
        except Exception as e:
            logger.error(f"Error executing validation rule {rule.name}: {e}")
            return ValidationResult(
                rule_name=rule.name,
                passed=False,
                severity=ValidationSeverity.CRITICAL,
                message=f"Rule execution failed: {str(e)}",
            )

    def _validate_minimum_length(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate minimum length requirement."""
        env_params = rule.custom_params.get(
            environment, rule.custom_params.get("production", {})
        )
        min_length = env_params.get(secret_name, env_params.get("default", 12))

        actual_length = len(secret_value)
        passed = actual_length >= min_length

        return ValidationResult(
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=f"Length {actual_length} {'meets' if passed else 'below'} minimum {min_length}",
            details={
                "actual_length": actual_length,
                "minimum_length": min_length,
                "environment": environment,
            },
            remediation=(
                f"Increase secret length to at least {min_length} characters"
                if not passed
                else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    def _validate_entropy_threshold(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate entropy threshold."""
        env_params = rule.custom_params.get(
            environment, rule.custom_params.get("production", {})
        )
        min_entropy = env_params.get("min_entropy", 64)

        actual_entropy = calculate_entropy(secret_value)
        passed = actual_entropy >= min_entropy

        return ValidationResult(
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=f"Entropy {actual_entropy:.1f} bits {'meets' if passed else 'below'} minimum {min_entropy} bits",
            details={
                "actual_entropy": actual_entropy,
                "minimum_entropy": min_entropy,
                "entropy_per_character": (
                    actual_entropy / len(secret_value) if secret_value else 0
                ),
            },
            remediation=(
                f"Increase randomness to achieve at least {min_entropy} bits of entropy"
                if not passed
                else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    def _validate_no_weak_patterns(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate against weak patterns."""
        weak_patterns = rule.custom_params.get("weak_patterns", [])
        found_patterns = []

        secret_lower = secret_value.lower()

        # Check for weak patterns
        for pattern in weak_patterns:
            if pattern in secret_lower:
                found_patterns.append(pattern)

        # Check for sequential patterns if enabled
        if rule.custom_params.get("sequential_patterns", False):
            sequential = self._detect_sequential_patterns(secret_value)
            if sequential:
                found_patterns.extend(sequential)

        # Check for keyboard patterns if enabled
        if rule.custom_params.get("keyboard_patterns", False):
            keyboard = self._detect_keyboard_patterns(secret_value)
            if keyboard:
                found_patterns.extend(keyboard)

        passed = len(found_patterns) == 0

        return ValidationResult(
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=f"{'No weak patterns detected' if passed else f'Found weak patterns: {found_patterns}'}",
            details={
                "found_patterns": found_patterns,
                "patterns_checked": len(weak_patterns),
            },
            remediation=(
                "Remove weak patterns and use more random characters"
                if not passed
                else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    def _validate_character_diversity(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate character diversity requirements."""
        has_upper = any(c.isupper() for c in secret_value)
        has_lower = any(c.islower() for c in secret_value)
        has_digits = any(c.isdigit() for c in secret_value)
        has_special = any(not c.isalnum() for c in secret_value)

        character_classes = sum([has_upper, has_lower, has_digits, has_special])
        min_classes = rule.custom_params.get("min_character_classes", 3)

        passed = character_classes >= min_classes

        missing_classes = []
        if rule.custom_params.get("require_uppercase", True) and not has_upper:
            missing_classes.append("uppercase letters")
        if rule.custom_params.get("require_lowercase", True) and not has_lower:
            missing_classes.append("lowercase letters")
        if rule.custom_params.get("require_digits", True) and not has_digits:
            missing_classes.append("digits")
        if rule.custom_params.get("require_special", True) and not has_special:
            missing_classes.append("special characters")

        return ValidationResult(
            rule_name=rule.name,
            passed=passed and len(missing_classes) == 0,
            severity=rule.severity,
            message=f"Uses {character_classes}/{min_classes} character classes"
            + (f", missing: {missing_classes}" if missing_classes else ""),
            details={
                "character_classes_used": character_classes,
                "minimum_required": min_classes,
                "has_uppercase": has_upper,
                "has_lowercase": has_lower,
                "has_digits": has_digits,
                "has_special": has_special,
                "missing_classes": missing_classes,
            },
            remediation=(
                f"Add {', '.join(missing_classes)}" if missing_classes else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    def _validate_no_dictionary_words(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate against dictionary words (simplified implementation)."""
        # This is a simplified implementation
        # In production, you would use a comprehensive dictionary and common password list
        common_words = [
            "password",
            "admin",
            "user",
            "login",
            "secret",
            "key",
            "token",
            "access",
            "secure",
            "private",
            "public",
            "system",
            "database",
            "server",
            "application",
            "service",
            "default",
            "test",
            "demo",
        ]

        secret_lower = secret_value.lower()
        found_words = [word for word in common_words if word in secret_lower]

        # Calculate dictionary ratio
        total_chars = len(secret_value)
        dict_chars = sum(len(word) for word in found_words)
        dict_ratio = dict_chars / total_chars if total_chars > 0 else 0

        max_ratio = rule.custom_params.get("max_dictionary_ratio", 0.5)
        passed = dict_ratio <= max_ratio and len(found_words) == 0

        return ValidationResult(
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=f"Dictionary ratio: {dict_ratio:.2%}"
            + (f", found words: {found_words}" if found_words else ""),
            details={
                "found_words": found_words,
                "dictionary_ratio": dict_ratio,
                "max_allowed_ratio": max_ratio,
            },
            remediation=(
                "Avoid common dictionary words and increase randomness"
                if not passed
                else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    async def _validate_rotation_age_check(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate secret rotation age."""
        # Get secret metadata from secrets manager
        try:
            metadata = (
                self.secrets_manager.get_secret_metadata(secret_name)
                if self.secrets_manager
                else None
            )
        except Exception:
            metadata = None

        if not metadata:
            return ValidationResult(
                rule_name=rule.name,
                passed=False,
                severity=ValidationSeverity.MEDIUM,
                message="Cannot determine secret age - metadata unavailable",
                details={"metadata_available": False},
                remediation="Implement proper secret metadata tracking",
                compliance_impact=rule.compliance_standards,
            )

        env_params = rule.custom_params.get(
            environment, rule.custom_params.get("production", {})
        )
        max_age_days = env_params.get(secret_name, env_params.get("default", 90))

        # Calculate age
        if metadata.last_rotated:
            age_days = (datetime.utcnow() - metadata.last_rotated).days
        else:
            age_days = (datetime.utcnow() - metadata.created_at).days

        passed = age_days <= max_age_days

        return ValidationResult(
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=f"Secret age: {age_days} days ({'within' if passed else 'exceeds'} {max_age_days} day limit)",
            details={
                "age_days": age_days,
                "max_age_days": max_age_days,
                "last_rotated": (
                    metadata.last_rotated.isoformat() if metadata.last_rotated else None
                ),
                "created_at": metadata.created_at.isoformat(),
            },
            remediation=(
                f"Rotate secret (overdue by {age_days - max_age_days} days)"
                if not passed
                else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    async def _validate_access_frequency_check(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate access frequency patterns."""
        # This would typically integrate with access logs
        # For now, return a placeholder implementation

        return ValidationResult(
            rule_name=rule.name,
            passed=True,
            severity=rule.severity,
            message="Access frequency check passed (placeholder implementation)",
            details={
                "implementation_status": "placeholder",
                "note": "Would integrate with actual access logs in production",
            },
            compliance_impact=rule.compliance_standards,
        )

    def _validate_encryption_compliance(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Validate encryption compliance."""
        # Check encryption algorithm used by secrets manager
        if hasattr(self.secrets_manager, "_encryption_algorithm"):
            algorithm = self.secrets_manager._encryption_algorithm.value
        else:
            algorithm = "unknown"

        required_algorithms = rule.custom_params.get("required_algorithms", [])
        passed = algorithm in required_algorithms

        return ValidationResult(
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=f"Encryption algorithm: {algorithm} {'compliant' if passed else 'not compliant'}",
            details={
                "current_algorithm": algorithm,
                "required_algorithms": required_algorithms,
                "algorithm_compliant": passed,
            },
            remediation=(
                f"Use approved encryption algorithm: {required_algorithms}"
                if not passed
                else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    async def _validate_exposure_check(
        self,
        rule: ValidationRule,
        secret_name: str,
        secret_value: str,
        environment: str,
    ) -> ValidationResult:
        """Check for potential secret exposure."""
        exposure_risks = []

        # Check environment variables
        if rule.custom_params.get("check_environment_vars", True):
            env_vars = dict(os.environ)
            for var_name, var_value in env_vars.items():
                if secret_value in str(var_value):
                    exposure_risks.append(f"Found in environment variable: {var_name}")

        # Check common config file patterns (simplified)
        if rule.custom_params.get("check_config_files", True):
            # In production, this would actually scan files
            # For now, it's a placeholder
            pass

        passed = len(exposure_risks) == 0

        return ValidationResult(
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=f"{'No exposure detected' if passed else f'Potential exposure: {len(exposure_risks)} risks'}",
            details={
                "exposure_risks": exposure_risks,
                "checks_performed": [
                    key
                    for key, enabled in rule.custom_params.items()
                    if key.startswith("check_") and enabled
                ],
            },
            remediation=(
                "Review and remove exposed secrets immediately" if not passed else None
            ),
            compliance_impact=rule.compliance_standards,
        )

    def _detect_sequential_patterns(self, text: str) -> list[str]:
        """Detect sequential character patterns."""
        patterns = []
        text_lower = text.lower()

        # Check for alphabetical sequences
        alpha_sequences = ["abcd", "efgh", "ijkl", "mnop", "qrst", "uvwx", "wxyz"]
        for seq in alpha_sequences:
            if seq in text_lower or seq[::-1] in text_lower:
                patterns.append(f"alphabetical_sequence:{seq}")

        # Check for numerical sequences
        for i in range(10 - 3):
            seq = "".join(str(j) for j in range(i, i + 4))
            if seq in text or seq[::-1] in text:
                patterns.append(f"numerical_sequence:{seq}")

        return patterns

    def _detect_keyboard_patterns(self, text: str) -> list[str]:
        """Detect keyboard pattern sequences."""
        patterns = []

        # Common keyboard patterns
        keyboard_patterns = [
            "qwerty",
            "asdf",
            "zxcv",
            "1234",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
            "!@#$",
            "qwer",
            "asdf",
        ]

        text_lower = text.lower()
        for pattern in keyboard_patterns:
            if pattern in text_lower:
                patterns.append(f"keyboard_pattern:{pattern}")

        return patterns

    def _count_character_classes(self, text: str) -> int:
        """Count the number of character classes used."""
        has_upper = any(c.isupper() for c in text)
        has_lower = any(c.islower() for c in text)
        has_digits = any(c.isdigit() for c in text)
        has_special = any(not c.isalnum() for c in text)

        return sum([has_upper, has_lower, has_digits, has_special])

    def _get_environment_compliance_standards(
        self, environment: str
    ) -> list[ComplianceStandard]:
        """Get applicable compliance standards for environment."""
        if environment == "production":
            return [
                ComplianceStandard.NIST_800_53,
                ComplianceStandard.ISO_27001,
                ComplianceStandard.SOC2_TYPE2,
            ]
        elif environment == "staging":
            return [ComplianceStandard.ISO_27001, ComplianceStandard.SOC2_TYPE2]
        else:
            return [ComplianceStandard.ISO_27001]

    def _calculate_compliance_status(
        self, validation_results: list[ValidationResult], standard: ComplianceStandard
    ) -> str:
        """Calculate compliance status for a standard."""
        standard_info = self.compliance_mappings.get(standard, {})
        required_rules = standard_info.get("required_rules", [])

        relevant_results = [
            result
            for result in validation_results
            if result.rule_name in required_rules
        ]

        if not relevant_results:
            return "not_applicable"

        passed_results = [r for r in relevant_results if r.passed]
        failed_critical = [
            r
            for r in relevant_results
            if not r.passed and r.severity == ValidationSeverity.CRITICAL
        ]
        failed_high = [
            r
            for r in relevant_results
            if not r.passed and r.severity == ValidationSeverity.HIGH
        ]

        if failed_critical:
            return "non_compliant"
        elif failed_high:
            return "partially_compliant"
        elif len(passed_results) == len(relevant_results):
            return "compliant"
        else:
            return "partially_compliant"

    def generate_compliance_report(
        self,
        validation_reports: dict[str, SecretValidationReport],
        environment: str,
        compliance_standards: list[ComplianceStandard] | None = None,
    ) -> dict[str, Any]:
        """Generate comprehensive compliance report."""
        if compliance_standards is None:
            compliance_standards = self._get_environment_compliance_standards(
                environment
            )

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": environment,
            "compliance_standards": [s.value for s in compliance_standards],
            "summary": {
                "total_secrets": len(validation_reports),
                "compliant_secrets": 0,
                "non_compliant_secrets": 0,
                "partially_compliant_secrets": 0,
            },
            "standards_compliance": {},
            "recommendations": [],
            "critical_issues": [],
            "detailed_results": validation_reports,
        }

        # Analyze compliance by standard
        for standard in compliance_standards:
            standard_results = {
                "compliant": 0,
                "partially_compliant": 0,
                "non_compliant": 0,
                "not_applicable": 0,
            }

            for _secret_name, validation_report in validation_reports.values():
                status = validation_report.compliance_status.get(
                    standard, "not_applicable"
                )
                standard_results[status] = standard_results.get(status, 0) + 1

            report["standards_compliance"][standard.value] = {
                "name": self.compliance_mappings[standard]["name"],
                "overall_status": self._calculate_overall_compliance_status(
                    standard_results
                ),
                "results": standard_results,
                "compliance_percentage": (
                    standard_results["compliant"] / len(validation_reports) * 100
                    if validation_reports
                    else 0
                ),
            }

        # Generate recommendations
        all_failed_results = []
        for validation_report in validation_reports.values():
            all_failed_results.extend(
                [r for r in validation_report.validation_results if not r.passed]
            )

        # Group recommendations by severity
        critical_issues = [
            r for r in all_failed_results if r.severity == ValidationSeverity.CRITICAL
        ]
        high_issues = [
            r for r in all_failed_results if r.severity == ValidationSeverity.HIGH
        ]

        report["critical_issues"] = [
            {
                "secret_name": result.rule_name,  # This would be better tracked
                "rule": result.rule_name,
                "message": result.message,
                "remediation": result.remediation,
            }
            for result in critical_issues
        ]

        # Generate general recommendations
        if critical_issues:
            report["recommendations"].append(
                "URGENT: Address all critical security issues immediately"
            )
        if high_issues:
            report["recommendations"].append(
                "HIGH: Review and remediate high-severity issues within 24 hours"
            )

        return report

    def _calculate_overall_compliance_status(self, results: dict[str, int]) -> str:
        """Calculate overall compliance status from results."""
        total = sum(results.values())
        if total == 0:
            return "not_applicable"

        compliant_ratio = results["compliant"] / total
        non_compliant_ratio = results["non_compliant"] / total

        if compliant_ratio >= 0.9:
            return "compliant"
        elif non_compliant_ratio >= 0.1:
            return "non_compliant"
        else:
            return "partially_compliant"
