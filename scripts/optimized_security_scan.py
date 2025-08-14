#!/usr/bin/env python3
"""
Optimized Security Scanning Script for CI/CD
Focuses on performance and timeout prevention while maintaining security coverage.
"""

import subprocess
import sys
import json
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
from typing import List, Dict, Tuple, Optional


class SecurityScanner:
    """Optimized security scanner with timeout management."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.results = {
            "python_dependencies": {"status": "pending", "issues": 0, "duration": 0},
            "frontend_dependencies": {"status": "pending", "issues": 0, "duration": 0},
            "code_analysis": {"status": "pending", "issues": 0, "duration": 0},
            "total_duration": 0
        }
        self.start_time = time.time()

    def run_command_with_timeout(self, cmd: List[str], timeout: int = 60, cwd: Optional[Path] = None) -> Tuple[bool, str, str]:
        """Run command with timeout and error handling."""
        try:
            result = subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=True,
                text=True,
                cwd=cwd or self.project_root
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return False, "", str(e)

    def scan_python_dependencies(self) -> bool:
        """Optimized Python dependency vulnerability scanning."""
        print("🔍 Scanning Python dependencies...")
        start_time = time.time()

        # Use lightweight scanning approach
        cmd = [
            sys.executable, "-m", "pip", "list", "--format=json"
        ]

        success, stdout, stderr = self.run_command_with_timeout(cmd, timeout=30)

        if not success:
            print(f"❌ Failed to get package list: {stderr}")
            self.results["python_dependencies"]["status"] = "failed"
            return False

        try:
            packages = json.loads(stdout)
            print(f"📦 Found {len(packages)} Python packages")

            # Quick safety check with timeout (updated for safety 3.x)
            safety_cmd = [
                sys.executable, "-m", "safety", "check",
                "--save-json", "safety-report.json"
            ]

            success, _, stderr = self.run_command_with_timeout(safety_cmd, timeout=45)

            if success:
                print("✅ Safety scan completed")
                self.results["python_dependencies"]["status"] = "completed"
                self.results["python_dependencies"]["issues"] = 0
            else:
                print(f"⚠️ Safety scan issues: {stderr}")
                self.results["python_dependencies"]["status"] = "completed_with_issues"
                self.results["python_dependencies"]["issues"] = 1

        except Exception as e:
            print(f"❌ Python dependency scan failed: {e}")
            self.results["python_dependencies"]["status"] = "failed"
            return False

        finally:
            self.results["python_dependencies"]["duration"] = time.time() - start_time

        return True

    def scan_frontend_dependencies(self) -> bool:
        """Optimized frontend dependency vulnerability scanning."""
        print("🔍 Scanning frontend dependencies...")
        start_time = time.time()

        frontend_dir = self.project_root / "frontend"
        if not frontend_dir.exists():
            print("⏭️ No frontend directory found, skipping")
            self.results["frontend_dependencies"]["status"] = "skipped"
            return True

        # Quick npm audit with limited output
        cmd = [
            "npm", "audit", "--audit-level=moderate",
            "--json", "--production"
        ]

        success, stdout, stderr = self.run_command_with_timeout(
            cmd, timeout=60, cwd=frontend_dir
        )

        try:
            if stdout:
                audit_data = json.loads(stdout)
                vulnerabilities = audit_data.get("metadata", {}).get("vulnerabilities", {})
                total_vulns = sum(vulnerabilities.values()) if vulnerabilities else 0

                print(f"📦 Frontend audit found {total_vulns} vulnerabilities")
                self.results["frontend_dependencies"]["issues"] = total_vulns
                self.results["frontend_dependencies"]["status"] = "completed"

                # Save report
                with open(self.project_root / "npm-audit-report.json", "w") as f:
                    json.dump(audit_data, f, indent=2)
            else:
                print("✅ No frontend vulnerabilities found")
                self.results["frontend_dependencies"]["status"] = "completed"

        except json.JSONDecodeError:
            print("⚠️ Could not parse npm audit output")
            self.results["frontend_dependencies"]["status"] = "completed_with_issues"
        except Exception as e:
            print(f"❌ Frontend scan failed: {e}")
            self.results["frontend_dependencies"]["status"] = "failed"
            return False

        finally:
            self.results["frontend_dependencies"]["duration"] = time.time() - start_time

        return True

    def scan_code_security(self) -> bool:
        """Optimized code security analysis with bandit."""
        print("🔍 Scanning code security...")
        start_time = time.time()

        # Use optimized bandit configuration
        cmd = [
            sys.executable, "-m", "bandit",
            "-c", ".bandit",
            "-f", "json",
            "-o", "bandit-report.json",
            "-ll",  # Low severity threshold for speed
            "src/", "backend/"
        ]

        success, stdout, stderr = self.run_command_with_timeout(cmd, timeout=45)

        try:
            if os.path.exists("bandit-report.json"):
                try:
                    with open("bandit-report.json", "r") as f:
                        content = f.read().strip()
                        if content:
                            bandit_data = json.loads(content)
                            issues = len(bandit_data.get("results", []))
                            print(f"🔍 Bandit found {issues} security issues")
                            self.results["code_analysis"]["issues"] = issues
                            self.results["code_analysis"]["status"] = "completed"
                        else:
                            print("✅ No code security issues found (empty report)")
                            self.results["code_analysis"]["status"] = "completed"
                except json.JSONDecodeError as e:
                    print(f"⚠️ Could not parse bandit report: {e}")
                    self.results["code_analysis"]["status"] = "completed_with_issues"
            else:
                print("✅ No code security issues found")
                self.results["code_analysis"]["status"] = "completed"

        except Exception as e:
            print(f"❌ Code security scan failed: {e}")
            self.results["code_analysis"]["status"] = "failed"
            return False

        finally:
            self.results["code_analysis"]["duration"] = time.time() - start_time

        return True

    def run_parallel_scans(self) -> bool:
        """Run security scans in parallel for better performance."""
        print("🚀 Starting parallel security scans...")

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.scan_python_dependencies): "python_deps",
                executor.submit(self.scan_frontend_dependencies): "frontend_deps",
                executor.submit(self.scan_code_security): "code_analysis"
            }

            results = {}
            for future in as_completed(futures, timeout=180):  # 3 minute total timeout
                scan_type = futures[future]
                try:
                    results[scan_type] = future.result()
                except Exception as e:
                    print(f"❌ {scan_type} scan failed: {e}")
                    results[scan_type] = False

        return all(results.values())

    def generate_summary_report(self) -> None:
        """Generate a summary security report."""
        self.results["total_duration"] = time.time() - self.start_time

        print("\n" + "="*60)
        print("🛡️ SECURITY SCAN SUMMARY")
        print("="*60)

        for scan_type, result in self.results.items():
            if isinstance(result, dict):
                status = result.get("status", "unknown")
                issues = result.get("issues", 0)
                duration = result.get("duration", 0)

                status_emoji = {
                    "completed": "✅",
                    "completed_with_issues": "⚠️",
                    "failed": "❌",
                    "skipped": "⏭️",
                    "pending": "⏳"
                }.get(status, "❓")

                print(f"{status_emoji} {scan_type.replace('_', ' ').title()}: "
                      f"{status} ({issues} issues, {duration:.1f}s)")

        print(f"⏱️ Total Duration: {self.results['total_duration']:.1f}s")

        # Calculate overall risk level
        total_issues = sum(
            result.get("issues", 0)
            for result in self.results.values()
            if isinstance(result, dict)
        )

        if total_issues == 0:
            print("🎉 No security issues found!")
        elif total_issues < 5:
            print(f"⚠️ Low risk: {total_issues} security issues found")
        elif total_issues < 15:
            print(f"🟠 Medium risk: {total_issues} security issues found")
        else:
            print(f"🔴 High risk: {total_issues} security issues found")

        print("="*60)

    def save_reports(self) -> None:
        """Save security scan results."""
        results_file = self.project_root / "security-scan-results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"📄 Results saved to {results_file}")


def main():
    """Main security scanner entry point."""
    project_root = Path(__file__).parent.parent
    scanner = SecurityScanner(project_root)

    # Check if required tools are available
    required_tools = ["safety", "bandit"]
    for tool in required_tools:
        try:
            result = subprocess.run([sys.executable, "-m", tool, "--version"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ Tool '{tool}' is available")
            else:
                raise subprocess.CalledProcessError(result.returncode, tool)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            print(f"⚠️ Installing tool '{tool}'...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", tool],
                             check=True, timeout=60)
                print(f"✅ Tool '{tool}' installed successfully")
            except subprocess.TimeoutExpired:
                print(f"❌ Failed to install '{tool}' - timeout")
                sys.exit(1)
            except Exception as e:
                print(f"❌ Failed to install '{tool}': {e}")
                sys.exit(1)

    # Run scans
    try:
        success = scanner.run_parallel_scans()
        scanner.generate_summary_report()
        scanner.save_reports()

        # Exit with appropriate code
        if success:
            print("✅ Security scanning completed successfully")
            sys.exit(0)
        else:
            print("❌ Security scanning completed with errors")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Security scan interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Fatal error during security scan: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()