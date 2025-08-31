#!/usr/bin/env python3
"""
Fix incorrect indentation of 'from e)' clauses.
"""

import re
from pathlib import Path


def fix_from_e_indentation(filepath: Path) -> int:
    """Fix 'from e)' on wrong lines."""
    try:
        lines = filepath.read_text(encoding='utf-8').splitlines()
        new_lines = []
        fixes = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if this line has incorrect indentation for 'from e)'
            if re.match(r'^\s+from\s+\w+\)?\s*$', line):
                # This is a 'from e)' on its own line with wrong indentation
                # It should be appended to the previous line
                if new_lines and i > 0:
                    # Get the previous line
                    prev_line = new_lines[-1]
                    # Remove the previous line and append the from clause
                    new_lines[-1] = prev_line.rstrip() + ' ' + line.strip()
                    fixes += 1
                    i += 1
                    continue

            new_lines.append(line)
            i += 1

        if fixes > 0:
            filepath.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
            print(f"Fixed {fixes} indentation issues in {filepath}")

        return fixes

    except Exception as e:
        print(f"Error fixing {filepath}: {e}")
        return 0


def main():
    """Main function."""
    total_fixes = 0

    # Find all Python files
    for py_file in Path(".").rglob("*.py"):
        if "venv" in str(py_file) or "build" in str(py_file):
            continue

        fixes = fix_from_e_indentation(py_file)
        total_fixes += fixes

    print(f"\nTotal fixes: {total_fixes}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
