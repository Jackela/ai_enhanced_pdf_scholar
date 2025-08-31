#!/usr/bin/env python3
"""
Script to automatically fix B904 violations (missing 'from e' in exception chains).
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def get_b904_violations() -> list[tuple[str, int, str]]:
    """Get all B904 violations from ruff."""
    try:
        result = subprocess.run(
            ["ruff", "check", "--select", "B904"],
            capture_output=True,
            text=True
        )

        violations = []
        for line in result.stdout.splitlines():
            # Parse ruff output: filename:line:col: B904 ...
            match = re.match(r'^([^:]+):(\d+):\d+: B904', line)
            if match:
                filepath = match.group(1)
                line_num = int(match.group(2))
                violations.append((filepath, line_num, line))

        return violations
    except Exception as e:
        print(f"Error running ruff: {e}")
        return []


def fix_violation(filepath: str, line_num: int) -> bool:
    """Fix a single B904 violation."""
    try:
        file_path = Path(filepath)
        if not file_path.exists():
            print(f"File not found: {filepath}")
            return False

        lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)

        # Find the raise statement
        if line_num > len(lines):
            print(f"Line {line_num} out of range in {filepath}")
            return False

        # Check if it's a multi-line raise statement
        raise_line_idx = line_num - 1

        # Find the complete raise statement
        statement_lines = []
        idx = raise_line_idx

        # Check if current line starts with raise or is a continuation
        while idx < len(lines):
            line = lines[idx]
            statement_lines.append(line)

            # Check if this line contains a closing parenthesis
            if ')' in line and not line.strip().endswith(','):
                # Check if we're at the end of a multi-line statement
                stripped = line.rstrip()
                if stripped.endswith(')'):
                    # This is likely the end of the raise statement
                    break

            # If line doesn't end with a backslash or comma, and next line doesn't start with whitespace, we're done
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if not (line.rstrip().endswith((',', '\\')) or next_line[0].isspace()):
                    break

            idx += 1
            if idx >= len(lines):
                break

        # Find the corresponding except clause
        except_line_idx = None
        for i in range(raise_line_idx - 1, -1, -1):
            if re.match(r'\s*except\s+.*\s+as\s+(\w+)', lines[i]):
                except_line_idx = i
                match = re.match(r'\s*except\s+.*\s+as\s+(\w+)', lines[i])
                exception_var = match.group(1)
                break
            elif re.match(r'\s*except\s+\w+:', lines[i]) or re.match(r'\s*except:', lines[i]):
                except_line_idx = i
                exception_var = None
                break

        if except_line_idx is None:
            print(f"Could not find except clause for line {line_num} in {filepath}")
            return False

        # Check if last line already has 'from'
        last_statement_line = statement_lines[-1].rstrip()
        if ' from ' in last_statement_line:
            print(f"Already fixed: {filepath}:{line_num}")
            return False

        # Add 'from e' or 'from None' to the last line of the raise statement
        if exception_var:
            suffix = f" from {exception_var}"
        else:
            # If no exception variable, use 'from None' to explicitly break the chain
            suffix = " from None"

        # Modify the last line of the statement
        modified_line = statement_lines[-1].rstrip()
        if modified_line.endswith(')'):
            modified_line = modified_line[:-1] + suffix + ')'
        else:
            modified_line = modified_line + suffix

        modified_line += '\n' if statement_lines[-1].endswith('\n') else ''

        # Update the lines
        lines[raise_line_idx + len(statement_lines) - 1] = modified_line

        # Write back to file
        file_path.write_text(''.join(lines), encoding='utf-8')
        print(f"Fixed: {filepath}:{line_num}")
        return True

    except Exception as e:
        print(f"Error fixing {filepath}:{line_num}: {e}")
        return False


def main():
    """Main function to fix all B904 violations."""
    print("Scanning for B904 violations...")
    violations = get_b904_violations()

    if not violations:
        print("No B904 violations found!")
        return 0

    print(f"Found {len(violations)} B904 violations")

    # Group violations by file
    files_to_fix = {}
    for filepath, line_num, full_line in violations:
        if filepath not in files_to_fix:
            files_to_fix[filepath] = []
        files_to_fix[filepath].append(line_num)

    fixed_count = 0
    failed_count = 0

    # Process each file
    for filepath, line_nums in files_to_fix.items():
        print(f"\nProcessing {filepath} ({len(line_nums)} violations)...")

        # Sort line numbers in reverse to avoid line number shifts
        for line_num in sorted(line_nums, reverse=True):
            if fix_violation(filepath, line_num):
                fixed_count += 1
            else:
                failed_count += 1

    print(f"\n{'='*50}")
    print(f"Summary: Fixed {fixed_count} violations, {failed_count} failed")

    # Run ruff check again to verify
    print("\nVerifying fixes...")
    remaining = get_b904_violations()
    if remaining:
        print(f"Warning: {len(remaining)} B904 violations still remain")
        return 1
    else:
        print("All B904 violations have been fixed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
