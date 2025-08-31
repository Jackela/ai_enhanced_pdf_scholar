#!/usr/bin/env python3
"""
Simple script to fix 'from e' syntax errors.
"""

import re
from pathlib import Path


def fix_file(filepath: Path) -> int:
    """Fix 'from e' patterns in a file."""
    try:
        content = filepath.read_text(encoding='utf-8')
        original = content

        # Fix patterns where 'from e' is inside the closing parenthesis
        content = re.sub(
            r'(error_type="[^"]*")\s+from\s+(\w+)\)',
            r'\1) from \2',
            content
        )

        # Fix patterns where 'from e' is inside the detail string
        content = re.sub(
            r'(detail="[^"]*)\s+from\s+(\w+)',
            r'\1") from \2',
            content
        )

        # Fix patterns where 'from e' is inside a string literal
        content = re.sub(
            r'(detail=f?"[^"]*)\s+from\s+(\w+)',
            r'\1") from \2',
            content
        )

        # Fix patterns with detail=str(e from e)
        content = re.sub(
            r'detail=str\(e\s+from\s+e\)',
            r'detail=str(e)) from e',
            content
        )

        # Fix RuntimeError pattern
        content = re.sub(
            r'raise RuntimeError\("([^"]*)\s+from\s+(\w+)\)',
            r'raise RuntimeError("\1") from \2',
            content
        )

        if content != original:
            filepath.write_text(content, encoding='utf-8')
            return 1
        return 0

    except Exception as e:
        print(f"Error fixing {filepath}: {e}")
        return 0


def main():
    """Main function."""
    total_fixed = 0

    # Fix specific directories
    for dir_path in ["backend/api/routes", "backend/api", "backend/services", "backend/core"]:
        path = Path(dir_path)
        if path.exists():
            for py_file in path.glob("*.py"):
                fixed = fix_file(py_file)
                if fixed:
                    print(f"Fixed: {py_file}")
                    total_fixed += fixed

    print(f"\nTotal files fixed: {total_fixed}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
