#!/usr/bin/env python3
"""
📋 Compliance Validator

SOC2/ISO27001 compliance validation script for the AI Enhanced PDF Scholar project.
Automated compliance checking and reporting for enterprise security standards.

Agent B1: CI/CD Pipeline Optimization Specialist
Generated: 2025-01-19
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ComplianceStandard(Enum):
    """Supported compliance standards"""

    SOC2_TYPE1 = "soc2_type1"
    SOC2_TYPE2 = "soc2_type2"
    ISO27001 = "iso27001"
    PCI_DSS = "pci_dss"
    GDPR = "gdpr"
    HIPAA = "hipaa"


class ComplianceLevel(Enum):
    """Compliance assessment levels"""

    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"


class Severity(Enum):
    """Finding severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ComplianceFinding:
    """Individual compliance finding"""

    control_id: str
    control_name: str
    requirement: str
    severity: Severity
    status: ComplianceLevel
    evidence: list[str]
    remediation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "control_name": self.control_name,
            "requirement": self.requirement,
            "severity": self.severity.value,
            "status": self.status.value,
            "evidence": self.evidence,
            "remediation": self.remediation,
        }


@dataclass
class ComplianceReport:
    """Compliance assessment report"""

    standard: ComplianceStandard
    assessment_date: datetime
    overall_status: ComplianceLevel
    findings: list[ComplianceFinding]
    summary_stats: dict[str, int]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard": self.standard.value,
            "assessment_date": self.assessment_date.isoformat(),
            "overall_status": self.overall_status.value,
            "findings": [f.to_dict() for f in self.findings],
            "summary_stats": self.summary_stats,
            "recommendations": self.recommendations,
        }


