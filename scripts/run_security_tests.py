#!/usr/bin/env python3
"""
Security Testing Automation Script
Orchestrates and runs comprehensive security testing suite.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.security.test_penetration_testing import (
    PenetrationTestConfig,
    PenetrationTestRunner,
)
from tests.security.test_security_suite import SecurityTestConfig, SecurityTestRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SecurityTestOrchestrator:
    """Orchestrates all security testing activities."""

    def __init__(self, target_url: str, output_dir: str = "security_reports") -> None:
        self.target_url = target_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    async def run_comprehensive_security_assessment(self) -> dict[str, Any]:
        """Run complete security assessment including all test suites."""
        logger.info(f"Starting comprehensive security assessment for {self.target_url}")

        start_time = datetime.utcnow()

        # Initialize test configurations
        security_config = SecurityTestConfig()
        security_config.base_url = self.target_url
        security_config.api_base = f"{self.target_url}/api/v1"

        pentest_config = PenetrationTestConfig()
        pentest_config.target_url = self.target_url

        # Results container
        assessment_results = {
            "target_url": self.target_url,
            "test_timestamp": start_time.isoformat(),
            "owasp_security_tests": {},
            "penetration_tests": {},
            "combined_analysis": {},
        }

        try:
            # Run OWASP security tests
            logger.info("Running OWASP security test suite...")
            security_runner = SecurityTestRunner(security_config)
            security_results = await security_runner.run_all_tests()
            assessment_results["owasp_security_tests"] = security_results

            # Run penetration tests
            logger.info("Running penetration test suite...")
            pentest_runner = PenetrationTestRunner(pentest_config)
            pentest_results = await pentest_runner.run_full_pentest()
            assessment_results["penetration_tests"] = pentest_results

            # Generate combined analysis
            assessment_results["combined_analysis"] = self._generate_combined_analysis(
                security_results, pentest_results, start_time
            )

        except Exception as e:
            logger.error(f"Security assessment failed: {e}")
            assessment_results["error"] = str(e)

        # Save results
        await self._save_assessment_results(assessment_results)

        logger.info("Comprehensive security assessment completed")
        return assessment_results

    def _generate_combined_analysis(
        self,
        security_results: dict[str, Any],
        pentest_results: dict[str, Any],
        start_time: datetime,
    ) -> dict[str, Any]:
        """Generate combined analysis from all test results."""

        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()

        # Extract vulnerabilities from both test suites
        security_vulns = security_results.get("all_vulnerabilities", [])
        pentest_findings = pentest_results.get("findings_summary", {}).get(
            "all_findings", []
        )

        # Combine and deduplicate vulnerabilities
        all_vulnerabilities = security_vulns + pentest_findings
        unique_vulnerabilities = self._deduplicate_vulnerabilities(all_vulnerabilities)

        # Calculate combined severity counts
        severity_counts = {
            "critical": len(
                [v for v in unique_vulnerabilities if v.get("severity") == "critical"]
            ),
            "high": len(
                [v for v in unique_vulnerabilities if v.get("severity") == "high"]
            ),
            "medium": len(
                [v for v in unique_vulnerabilities if v.get("severity") == "medium"]
            ),
            "low": len(
                [v for v in unique_vulnerabilities if v.get("severity") == "low"]
            ),
        }

        # Calculate overall risk score
        risk_score = (
            severity_counts["critical"] * 25
            + severity_counts["high"] * 15
            + severity_counts["medium"] * 8
            + severity_counts["low"] * 3
        )

        # Determine security posture
        security_posture = self._determine_security_posture(severity_counts, risk_score)

        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            severity_counts, risk_score, security_posture, total_duration
        )

        # Generate compliance assessment
        compliance_assessment = self._generate_compliance_assessment(
            unique_vulnerabilities
        )

        # Generate prioritized action plan
        action_plan = self._generate_action_plan(unique_vulnerabilities)

        return {
            "test_duration_seconds": total_duration,
            "total_unique_vulnerabilities": len(unique_vulnerabilities),
            "severity_breakdown": severity_counts,
            "overall_risk_score": risk_score,
            "security_posture": security_posture,
            "executive_summary": executive_summary,
            "compliance_assessment": compliance_assessment,
            "action_plan": action_plan,
            "all_vulnerabilities": unique_vulnerabilities,
            "test_coverage": {
                "owasp_top_10": True,
                "network_reconnaissance": True,
                "web_application_testing": True,
                "authentication_testing": True,
                "session_management": True,
                "input_validation": True,
                "injection_testing": True,
                "file_inclusion_testing": True,
                "xxe_testing": True,
                "ssrf_testing": True,
            },
        }

    def _deduplicate_vulnerabilities(
        self, vulnerabilities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove duplicate vulnerabilities based on type and description."""
        seen = set()
        unique_vulns = []

        for vuln in vulnerabilities:
            # Create a signature for the vulnerability
            signature = (
                vuln.get("type", ""),
                vuln.get("description", ""),
                vuln.get("endpoint", ""),
                vuln.get("severity", ""),
            )

            if signature not in seen:
                seen.add(signature)
                unique_vulns.append(vuln)

        return unique_vulns

    def _determine_security_posture(
        self, severity_counts: dict[str, int], risk_score: int
    ) -> dict[str, Any]:
        """Determine overall security posture."""
        if severity_counts["critical"] > 0:
            level = "Critical Risk"
            description = "Immediate action required. Critical vulnerabilities present."
            color = "red"
        elif severity_counts["high"] > 3:
            level = "High Risk"
            description = (
                "High priority remediation needed. Multiple high-severity issues."
            )
            color = "orange"
        elif severity_counts["high"] > 0 or severity_counts["medium"] > 5:
            level = "Medium Risk"
            description = "Moderate security concerns. Planned remediation recommended."
            color = "yellow"
        elif severity_counts["medium"] > 0 or severity_counts["low"] > 0:
            level = "Low Risk"
            description = "Minor security issues. Good overall security posture."
            color = "green"
        else:
            level = "Secure"
            description = "No significant security vulnerabilities identified."
            color = "green"

        return {
            "level": level,
            "description": description,
            "color": color,
            "risk_score": risk_score,
        }

    def _generate_executive_summary(
        self,
        severity_counts: dict[str, int],
        risk_score: int,
        security_posture: dict[str, Any],
        duration_seconds: float,
    ) -> str:
        """Generate executive summary of security assessment."""

        total_issues = sum(severity_counts.values())

        summary = f"""
EXECUTIVE SECURITY ASSESSMENT SUMMARY

Target Application: {self.target_url}
Assessment Duration: {duration_seconds/60:.1f} minutes
Assessment Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

OVERALL SECURITY POSTURE: {security_posture['level']}
{security_posture['description']}

VULNERABILITY SUMMARY:
• Total Security Issues: {total_issues}
• Critical Vulnerabilities: {severity_counts['critical']}
• High-Severity Issues: {severity_counts['high']}
• Medium-Severity Issues: {severity_counts['medium']}
• Low-Severity Issues: {severity_counts['low']}
• Overall Risk Score: {risk_score}/100

KEY FINDINGS:
"""

        if severity_counts["critical"] > 0:
            summary += f"• {severity_counts['critical']} CRITICAL vulnerabilities require immediate attention\n"

        if severity_counts["high"] > 0:
            summary += f"• {severity_counts['high']} HIGH-severity issues need priority remediation\n"

        if total_issues == 0:
            summary += "• No significant security vulnerabilities were identified\n"
            summary += "• Application demonstrates strong security controls\n"

        summary += """
RECOMMENDATIONS:
• Prioritize remediation of critical and high-severity vulnerabilities
• Implement a regular security testing schedule
• Consider security code review for custom application components
• Establish security monitoring and incident response procedures

This assessment covered OWASP Top 10 vulnerabilities, network security,
web application security, and common penetration testing techniques.
        """

        return summary.strip()

    def _generate_compliance_assessment(
        self, vulnerabilities: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate compliance assessment against security standards."""

        critical_count = len(
            [v for v in vulnerabilities if v.get("severity") == "critical"]
        )
        high_count = len([v for v in vulnerabilities if v.get("severity") == "high"])

        # OWASP Top 10 compliance
        owasp_issues = len(
            [
                v
                for v in vulnerabilities
                if any(
                    owasp_cat in v.get("type", "")
                    for owasp_cat in [
                        "Broken Access Control",
                        "Cryptographic Failures",
                        "Injection",
                        "Insecure Design",
                        "Security Misconfiguration",
                    ]
                )
            ]
        )

        return {
            "owasp_top_10": {
                "compliant": owasp_issues == 0,
                "issues_found": owasp_issues,
                "status": "Compliant" if owasp_issues == 0 else "Non-Compliant",
            },
            "pci_dss": {
                "ready": critical_count == 0 and high_count <= 2,
                "critical_issues": critical_count,
                "high_issues": high_count,
                "status": (
                    "Ready" if critical_count == 0 and high_count <= 2 else "Not Ready"
                ),
            },
            "iso_27001": {
                "aligned": critical_count == 0 and high_count <= 3,
                "major_gaps": critical_count + high_count,
                "status": (
                    "Aligned"
                    if critical_count == 0 and high_count <= 3
                    else "Gaps Identified"
                ),
            },
            "nist_cybersecurity_framework": {
                "mature": critical_count == 0 and high_count == 0,
                "status": (
                    "Mature"
                    if critical_count == 0 and high_count == 0
                    else "Developing"
                ),
            },
        }

    def _generate_action_plan(
        self, vulnerabilities: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Generate prioritized action plan for remediation."""

        # Group vulnerabilities by type and severity
        vuln_groups = {}
        for vuln in vulnerabilities:
            vuln_type = vuln.get("type", "Unknown")
            severity = vuln.get("severity", "low")

            key = (vuln_type, severity)
            if key not in vuln_groups:
                vuln_groups[key] = []
            vuln_groups[key].append(vuln)

        action_items = []

        # Priority order
        priority_order = ["critical", "high", "medium", "low"]

        for severity in priority_order:
            for (vuln_type, vuln_severity), vulns in vuln_groups.items():
                if vuln_severity == severity:
                    # Generate action item
                    action_item = {
                        "priority": self._get_priority_label(severity),
                        "vulnerability_type": vuln_type,
                        "severity": severity,
                        "count": len(vulns),
                        "effort_estimate": self._estimate_effort(vuln_type, len(vulns)),
                        "timeline": self._estimate_timeline(severity),
                        "action_required": self._get_action_description(vuln_type),
                        "business_impact": self._get_business_impact(severity),
                        "affected_components": list(
                            set(
                                [
                                    vuln.get(
                                        "endpoint", vuln.get("component", "Unknown")
                                    )
                                    for vuln in vulns
                                ]
                            )
                        ),
                    }
                    action_items.append(action_item)

        return action_items

    def _get_priority_label(self, severity: str) -> str:
        """Get priority label for severity."""
        labels = {
            "critical": "P0 - Immediate",
            "high": "P1 - Urgent",
            "medium": "P2 - High",
            "low": "P3 - Medium",
        }
        return labels.get(severity, "P3 - Medium")

    def _estimate_effort(self, vuln_type: str, count: int) -> str:
        """Estimate remediation effort."""
        base_efforts = {
            "SQL Injection": "Medium",
            "Cross-Site Scripting (XSS)": "Medium",
            "Broken Access Control": "High",
            "Security Misconfiguration": "Low",
            "Cryptographic Failures": "High",
            "Information Disclosure": "Low",
        }

        base_effort = base_efforts.get(vuln_type, "Medium")

        if count > 5:
            return f"{base_effort} (Multiple instances increase effort)"

        return base_effort

    def _estimate_timeline(self, severity: str) -> str:
        """Estimate remediation timeline."""
        timelines = {
            "critical": "24-48 hours",
            "high": "1-2 weeks",
            "medium": "1 month",
            "low": "3 months",
        }
        return timelines.get(severity, "1 month")

    def _get_action_description(self, vuln_type: str) -> str:
        """Get action description for vulnerability type."""
        actions = {
            "SQL Injection": "Implement parameterized queries and input validation",
            "Cross-Site Scripting (XSS)": "Add input sanitization and output encoding",
            "Broken Access Control": "Implement proper authorization checks",
            "Security Misconfiguration": "Review and harden security configurations",
            "Cryptographic Failures": "Implement proper encryption and secure protocols",
            "Information Disclosure": "Remove sensitive information from error messages",
            "Local File Inclusion": "Validate file paths and implement access controls",
            "XML External Entity (XXE)": "Disable external entity processing",
            "Server-Side Request Forgery (SSRF)": "Implement URL validation and allow-lists",
        }
        return actions.get(
            vuln_type, "Review and remediate according to best practices"
        )

    def _get_business_impact(self, severity: str) -> str:
        """Get business impact description."""
        impacts = {
            "critical": "High - Immediate risk of data breach or system compromise",
            "high": "Medium-High - Potential for significant security incident",
            "medium": "Medium - Could lead to security issues if exploited",
            "low": "Low - Minor security concerns with limited impact",
        }
        return impacts.get(severity, "Medium - Moderate business impact")

    async def _save_assessment_results(self, results: dict[str, Any]) -> None:
        """Save assessment results to various formats."""

        # Save JSON report
        json_file = self.output_dir / f"security_assessment_{self.timestamp}.json"
        with open(json_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"JSON report saved: {json_file}")

        # Save executive summary
        if (
            "combined_analysis" in results
            and "executive_summary" in results["combined_analysis"]
        ):
            summary_file = self.output_dir / f"executive_summary_{self.timestamp}.txt"
            with open(summary_file, "w") as f:
                f.write(results["combined_analysis"]["executive_summary"])
            logger.info(f"Executive summary saved: {summary_file}")

        # Save CSV of vulnerabilities
        await self._save_vulnerabilities_csv(results)

        # Generate HTML report
        await self._generate_html_report(results)

    async def _save_vulnerabilities_csv(self, results: dict[str, Any]) -> None:
        """Save vulnerabilities in CSV format."""
        import csv

        csv_file = self.output_dir / f"vulnerabilities_{self.timestamp}.csv"

        if (
            "combined_analysis" in results
            and "all_vulnerabilities" in results["combined_analysis"]
        ):
            vulnerabilities = results["combined_analysis"]["all_vulnerabilities"]

            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                if vulnerabilities:
                    fieldnames = [
                        "type",
                        "severity",
                        "description",
                        "endpoint",
                        "recommendation",
                    ]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for vuln in vulnerabilities:
                        writer.writerow(
                            {
                                "type": vuln.get("type", ""),
                                "severity": vuln.get("severity", ""),
                                "description": vuln.get("description", ""),
                                "endpoint": vuln.get(
                                    "endpoint", vuln.get("component", "")
                                ),
                                "recommendation": vuln.get("recommendation", ""),
                            }
                        )

            logger.info(f"CSV report saved: {csv_file}")

    async def _generate_html_report(self, results: dict[str, Any]) -> None:
        """Generate HTML report."""
        html_file = self.output_dir / f"security_report_{self.timestamp}.html"

        # Simple HTML template
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Security Assessment Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; }}
        .critical {{ color: #d32f2f; font-weight: bold; }}
        .high {{ color: #f57c00; font-weight: bold; }}
        .medium {{ color: #fbc02d; font-weight: bold; }}
        .low {{ color: #689f38; }}
        .summary-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .summary-table th, .summary-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .summary-table th {{ background-color: #f2f2f2; }}
        pre {{ background: #f5f5f5; padding: 15px; border-radius: 5px; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Security Assessment Report</h1>
        <p><strong>Target:</strong> {results.get('target_url', 'Unknown')}</p>
        <p><strong>Date:</strong> {results.get('test_timestamp', 'Unknown')}</p>
    </div>
"""

        if "combined_analysis" in results:
            analysis = results["combined_analysis"]

            # Add summary table
            severity = analysis.get("severity_breakdown", {})
            html_content += f"""
    <h2>Vulnerability Summary</h2>
    <table class="summary-table">
        <tr>
            <th>Severity</th>
            <th>Count</th>
        </tr>
        <tr>
            <td class="critical">Critical</td>
            <td>{severity.get('critical', 0)}</td>
        </tr>
        <tr>
            <td class="high">High</td>
            <td>{severity.get('high', 0)}</td>
        </tr>
        <tr>
            <td class="medium">Medium</td>
            <td>{severity.get('medium', 0)}</td>
        </tr>
        <tr>
            <td class="low">Low</td>
            <td>{severity.get('low', 0)}</td>
        </tr>
    </table>

    <h2>Executive Summary</h2>
    <pre>{analysis.get('executive_summary', 'No summary available')}</pre>
"""

        html_content += """
</body>
</html>
"""

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"HTML report saved: {html_file}")


async def main() -> Any:
    """Main function to run security testing."""
    parser = argparse.ArgumentParser(description="Comprehensive Security Testing Suite")
    parser.add_argument("--target", "-t", required=True, help="Target URL to test")
    parser.add_argument(
        "--output",
        "-o",
        default="security_reports",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--tests",
        "-T",
        choices=["owasp", "pentest", "all"],
        default="all",
        help="Test suites to run",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create orchestrator
    orchestrator = SecurityTestOrchestrator(args.target, args.output)

    try:
        if args.tests == "all":
            # Run comprehensive assessment
            results = await orchestrator.run_comprehensive_security_assessment()
        elif args.tests == "owasp":
            # Run only OWASP tests
            config = SecurityTestConfig()
            config.base_url = args.target
            config.api_base = f"{args.target}/api/v1"

            runner = SecurityTestRunner(config)
            results = await runner.run_all_tests()
        elif args.tests == "pentest":
            # Run only penetration tests
            config = PenetrationTestConfig()
            config.target_url = args.target

            runner = PenetrationTestRunner(config)
            results = await runner.run_full_pentest()

        # Print summary
        if "combined_analysis" in results:
            analysis = results["combined_analysis"]
            posture = analysis.get("security_posture", {})

            print("\n" + "=" * 80)
            print("SECURITY ASSESSMENT COMPLETE")
            print("=" * 80)
            print(f"Target: {args.target}")
            print(f"Security Posture: {posture.get('level', 'Unknown')}")
            print(f"Risk Score: {analysis.get('overall_risk_score', 0)}")
            print(
                f"Total Vulnerabilities: {analysis.get('total_unique_vulnerabilities', 0)}"
            )

            severity = analysis.get("severity_breakdown", {})
            print(f"Critical: {severity.get('critical', 0)}")
            print(f"High: {severity.get('high', 0)}")
            print(f"Medium: {severity.get('medium', 0)}")
            print(f"Low: {severity.get('low', 0)}")
            print("=" * 80)
            print(f"Reports saved in: {args.output}/")

        return 0

    except Exception as e:
        logger.error(f"Security testing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
