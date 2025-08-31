#!/usr/bin/env python3
"""
Script to fix syntax errors from incorrect B904 fixes.
"""

import re
from pathlib import Path
from typing import List, Tuple


def find_syntax_errors() -> list[tuple[Path, int, str]]:
    """Find all files with the specific syntax error pattern."""
    errors = []

    # Common patterns where 'from e' was incorrectly placed
    patterns = [
        # Pattern 1: from e inside string literal
        (r'(raise\s+\w+Exception\([^)]*"[^"]*)\s+from\s+(\w+)\)', r'\1") from \2'),
        # Pattern 2: from e on next line with wrong indentation
        (r'(raise\s+\w+Exception\([^)]*\n\s*[^)]*)\n\s+from\s+(\w+)\)', r'\1\n        ) from \2'),
        # Pattern 3: RuntimeError with from inside string
        (r'(raise\s+RuntimeError\("[^"]*)\s+from\s+(\w+)\)', r'\1") from \2'),
        # Pattern 4: ValueError with from inside string
        (r'(raise\s+ValueError\(f?"[^"]*)\s+from\s+(\w+)\)', r'\1") from \2'),
        # Pattern 5: Exception with from inside string
        (r'(raise\s+Exception\(f?"[^"]*)\s+from\s+(\w+)\)', r'\1") from \2'),
    ]

    # Find all Python files
    for py_file in Path(".").rglob("*.py"):
        if "venv" in str(py_file) or "build" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding='utf-8')

            # Check if file has the error pattern
            for pattern, _ in patterns:
                if re.search(pattern, content):
                    errors.append((py_file, 0, pattern))
                    break

        except Exception:
            continue

    return errors


def fix_file(filepath: Path) -> bool:
    """Fix syntax errors in a file."""
    try:
        content = filepath.read_text(encoding='utf-8')
        original_content = content

        # Fix patterns
        replacements = [
            # Fix: from e inside string literal - move it outside
            (r'(raise\s+\w+Exception\([^)]*)"([^"]*)\s+from\s+(\w+)', r'\1"\2) from \3'),
            # Fix: from e on wrong line with wrong indentation
            (r'(raise\s+\w+Exception\([^)]*\n\s*[^)]*)\n\s+from\s+(\w+)\)', r'\1\n        ) from \2'),
            # Fix: RuntimeError with from inside string
            (r'(raise\s+RuntimeError\("[^"]*)\s+from\s+(\w+)(\))?', r'\1") from \2'),
            # Fix: ValueError with from inside f-string
            (r'(raise\s+ValueError\(f"[^"]*)\s+from\s+(\w+)(\))?', r'\1") from \2'),
            # Fix: Exception with from inside f-string
            (r'(raise\s+Exception\(f"[^"]*)\s+from\s+(\w+)(\))?', r'\1") from \2'),
            # Fix: HTTPException patterns
            (r'(raise\s+HTTPException\([^)]+detail="[^"]*)\s+from\s+(\w+)', r'\1") from \2'),
            (r'(raise\s+HTTPException\([^)]+detail=str\([^)]+\)\s+from\s+(\w+)', r'\1)) from \2'),
            # Fix: SystemException patterns
            (r'(error_type="[^"]*"\n\s*)\s+from\s+(\w+)\)', r'\1) from \2'),
        ]

        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if content != original_content:
            filepath.write_text(content, encoding='utf-8')
            print(f"Fixed: {filepath}")
            return True

        return False

    except Exception as e:
        print(f"Error fixing {filepath}: {e}")
        return False


def main():
    """Main function to fix syntax errors."""
    print("Scanning for syntax errors from B904 fixes...")

    errors = find_syntax_errors()
    if not errors:
        print("No obvious syntax error patterns found")
        return 0

    print(f"Found potential syntax errors in {len(errors)} files")

    fixed_count = 0
    for filepath, _, _ in errors:
        if fix_file(filepath):
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