class ComplianceValidator:
    """Main compliance validation engine"""

    def __init__(self, project_root: Path = None) -> None:
        self.project_root = project_root or Path.cwd()
        self.findings: list[ComplianceFinding] = []
        self.recommendations: list[str] = []

        # Load compliance control definitions
        self.controls = self._load_control_definitions()

    def _load_control_definitions(self) -> dict[str, dict]:
        """Load compliance control definitions"""
        controls = {
            # SOC2 Type II Controls
            ComplianceStandard.SOC2_TYPE2: {
                "CC1.1": {
                    "name": "Governance and Risk Management",
                    "requirement": "Management demonstrates a commitment to integrity and ethical values",
                    "checks": ["code_of_conduct", "security_policy", "governance_docs"],
                },
                "CC2.1": {
                    "name": "Communication and Information",
                    "requirement": "Internal communication of information supports the functioning of internal control",
                    "checks": [
                        "documentation",
                        "communication_channels",
                        "incident_response",
                    ],
                },
                "CC3.1": {
                    "name": "Risk Assessment Process",
                    "requirement": "Risk assessment process identifies and analyzes risks",
                    "checks": [
                        "risk_assessment",
                        "threat_modeling",
                        "security_reviews",
                    ],
                },
                "CC4.1": {
                    "name": "Control Activities",
                    "requirement": "Policies and procedures established to achieve objectives",
                    "checks": [
                        "access_controls",
                        "change_management",
                        "deployment_controls",
                    ],
                },
                "CC5.1": {
                    "name": "Monitoring Activities",
                    "requirement": "Ongoing monitoring evaluates internal control effectiveness",
                    "checks": ["monitoring_systems", "alerting", "log_management"],
                },
                "CC6.1": {
                    "name": "Logical and Physical Access",
                    "requirement": "Logical and physical access controls restrict access",
                    "checks": [
                        "authentication",
                        "authorization",
                        "mfa",
                        "physical_security",
                    ],
                },
                "CC7.1": {
                    "name": "System Operations",
                    "requirement": "System operations include procedures for system availability",
                    "checks": [
                        "backup_restore",
                        "disaster_recovery",
                        "capacity_management",
                    ],
                },
                "CC8.1": {
                    "name": "Change Management",
                    "requirement": "Changes to system components are authorized and tested",
                    "checks": [
                        "change_control",
                        "testing_procedures",
                        "rollback_procedures",
                    ],
                },
            },
            # ISO 27001 Controls
            ComplianceStandard.ISO27001: {
                "A.5.1.1": {
                    "name": "Information Security Policies",
                    "requirement": "Set of policies for information security defined and approved",
                    "checks": [
                        "security_policy",
                        "policy_approval",
                        "policy_communication",
                    ],
                },
                "A.6.1.1": {
                    "name": "Information Security Roles",
                    "requirement": "Information security responsibilities defined and allocated",
                    "checks": [
                        "role_definition",
                        "responsibility_matrix",
                        "security_team",
                    ],
                },
                "A.8.1.1": {
                    "name": "Inventory of Assets",
                    "requirement": "Assets associated with information and processing facilities identified",
                    "checks": [
                        "asset_inventory",
                        "asset_classification",
                        "asset_ownership",
                    ],
                },
                "A.9.1.1": {
                    "name": "Access Control Policy",
                    "requirement": "Access control policy established and reviewed",
                    "checks": ["access_policy", "rbac", "access_reviews"],
                },
                "A.12.1.1": {
                    "name": "Documented Procedures",
                    "requirement": "Operating procedures documented and made available",
                    "checks": [
                        "procedures_documented",
                        "procedures_updated",
                        "procedures_accessible",
                    ],
                },
                "A.14.2.1": {
                    "name": "Secure Development Policy",
                    "requirement": "Rules for development of software and systems established",
                    "checks": ["secure_coding", "code_review", "security_testing"],
                },
                "A.16.1.1": {
                    "name": "Incident Response",
                    "requirement": "Responsibilities and procedures established for incident management",
                    "checks": [
                        "incident_procedures",
                        "incident_team",
                        "incident_reporting",
                    ],
                },
                "A.18.1.1": {
                    "name": "Legal Requirements",
                    "requirement": "Legal, statutory, regulatory requirements identified",
                    "checks": [
                        "legal_compliance",
                        "regulatory_mapping",
                        "compliance_monitoring",
                    ],
                },
            },
        }

        return controls

    def validate_compliance(self, standard: ComplianceStandard) -> ComplianceReport:
        """Perform comprehensive compliance validation"""
        logger.info(f"🔍 Starting compliance validation for {standard.value}")

        self.findings = []
        self.recommendations = []

        # Get controls for the specified standard
        if standard not in self.controls:
            raise ValueError(f"Unsupported compliance standard: {standard}")

        standard_controls = self.controls[standard]

        # Validate each control
        for control_id, control_info in standard_controls.items():
            logger.info(f"📋 Validating control {control_id}: {control_info['name']}")

            finding = self._validate_control(
                control_id,
                control_info["name"],
                control_info["requirement"],
                control_info["checks"],
                standard,
            )

            self.findings.append(finding)

        # Calculate overall compliance status
        overall_status = self._calculate_overall_status()

        # Generate summary statistics
        summary_stats = self._generate_summary_stats()

        # Generate recommendations
        self._generate_recommendations(standard)

        report = ComplianceReport(
            standard=standard,
            assessment_date=datetime.now(timezone.utc),
            overall_status=overall_status,
            findings=self.findings,
            summary_stats=summary_stats,
            recommendations=self.recommendations,
        )

        logger.info(
            f"✅ Compliance validation completed. Overall status: {overall_status.value}"
        )
        return report

    def _validate_control(
        self,
        control_id: str,
        control_name: str,
        requirement: str,
        checks: list[str],
        standard: ComplianceStandard,
    ) -> ComplianceFinding:
        """Validate a specific compliance control"""

        evidence = []
        status = ComplianceLevel.COMPLIANT
        severity = Severity.MEDIUM
        remediation = None

        # Execute checks based on control requirements
        for check in checks:
            check_result = self._execute_check(check)

            if check_result["passed"]:
                evidence.extend(check_result["evidence"])
            else:
                evidence.extend(check_result["evidence"])
                if status == ComplianceLevel.COMPLIANT:
                    status = ComplianceLevel.PARTIAL

                # Determine severity based on check type
                if check in [
                    "authentication",
                    "authorization",
                    "security_policy",
                    "incident_response",
                ]:
                    severity = Severity.HIGH
                elif check in ["mfa", "encryption", "access_controls"]:
                    severity = Severity.CRITICAL

        # If critical checks failed, mark as non-compliant
        critical_checks = ["security_policy", "access_controls", "authentication"]
        failed_critical = any(
            not self._execute_check(check)["passed"]
            for check in checks
            if check in critical_checks
        )

        if failed_critical:
            status = ComplianceLevel.NON_COMPLIANT
            severity = Severity.CRITICAL
            remediation = self._generate_remediation(control_id, checks, standard)
        elif status == ComplianceLevel.PARTIAL:
            remediation = self._generate_remediation(control_id, checks, standard)

        return ComplianceFinding(
            control_id=control_id,
            control_name=control_name,
            requirement=requirement,
            severity=severity,
            status=status,
            evidence=evidence,
            remediation=remediation,
        )

    def _execute_check(self, check_type: str) -> dict[str, Any]:
        """Execute a specific compliance check"""

        if check_type == "security_policy":
            return self._check_security_policy()
        elif check_type == "code_of_conduct":
            return self._check_code_of_conduct()
        elif check_type == "documentation":
            return self._check_documentation()
        elif check_type == "access_controls":
            return self._check_access_controls()
        elif check_type == "authentication":
            return self._check_authentication()
        elif check_type == "authorization":
            return self._check_authorization()
        elif check_type == "mfa":
            return self._check_mfa()
        elif check_type == "encryption":
            return self._check_encryption()
        elif check_type == "monitoring_systems":
            return self._check_monitoring()
        elif check_type == "log_management":
            return self._check_logging()
        elif check_type == "backup_restore":
            return self._check_backup_procedures()
        elif check_type == "incident_response":
            return self._check_incident_response()
        elif check_type == "change_management":
            return self._check_change_management()
        elif check_type == "secure_coding":
            return self._check_secure_coding()
        elif check_type == "code_review":
            return self._check_code_review_process()
        elif check_type == "security_testing":
            return self._check_security_testing()
        else:
            return {"passed": False, "evidence": [f"Unknown check type: {check_type}"]}

    def _check_security_policy(self) -> dict[str, Any]:
        """Check for security policy documentation"""
        policy_files = [
            "SECURITY.md",
            ".github/SECURITY.md",
            "docs/SECURITY.md",
            "security-policy.md",
        ]

        evidence = []
        found_policy = False

        for policy_file in policy_files:
            file_path = self.project_root / policy_file
            if file_path.exists():
                evidence.append(f"Security policy found: {policy_file}")
                found_policy = True

                # Check if policy is comprehensive
                content = file_path.read_text().lower()
                required_sections = [
                    "reporting",
                    "vulnerabilities",
                    "response",
                    "disclosure",
                ]
                missing_sections = [s for s in required_sections if s not in content]

                if missing_sections:
                    evidence.append(f"Policy missing sections: {missing_sections}")
                else:
                    evidence.append("Security policy appears comprehensive")

        if not found_policy:
            evidence.append("No security policy documentation found")

        return {"passed": found_policy, "evidence": evidence}

    def _check_code_of_conduct(self) -> dict[str, Any]:
        """Check for code of conduct"""
        conduct_files = [
            "CODE_OF_CONDUCT.md",
            ".github/CODE_OF_CONDUCT.md",
            "docs/CODE_OF_CONDUCT.md",
        ]

        evidence = []
        found_conduct = False

        for conduct_file in conduct_files:
            file_path = self.project_root / conduct_file
            if file_path.exists():
                evidence.append(f"Code of conduct found: {conduct_file}")
                found_conduct = True

        if not found_conduct:
            evidence.append("No code of conduct found")

        return {"passed": found_conduct, "evidence": evidence}

    def _check_documentation(self) -> dict[str, Any]:
        """Check for adequate documentation"""
        required_docs = {
            "README.md": "Project documentation",
            "API_ENDPOINTS.md": "API documentation",
            "TECHNICAL_DESIGN.md": "Technical design documentation",
            "PROJECT_DOCS.md": "Project documentation",
        }

        evidence = []
        found_docs = 0

        for doc_file, description in required_docs.items():
            file_path = self.project_root / doc_file
            if file_path.exists():
                evidence.append(f"Found {description}: {doc_file}")
                found_docs += 1
            else:
                evidence.append(f"Missing {description}: {doc_file}")

        # At least 75% of required docs should exist
        docs_percentage = (found_docs / len(required_docs)) * 100
        passed = docs_percentage >= 75

        evidence.append(f"Documentation coverage: {docs_percentage:.1f}%")

        return {"passed": passed, "evidence": evidence}

    def _check_access_controls(self) -> dict[str, Any]:
        """Check for access control implementation"""
        evidence = []

        # Check for authentication/authorization code
        auth_files = list(self.project_root.glob("**/auth/*.py"))
        auth_files.extend(list(self.project_root.glob("**/authentication.py")))
        auth_files.extend(list(self.project_root.glob("**/authorization.py")))

        if auth_files:
            evidence.append(
                f"Found {len(auth_files)} authentication/authorization files"
            )

            # Check for RBAC implementation
            rbac_found = any(
                "rbac" in str(f).lower() or "role" in str(f).lower() for f in auth_files
            )
            if rbac_found:
                evidence.append("Role-based access control (RBAC) implementation found")
        else:
            evidence.append("No authentication/authorization files found")

        # Check for middleware
        middleware_files = list(self.project_root.glob("**/middleware/*.py"))
        if middleware_files:
            evidence.append(f"Found {len(middleware_files)} middleware files")

        passed = len(auth_files) > 0
        return {"passed": passed, "evidence": evidence}

    def _check_authentication(self) -> dict[str, Any]:
        """Check for authentication implementation"""
        evidence = []

        # Check for JWT or session handling
        auth_patterns = ["jwt", "session", "token", "authentication"]
        auth_implementations = []

        for pattern in ["**/*.py", "**/*.ts", "**/*.js"]:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file() and not any(
                    exclude in str(file_path)
                    for exclude in ["node_modules", "__pycache__", ".git"]
                ):
                    try:
                        content = file_path.read_text(
                            encoding="utf-8", errors="ignore"
                        ).lower()
                        found_patterns = [p for p in auth_patterns if p in content]
                        if found_patterns:
                            auth_implementations.extend(found_patterns)
                    except Exception:
                        continue

        unique_implementations = list(set(auth_implementations))
        if unique_implementations:
            evidence.append(f"Authentication patterns found: {unique_implementations}")
        else:
            evidence.append("No authentication implementation patterns found")

        passed = len(unique_implementations) > 0
        return {"passed": passed, "evidence": evidence}

    def _check_authorization(self) -> dict[str, Any]:
        """Check for authorization controls"""
        evidence = []

        # Look for authorization decorators, middleware, or functions
        auth_patterns = [
            "@require",
            "authorize",
            "permission",
            "role",
            "access_control",
        ]
        found_patterns = []

        for pattern in ["**/*.py", "**/*.ts", "**/*.js"]:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file() and not any(
                    exclude in str(file_path)
                    for exclude in ["node_modules", "__pycache__", ".git"]
                ):
                    try:
                        content = file_path.read_text(
                            encoding="utf-8", errors="ignore"
                        ).lower()
                        file_patterns = [p for p in auth_patterns if p in content]
                        if file_patterns:
                            found_patterns.extend(file_patterns)
                    except Exception:
                        continue

        unique_patterns = list(set(found_patterns))
        if unique_patterns:
            evidence.append(f"Authorization patterns found: {unique_patterns}")
        else:
            evidence.append("No authorization implementation patterns found")

        passed = len(unique_patterns) > 0
        return {"passed": passed, "evidence": evidence}

    def _check_mfa(self) -> dict[str, Any]:
        """Check for multi-factor authentication"""
        evidence = []

        # Check for MFA patterns in code
        mfa_patterns = ["mfa", "2fa", "two_factor", "totp", "authenticator"]
        found_mfa = []

        for pattern in ["**/*.py", "**/*.ts", "**/*.js"]:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(
                            encoding="utf-8", errors="ignore"
                        ).lower()
                        file_mfa = [p for p in mfa_patterns if p in content]
                        if file_mfa:
                            found_mfa.extend(file_mfa)
                    except Exception:
                        continue

        if found_mfa:
            evidence.append(
                f"MFA implementation indicators found: {list(set(found_mfa))}"
            )
            passed = True
        else:
            evidence.append("No MFA implementation indicators found")
            passed = False

        return {"passed": passed, "evidence": evidence}

    def _check_encryption(self) -> dict[str, Any]:
        """Check for encryption implementation"""
        evidence = []

        # Check for encryption services and patterns
        encryption_files = list(self.project_root.glob("**/encryption*.py"))
        if encryption_files:
            evidence.append(f"Found {len(encryption_files)} encryption service files")

        # Check for encryption patterns
        crypto_patterns = ["encrypt", "decrypt", "crypto", "cipher", "hash"]
        found_crypto = []

        for pattern in ["**/*.py"]:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file() and "encryption" in str(file_path):
                    try:
                        content = file_path.read_text(
                            encoding="utf-8", errors="ignore"
                        ).lower()
                        file_crypto = [p for p in crypto_patterns if p in content]
                        if file_crypto:
                            found_crypto.extend(file_crypto)
                    except Exception:
                        continue

        if found_crypto or encryption_files:
            evidence.append(f"Encryption patterns found: {list(set(found_crypto))}")
            passed = True
        else:
            evidence.append("No encryption implementation found")
            passed = False

        return {"passed": passed, "evidence": evidence}

    def _check_monitoring(self) -> dict[str, Any]:
        """Check for monitoring systems"""
        evidence = []

        # Check for monitoring services
        monitoring_files = list(self.project_root.glob("**/monitoring*.py"))
        monitoring_files.extend(list(self.project_root.glob("**/metrics*.py")))

        if monitoring_files:
            evidence.append(f"Found {len(monitoring_files)} monitoring service files")
            passed = True
        else:
            evidence.append("No monitoring service files found")
            passed = False

        return {"passed": passed, "evidence": evidence}

    def _check_logging(self) -> dict[str, Any]:
        """Check for logging implementation"""
        evidence = []

        # Check for logging services
        logging_files = list(self.project_root.glob("**/logging*.py"))
        logging_files.extend(list(self.project_root.glob("**/log*.py")))

        if logging_files:
            evidence.append(f"Found {len(logging_files)} logging service files")

        # Check for logging usage in code
        logging_usage = 0
        for file_path in self.project_root.glob("**/*.py"):
            if file_path.is_file() and not any(
                exclude in str(file_path) for exclude in ["__pycache__", ".git"]
            ):
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if "import logging" in content or "logger." in content:
                        logging_usage += 1
                except Exception:
                    continue

        evidence.append(f"Files using logging: {logging_usage}")
        passed = logging_usage > 0 or len(logging_files) > 0

        return {"passed": passed, "evidence": evidence}

    def _check_backup_procedures(self) -> dict[str, Any]:
        """Check for backup and recovery procedures"""
        evidence = []

        # Check for backup-related documentation
        backup_docs = ["backup", "recovery", "disaster"]
        found_backup_docs = []

        for doc_pattern in ["**/*.md", "**/*.txt"]:
            for doc_file in self.project_root.glob(doc_pattern):
                if doc_file.is_file():
                    try:
                        content = doc_file.read_text(
                            encoding="utf-8", errors="ignore"
                        ).lower()
                        if any(term in content for term in backup_docs):
                            found_backup_docs.append(str(doc_file.name))
                    except Exception:
                        continue

        if found_backup_docs:
            evidence.append(f"Backup documentation found: {found_backup_docs}")
            passed = True
        else:
            evidence.append("No backup/recovery documentation found")
            passed = False

        return {"passed": passed, "evidence": evidence}

    def _check_incident_response(self) -> dict[str, Any]:
        """Check for incident response procedures"""
        evidence = []

        # Check for incident response documentation
        incident_files = [
            "INCIDENT_RESPONSE.md",
            "docs/incident-response.md",
            "SECURITY.md",
        ]

        found_incident = False
        for incident_file in incident_files:
            file_path = self.project_root / incident_file
            if file_path.exists():
                evidence.append(f"Incident response documentation: {incident_file}")
                found_incident = True

        if not found_incident:
            evidence.append("No incident response documentation found")

        return {"passed": found_incident, "evidence": evidence}

    def _check_change_management(self) -> dict[str, Any]:
        """Check for change management processes"""
        evidence = []

        # Check for GitHub workflows (change management automation)
        workflow_files = list(self.project_root.glob(".github/workflows/*.yml"))
        workflow_files.extend(list(self.project_root.glob(".github/workflows/*.yaml")))

        if workflow_files:
            evidence.append(f"Found {len(workflow_files)} CI/CD workflow files")

            # Check for specific change management workflows
            change_mgmt_workflows = []
            for workflow_file in workflow_files:
                if any(
                    term in str(workflow_file).lower()
                    for term in ["deploy", "release", "quality", "security"]
                ):
                    change_mgmt_workflows.append(workflow_file.name)

            if change_mgmt_workflows:
                evidence.append(f"Change management workflows: {change_mgmt_workflows}")
        else:
            evidence.append("No CI/CD workflows found")

        # Check for pull request templates
        pr_templates = list(self.project_root.glob(".github/pull_request_template.md"))
        pr_templates.extend(
            list(self.project_root.glob(".github/PULL_REQUEST_TEMPLATE.md"))
        )

        if pr_templates:
            evidence.append("Pull request template found")

        passed = len(workflow_files) > 0
        return {"passed": passed, "evidence": evidence}

    def _check_secure_coding(self) -> dict[str, Any]:
        """Check for secure coding practices"""
        evidence = []

        # Check for security linting tools
        security_configs = [
            ".bandit",
            "bandit.yml",
            ".safety-policy.json",
            "pyproject.toml",  # May contain bandit config
        ]

        found_security_tools = []
        for config_file in security_configs:
            file_path = self.project_root / config_file
            if file_path.exists():
                found_security_tools.append(config_file)

        if found_security_tools:
            evidence.append(
                f"Security tool configurations found: {found_security_tools}"
            )
        else:
            evidence.append("No security tool configurations found")

        # Check for requirements files with security tools
        req_files = list(self.project_root.glob("requirements*.txt"))
        security_tools_in_reqs = []

        for req_file in req_files:
            try:
                content = req_file.read_text()
                if any(
                    tool in content.lower()
                    for tool in ["bandit", "safety", "pip-audit"]
                ):
                    security_tools_in_reqs.append(req_file.name)
            except Exception:
                continue

        if security_tools_in_reqs:
            evidence.append(f"Security tools in requirements: {security_tools_in_reqs}")

        passed = len(found_security_tools) > 0 or len(security_tools_in_reqs) > 0
        return {"passed": passed, "evidence": evidence}

    def _check_code_review_process(self) -> dict[str, Any]:
        """Check for code review processes"""
        evidence = []

        # Check for branch protection rules indication
        github_files = list(self.project_root.glob(".github/**/*"))

        if github_files:
            evidence.append(f"GitHub configuration files found: {len(github_files)}")

        # Check for CODEOWNERS file
        codeowners_files = list(self.project_root.glob(".github/CODEOWNERS"))
        codeowners_files.extend(list(self.project_root.glob("CODEOWNERS")))

        if codeowners_files:
            evidence.append("CODEOWNERS file found for mandatory reviews")

        # Check for pull request templates
        pr_templates = list(self.project_root.glob(".github/**/pull_request_template*"))
        if pr_templates:
            evidence.append("Pull request template found")

        passed = len(codeowners_files) > 0 or len(pr_templates) > 0
        return {"passed": passed, "evidence": evidence}

    def _check_security_testing(self) -> dict[str, Any]:
        """Check for security testing implementation"""
        evidence = []

        # Check for security test workflows
        security_workflows = []
        for workflow_file in self.project_root.glob(".github/workflows/*.yml"):
            if any(
                term in str(workflow_file).lower()
                for term in ["security", "scan", "audit"]
            ):
                security_workflows.append(workflow_file.name)

        if security_workflows:
            evidence.append(f"Security testing workflows: {security_workflows}")

        # Check for security test files
        security_tests = list(self.project_root.glob("**/test*security*.py"))
        security_tests.extend(list(self.project_root.glob("**/security*test*.py")))

        if security_tests:
            evidence.append(f"Security test files: {len(security_tests)}")

        passed = len(security_workflows) > 0 or len(security_tests) > 0
        return {"passed": passed, "evidence": evidence}

    def _calculate_overall_status(self) -> ComplianceLevel:
        """Calculate overall compliance status"""
        if not self.findings:
            return ComplianceLevel.NOT_APPLICABLE

        compliant_count = sum(
            1 for f in self.findings if f.status == ComplianceLevel.COMPLIANT
        )
        non_compliant_count = sum(
            1 for f in self.findings if f.status == ComplianceLevel.NON_COMPLIANT
        )

        total_findings = len(self.findings)
        compliant_percentage = (compliant_count / total_findings) * 100

        # Determine overall status
        if non_compliant_count > 0:
            return ComplianceLevel.NON_COMPLIANT
        elif compliant_percentage >= 80:
            return ComplianceLevel.COMPLIANT
        else:
            return ComplianceLevel.PARTIAL

    def _generate_summary_stats(self) -> dict[str, int]:
        """Generate summary statistics"""
        stats = {
            "total_controls": len(self.findings),
            "compliant": sum(
                1 for f in self.findings if f.status == ComplianceLevel.COMPLIANT
            ),
            "partial": sum(
                1 for f in self.findings if f.status == ComplianceLevel.PARTIAL
            ),
            "non_compliant": sum(
                1 for f in self.findings if f.status == ComplianceLevel.NON_COMPLIANT
            ),
            "not_applicable": sum(
                1 for f in self.findings if f.status == ComplianceLevel.NOT_APPLICABLE
            ),
            "critical_findings": sum(
                1 for f in self.findings if f.severity == Severity.CRITICAL
            ),
            "high_findings": sum(
                1 for f in self.findings if f.severity == Severity.HIGH
            ),
            "medium_findings": sum(
                1 for f in self.findings if f.severity == Severity.MEDIUM
            ),
            "low_findings": sum(1 for f in self.findings if f.severity == Severity.LOW),
        }

        return stats

    def _generate_recommendations(self, standard: ComplianceStandard) -> None:
        """Generate compliance recommendations"""

        # General recommendations
        self.recommendations.extend(
            [
                "Implement regular compliance assessments and monitoring",
                "Maintain up-to-date documentation for all security policies",
                "Establish incident response procedures and contact information",
                "Conduct regular security awareness training for development team",
                "Implement automated security testing in CI/CD pipeline",
            ]
        )

        # Standard-specific recommendations
        if standard == ComplianceStandard.SOC2_TYPE2:
            self.recommendations.extend(
                [
                    "Document risk assessment procedures and update annually",
                    "Implement continuous monitoring for system availability",
                    "Establish formal change management procedures with approval workflows",
                    "Maintain audit logs for all system access and changes",
                ]
            )
        elif standard == ComplianceStandard.ISO27001:
            self.recommendations.extend(
                [
                    "Create and maintain information asset inventory",
                    "Implement business continuity and disaster recovery plans",
                    "Establish supplier security assessment procedures",
                    "Conduct regular management reviews of information security",
                ]
            )

        # Recommendations based on findings
        critical_findings = [
            f for f in self.findings if f.severity == Severity.CRITICAL
        ]
        if critical_findings:
            self.recommendations.insert(
                0,
                f"Address {len(critical_findings)} critical compliance gaps immediately",
            )

        non_compliant = [
            f for f in self.findings if f.status == ComplianceLevel.NON_COMPLIANT
        ]
        if non_compliant:
            self.recommendations.append(
                f"Prioritize remediation of {len(non_compliant)} non-compliant controls"
            )

    def _generate_remediation(
        self, control_id: str, checks: list[str], standard: ComplianceStandard
    ) -> str:
        """Generate specific remediation guidance"""

        remediation_map = {
            "security_policy": "Create and maintain comprehensive security policy documentation",
            "access_controls": "Implement role-based access control (RBAC) system",
            "authentication": "Implement strong authentication mechanisms with secure session management",
            "authorization": "Add authorization checks to all protected endpoints and resources",
            "mfa": "Implement multi-factor authentication for administrative access",
            "encryption": "Implement encryption for data at rest and in transit",
            "monitoring_systems": "Deploy comprehensive monitoring and alerting systems",
            "log_management": "Implement centralized logging with appropriate retention policies",
            "incident_response": "Develop and document incident response procedures",
            "change_management": "Implement formal change management process with approval workflows",
            "secure_coding": "Integrate security scanning tools into development workflow",
            "code_review": "Establish mandatory code review process with security focus",
            "backup_restore": "Document and test backup and recovery procedures",
        }

        applicable_remediations = [
            remediation_map.get(check, f"Address {check} requirements")
            for check in checks
        ]

        return "; ".join(applicable_remediations[:3])  # Top 3 recommendations

    def export_report(
        self,
        report: ComplianceReport,
        output_format: str = "json",
        output_file: Path = None,
    ) -> None:
        """Export compliance report in specified format"""

        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = (
                self.project_root
                / f"compliance_report_{report.standard.value}_{timestamp}.{output_format}"
            )

        if output_format == "json":
            with open(output_file, "w") as f:
                json.dump(report.to_dict(), f, indent=2)
        elif output_format == "html":
            self._export_html_report(report, output_file)
        elif output_format == "csv":
            self._export_csv_report(report, output_file)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

        logger.info(f"📊 Compliance report exported to {output_file}")

    def _export_html_report(self, report: ComplianceReport, output_file: Path) -> None:
        """Export HTML compliance report"""

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compliance Report - {report.standard.value.upper()}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .status-badge {{ display: inline-block; padding: 5px 10px; border-radius: 4px; color: white; font-weight: bold; }}
        .compliant {{ background-color: #28a745; }}
        .partial {{ background-color: #ffc107; color: black; }}
        .non-compliant {{ background-color: #dc3545; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .findings {{ margin-bottom: 30px; }}
        .finding {{ border: 1px solid #ddd; margin-bottom: 15px; border-radius: 8px; overflow: hidden; }}
        .finding-header {{ padding: 15px; background-color: #f8f9fa; font-weight: bold; }}
        .finding-content {{ padding: 15px; }}
        .severity-critical {{ border-left: 4px solid #dc3545; }}
        .severity-high {{ border-left: 4px solid #fd7e14; }}
        .severity-medium {{ border-left: 4px solid #ffc107; }}
        .severity-low {{ border-left: 4px solid #28a745; }}
        .recommendations {{ background-color: #e7f3ff; padding: 20px; border-radius: 8px; }}
        .recommendations h3 {{ margin-top: 0; }}
        .recommendations ul {{ margin-bottom: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Compliance Assessment Report</h1>
            <h2>{report.standard.value.upper()} Standard</h2>
            <p><strong>Assessment Date:</strong> {report.assessment_date.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <span class="status-badge {report.overall_status.value}">{report.overall_status.value.upper()}</span>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>Total Controls</h3>
                <p style="font-size: 2em; margin: 0;">{report.summary_stats['total_controls']}</p>
            </div>
            <div class="stat-card">
                <h3>Compliant</h3>
                <p style="font-size: 2em; margin: 0; color: #28a745;">{report.summary_stats['compliant']}</p>
            </div>
            <div class="stat-card">
                <h3>Non-Compliant</h3>
                <p style="font-size: 2em; margin: 0; color: #dc3545;">{report.summary_stats['non_compliant']}</p>
            </div>
            <div class="stat-card">
                <h3>Critical Findings</h3>
                <p style="font-size: 2em; margin: 0; color: #dc3545;">{report.summary_stats['critical_findings']}</p>
            </div>
        </div>

        <div class="findings">
            <h3>Detailed Findings</h3>
        """

        for finding in report.findings:
            status_class = finding.status.value.replace("_", "-")
            severity_class = f"severity-{finding.severity.value}"

            html_content += f"""
            <div class="finding {severity_class}">
                <div class="finding-header">
                    {finding.control_id}: {finding.control_name}
                    <span class="status-badge {status_class}" style="float: right; margin-left: 10px;">{finding.status.value.upper()}</span>
                    <span style="float: right; background-color: #{self._get_severity_color(finding.severity)}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{finding.severity.value.upper()}</span>
                </div>
                <div class="finding-content">
                    <p><strong>Requirement:</strong> {finding.requirement}</p>
                    <p><strong>Evidence:</strong></p>
                    <ul>
                        {''.join(f'<li>{evidence}</li>' for evidence in finding.evidence)}
                    </ul>
                    {f'<p><strong>Remediation:</strong> {finding.remediation}</p>' if finding.remediation else ''}
                </div>
            </div>
            """

        html_content += f"""
        </div>

        <div class="recommendations">
            <h3>Recommendations</h3>
            <ul>
                {''.join(f'<li>{rec}</li>' for rec in report.recommendations)}
            </ul>
        </div>

        <div style="margin-top: 30px; text-align: center; color: #6c757d; font-size: 0.9em;">
            <p>Generated by AI Enhanced PDF Scholar Compliance Validator</p>
            <p>Agent B1: CI/CD Pipeline Optimization Specialist</p>
        </div>
    </div>
</body>
</html>
        """

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _export_csv_report(self, report: ComplianceReport, output_file: Path) -> None:
        """Export CSV compliance report"""
        import csv

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(
                [
                    "Control ID",
                    "Control Name",
                    "Requirement",
                    "Status",
                    "Severity",
                    "Evidence Count",
                    "Has Remediation",
                    "Evidence Summary",
                ]
            )

            # Write findings
            for finding in report.findings:
                writer.writerow(
                    [
                        finding.control_id,
                        finding.control_name,
                        finding.requirement,
                        finding.status.value,
                        finding.severity.value,
                        len(finding.evidence),
                        "Yes" if finding.remediation else "No",
                        "; ".join(finding.evidence[:2]),  # First 2 pieces of evidence
                    ]
                )

    def _get_severity_color(self, severity: Severity) -> str:
        """Get color code for severity level"""
        colors = {
            Severity.CRITICAL: "dc3545",
            Severity.HIGH: "fd7e14",
            Severity.MEDIUM: "ffc107",
            Severity.LOW: "28a745",
            Severity.INFO: "17a2b8",
        }
        return colors.get(severity, "6c757d")


async def main() -> None:
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="📋 Compliance Validator for AI Enhanced PDF Scholar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run SOC2 Type II compliance assessment
  python compliance_validator.py validate --standard soc2_type2 --output-format html

  # Run ISO 27001 assessment with JSON output
  python compliance_validator.py validate --standard iso27001 --output-format json --output-file iso27001_report.json

  # Run all supported standards
  python compliance_validator.py validate-all --output-dir compliance_reports
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Run compliance validation"
    )
    validate_parser.add_argument(
        "--standard",
        type=str,
        required=True,
        choices=["soc2_type1", "soc2_type2", "iso27001", "pci_dss", "gdpr"],
        help="Compliance standard to validate against",
    )
    validate_parser.add_argument(
        "--output-format",
        type=str,
        default="json",
        choices=["json", "html", "csv"],
        help="Output report format",
    )
    validate_parser.add_argument(
        "--output-file",
        type=str,
        help="Output file path (auto-generated if not specified)",
    )
    validate_parser.add_argument(
        "--project-root",
        type=str,
        help="Project root directory (default: current directory)",
    )

    # Validate all command
    validate_all_parser = subparsers.add_parser(
        "validate-all", help="Run all compliance validations"
    )
    validate_all_parser.add_argument(
        "--output-dir",
        type=str,
        default="compliance_reports",
        help="Output directory for reports",
    )
    validate_all_parser.add_argument(
        "--output-format",
        type=str,
        default="html",
        choices=["json", "html", "csv"],
        help="Output report format",
    )

    # Summary command
    summary_parser = subparsers.add_parser(
        "summary", help="Generate compliance summary"
    )
    summary_parser.add_argument(
        "--standard",
        type=str,
        choices=["soc2_type1", "soc2_type2", "iso27001", "pci_dss", "gdpr"],
        help="Specific standard to summarize (optional)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize validator
    project_root = (
        Path(args.project_root)
        if hasattr(args, "project_root") and args.project_root
        else Path.cwd()
    )
    validator = ComplianceValidator(project_root)

    try:
        if args.command == "validate":
            standard = ComplianceStandard(args.standard)

            print(f"🔍 Running {standard.value.upper()} compliance validation...")
            report = validator.validate_compliance(standard)

            # Export report
            output_file = Path(args.output_file) if args.output_file else None
            validator.export_report(report, args.output_format, output_file)

            # Print summary
            print("\n📊 Compliance Assessment Summary:")
            print(f"  Standard: {report.standard.value.upper()}")
            print(f"  Overall Status: {report.overall_status.value.upper()}")
            print(f"  Total Controls: {report.summary_stats['total_controls']}")
            print(f"  Compliant: {report.summary_stats['compliant']}")
            print(f"  Non-Compliant: {report.summary_stats['non_compliant']}")
            print(f"  Critical Findings: {report.summary_stats['critical_findings']}")

            if report.overall_status == ComplianceLevel.NON_COMPLIANT:
                print("\n❌ Compliance validation failed")
                sys.exit(1)
            else:
                print("\n✅ Compliance validation completed")

        elif args.command == "validate-all":
            output_dir = Path(args.output_dir)
            output_dir.mkdir(exist_ok=True)

            standards = [ComplianceStandard.SOC2_TYPE2, ComplianceStandard.ISO27001]
            reports = []

            for standard in standards:
                print(f"🔍 Running {standard.value.upper()} validation...")
                report = validator.validate_compliance(standard)

                output_file = (
                    output_dir
                    / f"compliance_report_{standard.value}.{args.output_format}"
                )
                validator.export_report(report, args.output_format, output_file)

                reports.append(report)
                print(f"✅ {standard.value.upper()} report saved to {output_file}")

            # Generate combined summary
            print("\n📊 Combined Compliance Summary:")
            for report in reports:
                status_icon = (
                    "✅" if report.overall_status == ComplianceLevel.COMPLIANT else "❌"
                )
                print(
                    f"  {status_icon} {report.standard.value.upper()}: {report.overall_status.value}"
                )

        elif args.command == "summary":
            print("📋 Compliance Validation Summary")
            print("===============================")

            if args.standard:
                standard = ComplianceStandard(args.standard)
                report = validator.validate_compliance(standard)

                print(f"\n{standard.value.upper()} Compliance:")
                print(f"  Status: {report.overall_status.value}")
                print(
                    f"  Controls: {report.summary_stats['compliant']}/{report.summary_stats['total_controls']} compliant"
                )
                print(f"  Critical Issues: {report.summary_stats['critical_findings']}")
            else:
                print("\nSupported Standards:")
                print("  - SOC2 Type I & Type II")
                print("  - ISO 27001")
                print("  - PCI DSS (partial)")
                print("  - GDPR (privacy controls)")
                print("\nUse --standard to validate specific compliance framework")

    except Exception as e:
        logger.error(f"❌ Compliance validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
