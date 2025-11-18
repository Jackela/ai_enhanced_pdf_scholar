#!/usr/bin/env python3
"""
Local CI/CD Testing Script
Tests the CI/CD pipeline locally and identifies issues.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class LocalCITester:
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root or os.getcwd())
        self.workflows_dir = self.project_root / ".github" / "workflows"
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": [],
            "issues_found": [],
            "fixes_applied": [],
            "summary": {},
        }

    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_command(self, cmd: list, timeout: int = 60) -> dict:
        """Run a command and return result."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Command timed out",
                "returncode": -1,
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def check_act_installation(self) -> bool:
        """Check if act CLI is installed."""
        self.log("Checking act CLI installation...")
        result = self.run_command(["act", "--version"])

        if result["success"]:
            version = result["stdout"].strip()
            self.log(f"✅ act CLI found: {version}")
            self.results["tests_run"].append("act_installation_check")
            return True
        else:
            self.log("❌ act CLI not found or not working")
            self.results["issues_found"].append(
                {
                    "type": "missing_dependency",
                    "description": "act CLI not installed or not in PATH",
                    "fix": "Install act CLI: https://github.com/nektos/act",
                }
            )
            return False

    def check_docker_status(self) -> bool:
        """Check Docker status."""
        self.log("Checking Docker status...")
        result = self.run_command(["docker", "info"])

        if result["success"]:
            self.log("✅ Docker is running")
            self.results["tests_run"].append("docker_status_check")
            return True
        else:
            self.log("❌ Docker is not running or accessible")
            self.results["issues_found"].append(
                {
                    "type": "docker_issue",
                    "description": "Docker daemon not accessible",
                    "fix": "Start Docker Desktop or Docker daemon",
                }
            )
            return False

    def validate_workflows(self) -> bool:
        """Validate all workflow files."""
        self.log("Validating workflow files...")

        if not self.workflows_dir.exists():
            self.log("❌ Workflows directory not found")
            return False

        workflow_files = list(self.workflows_dir.glob("*.yml"))
        valid_count = 0

        for workflow_file in workflow_files:
            self.log(f"Checking {workflow_file.name}...")
            result = self.run_command(["act", "--list", "-W", str(workflow_file)])

            if result["success"]:
                self.log(f"✅ {workflow_file.name} is valid")
                valid_count += 1
            else:
                self.log(f"❌ {workflow_file.name} has issues")
                self.results["issues_found"].append(
                    {
                        "type": "workflow_validation",
                        "file": workflow_file.name,
                        "error": result["stderr"],
                    }
                )

        self.results["tests_run"].append("workflow_validation")
        self.results["summary"]["total_workflows"] = len(workflow_files)
        self.results["summary"]["valid_workflows"] = valid_count

        return valid_count == len(workflow_files)

    def test_simple_workflow(self) -> bool:
        """Test a simple workflow in dry-run mode."""
        self.log("Testing simple workflow...")

        simple_workflow = self.workflows_dir / "test-simple.yml"
        if not simple_workflow.exists():
            self.log("❌ Simple test workflow not found")
            return False

        result = self.run_command(
            ["act", "-n", "workflow_dispatch", "-W", str(simple_workflow)], timeout=120
        )

        if result["success"]:
            self.log("✅ Simple workflow test passed")
            self.results["tests_run"].append("simple_workflow_test")
            return True
        else:
            self.log("❌ Simple workflow test failed")
            self.results["issues_found"].append(
                {
                    "type": "workflow_execution",
                    "file": "test-simple.yml",
                    "error": result["stderr"],
                }
            )
            return False

    def test_enhanced_ci_workflow(self) -> bool:
        """Test the enhanced CI workflow in dry-run mode."""
        self.log("Testing enhanced CI workflow...")

        enhanced_workflow = self.workflows_dir / "ci-enhanced.yml"
        if not enhanced_workflow.exists():
            self.log("❌ Enhanced CI workflow not found")
            return False

        # Test just the change-detection job
        result = self.run_command(
            [
                "act",
                "-n",
                "workflow_dispatch",
                "-W",
                str(enhanced_workflow),
                "-j",
                "change-detection",
            ],
            timeout=180,
        )

        if result["success"]:
            self.log("✅ Enhanced CI workflow structure test passed")
            self.results["tests_run"].append("enhanced_ci_workflow_test")
            return True
        else:
            self.log("❌ Enhanced CI workflow test failed")
            self.results["issues_found"].append(
                {
                    "type": "workflow_execution",
                    "file": "ci-enhanced.yml",
                    "error": result["stderr"],
                }
            )
            return False

    def suggest_fixes(self):
        """Suggest fixes for found issues."""
        if not self.results["issues_found"]:
            self.log("🎉 No issues found! CI/CD pipeline is ready to run.")
            return

        self.log("🔧 Suggested fixes for found issues:")
        for i, issue in enumerate(self.results["issues_found"], 1):
            self.log(f"{i}. {issue['type']}: {issue['description']}")
            if "fix" in issue:
                self.log(f"   Fix: {issue['fix']}")
            if "file" in issue:
                self.log(f"   File: {issue['file']}")

    def run_full_test(self) -> bool:
        """Run full test suite."""
        self.log("🚀 Starting Local CI/CD Testing...")

        # Check prerequisites
        if not self.check_act_installation():
            return False

        if not self.check_docker_status():
            return False

        # Validate workflows
        workflows_valid = self.validate_workflows()

        # Test simple workflow
        simple_test = self.test_simple_workflow()

        # Test enhanced CI workflow
        enhanced_test = self.test_enhanced_ci_workflow()

        # Generate summary
        self.results["summary"]["all_tests_passed"] = (
            workflows_valid and simple_test and enhanced_test
        )

        self.results["summary"]["issues_count"] = len(self.results["issues_found"])
        self.results["summary"]["tests_passed"] = len(self.results["tests_run"])

        return self.results["summary"]["all_tests_passed"]

    def save_results(self, filename: str = "ci_test_results.json"):
        """Save test results to file."""
        results_file = self.project_root / filename
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        self.log(f"📊 Results saved to {results_file}")


def main():
    """Main function."""
    tester = LocalCITester()

    try:
        success = tester.run_full_test()
        tester.suggest_fixes()
        tester.save_results()

        if success:
            print("\n🎉 All tests passed! CI/CD pipeline is ready.")
            sys.exit(0)
        else:
            print(
                f"\n❌ Found {len(tester.results['issues_found'])} issues. Check the suggestions above."
            )
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️ Testing interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Testing failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
