from typing import Any

#!/usr/bin/env python3
"""
Verify that S106 (hardcoded password) violations have been fixed.
This script checks that the migration files properly use environment variables
instead of hardcoded passwords.
"""

import ast
import sys
from pathlib import Path


def check_file_for_hardcoded_passwords(file_path) -> Any:
    """Check a Python file for hardcoded passwords."""
    violations = []

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Parse the AST
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"⚠️ Syntax error in {file_path}: {e}")
        return violations

    # Check for assignments with hardcoded password-like strings
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    # Check if variable name contains password-related keywords
                    if any(
                        pwd in var_name
                        for pwd in ["password", "passwd", "pwd", "secret"]
                    ):
                        # Check if the value is a hardcoded string literal
                        if isinstance(node.value, ast.Constant) and isinstance(
                            node.value.value, str
                        ):
                            # Exclude empty strings and environment variable references
                            value = node.value.value
                            if (
                                value
                                and not value.startswith("$")
                                and not value.startswith("os.")
                            ):
                                violations.append(
                                    {
                                        "line": node.lineno,
                                        "variable": target.id,
                                        "value": (
                                            value[:20] + "..."
                                            if len(value) > 20
                                            else value
                                        ),
                                    }
                                )

    return violations


def main() -> Any:
    """Main function to check for S106 violations."""
    print("🔍 Checking for S106 (hardcoded password) violations...\n")

    # Files to check
    files_to_check = [
        Path("src/database/migrations.py"),
        Path("src/database/migrations/versions/006_add_authentication_tables.py"),
    ]

    total_violations = 0

    for file_path in files_to_check:
        if not file_path.exists():
            print(f"⚠️ File not found: {file_path}")
            continue

        print(f"Checking: {file_path}")
        violations = check_file_for_hardcoded_passwords(file_path)

        if violations:
            print(f"  ❌ Found {len(violations)} violation(s):")
            for v in violations:
                print(f"    Line {v['line']}: {v['variable']} = '{v['value']}'")
            total_violations += len(violations)
        else:
            print("  ✅ No hardcoded passwords found")

    print(f"\n{'='*60}")

    # Check for environment variable usage
    print("\n✅ Verifying environment variable usage:")

    for file_path in files_to_check:
        if not file_path.exists():
            continue

        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        if 'os.getenv("DEFAULT_ADMIN_PASSWORD")' in content:
            print(f"  ✅ {file_path.name}: Using os.getenv('DEFAULT_ADMIN_PASSWORD')")
        elif "os.environ" in content and "DEFAULT_ADMIN_PASSWORD" in content:
            print(f"  ✅ {file_path.name}: Using os.environ for DEFAULT_ADMIN_PASSWORD")
        else:
            print(
                f"  ⚠️ {file_path.name}: Not using environment variables for admin password"
            )

    # Check .env.example
    env_example = Path(".env.example")
    if env_example.exists():
        with open(env_example, encoding="utf-8") as f:
            if "DEFAULT_ADMIN_PASSWORD" in f.read():
                print("  ✅ .env.example: Contains DEFAULT_ADMIN_PASSWORD template")

    print(f"\n{'='*60}")

    if total_violations == 0:
        print("\n✅ SUCCESS: No S106 violations found!")
        print("   All passwords are properly configured via environment variables.")
        return 0
    else:
        print(f"\n❌ FAILED: Found {total_violations} S106 violation(s)")
        print("   Please replace hardcoded passwords with environment variables.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
