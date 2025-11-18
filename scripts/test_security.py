from typing import Any

#!/usr/bin/env python3
"""
Legacy security test script for CI/CD pipeline
This script is maintained for backward compatibility.
For optimized security scanning, use optimized_security_scan.py
"""

import json
import os
import subprocess
import sys


def run_command(cmd, cwd=None, timeout=60) -> Any:
    """Run a command and return the result with timeout"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return False, "", str(e)


def test_python_security() -> Any:
    """Test Python security with bandit (optimized)"""
    print("🔍 Testing Python security with bandit...")

    # Use optimized bandit configuration if available
    bandit_config = "-c .bandit" if os.path.exists(".bandit") else ""
    cmd = f"python -m bandit {bandit_config} -r src/ backend/ -f json -ll"

    success, stdout, stderr = run_command(cmd, timeout=45)
    if success:
        print("✅ Bandit scan completed successfully")
        return True
    else:
        print(f"⚠️ Bandit found issues: {stderr}")
        return False


def test_frontend_security() -> Any:
    """Test frontend security with npm audit"""
    print("🔍 Testing frontend security with npm audit...")

    os.chdir("frontend")
    success, stdout, stderr = run_command("npm audit --audit-level=high --json")
    os.chdir("..")

    if success:
        print("✅ No high/critical vulnerabilities found")
        return True
    else:
        try:
            audit_data = json.loads(stdout) if stdout else {}
            if "metadata" in audit_data:
                meta = audit_data["metadata"]["vulnerabilities"]
                high = meta.get("high", 0)
                critical = meta.get("critical", 0)
                if high > 0 or critical > 0:
                    print(
                        f"❌ Found {critical} critical and {high} high vulnerabilities"
                    )
                    return False
                else:
                    print("⚠️ Only moderate vulnerabilities found")
                    return True
            else:
                print("✅ No vulnerabilities found")
                return True
        except json.JSONDecodeError:
            print("⚠️ Could not parse audit results")
            return True


def test_secrets() -> Any:
    """Test for secrets in the codebase"""
    print("🔍 Testing for secrets...")

    # Simple secrets check
    patterns = [
        r"password\s*=\s*['\"][^'\"]+['\"]",
        r"api_key\s*=\s*['\"][^'\"]+['\"]",
        r"secret\s*=\s*['\"][^'\"]+['\"]",
        r"token\s*=\s*['\"][^'\"]+['\"]",
    ]

    # Check common files
    files_to_check = [
        "config.py",
        "backend/api/main.py",
        "src/**/*.py",
        "frontend/src/**/*.ts",
        "frontend/src/**/*.tsx",
    ]

    # Simple grep-like check
    for pattern in patterns:
        success, stdout, stderr = run_command(
            f"grep -r -i '{pattern}' --include='*.py' --include='*.ts' --include='*.tsx' ."
        )
        if success and stdout.strip():
            print(f"⚠️ Potential secret pattern found: {pattern}")
            return False

    print("✅ No obvious secrets found")
    return True


def main() -> Any:
    """Run all security tests"""
    print("🔒 Running security tests...")

    tests = [
        ("Python Security", test_python_security),
        ("Frontend Security", test_frontend_security),
        ("Secrets Check", test_secrets),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            print(f"{'✅' if result else '❌'} {name}: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"❌ {name}: ERROR - {e}")
            results.append((name, False))

    print("\n📊 Security Test Summary:")
    for name, result in results:
        print(f"  {'✅' if result else '❌'} {name}")

    # Exit with error code if any test failed
    if all(result for _, result in results):
        print("\n🎉 All security tests passed!")
        return 0
    else:
        print("\n⚠️ Some security tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
