#!/usr/bin/env python3
"""Fix var-annotated errors by adding type annotations to variables.

This script parses MyPy output for 'Need type annotation for X' errors
and adds type annotations using the hints provided by MyPy.

Usage:
    python scripts/fix_var_annotated.py mypy_output.txt
"""

import argparse
import re
from pathlib import Path
from typing import Any


def parse_var_annotated_errors(mypy_output_file: Path) -> list[dict[str, Any]]:
    """Parse MyPy output for var-annotated errors.

    Args:
        mypy_output_file: Path to MyPy output file

    Returns:
        List of error dictionaries with file, line, variable, and hint info
    """
    errors: list[Any] = []

    if not mypy_output_file.exists():
        print(f"❌ Error: File not found: {mypy_output_file}")
        return errors

    with open(mypy_output_file, encoding="utf-8") as f:
        for line in f:
            if "var-annotated" in line and "Need type annotation for" in line:
                # Parse: file.py:123: error: Need type annotation for "var_name" (hint: "var_name: type = ...") [var-annotated]
                match = re.match(
                    r'^(.+?):(\d+):\s+error:\s+Need type annotation for "([^"]+)"(?:\s+\(hint:\s+"([^"]+)"\))?',
                    line,
                )
                if match:
                    file_path_str, line_num_str, var_name, hint = match.groups()
                    errors.append(
                        {
                            "file": Path(file_path_str),
                            "line": int(line_num_str),
                            "variable": var_name,
                            "hint": hint or "",
                        }
                    )

    return errors


def extract_type_from_hint(hint: str, var_name: str) -> str | None:
    """Extract type annotation from MyPy hint.

    Args:
        hint: MyPy hint string like "violations: list[<type>] = ..."
        var_name: Variable name

    Returns:
        Type annotation string or None if not extractable
    """
    if not hint:
        return None

    # Pattern 1: "var: list[<type>] = ..." → list[Any]
    if "list[<type>]" in hint:
        return "list[Any]"

    # Pattern 2: "var: dict[<type>, <type>] = ..." → dict[str, Any]
    if "dict[<type>, <type>]" in hint:
        return "dict[str, Any]"

    # Pattern 3: "var: set[<type>] = ..." → set[Any]
    if "set[<type>]" in hint:
        return "set[Any]"

    # Pattern 4: No hint provided → use Any
    return None


def fix_variable_annotation(
    file_path: Path, line_num: int, var_name: str, type_annotation: str
) -> bool:
    """Add type annotation to a variable.

    Args:
        file_path: Path to the file to modify
        line_num: Line number (1-indexed) containing the variable
        var_name: Variable name
        type_annotation: Type annotation to add

    Returns:
        True if annotation was added, False otherwise
    """
    if not file_path.exists():
        print(f"⚠️  Warning: File not found: {file_path}")
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()

        if 0 < line_num <= len(lines):
            original_line = lines[line_num - 1]

            # Pattern: var_name = value → var_name: type = value
            # Handle various whitespace patterns
            patterns = [
                # Class attribute with self: self.var = value
                (
                    rf"^(\s*)(self\.{re.escape(var_name)})\s*=\s*(.+)$",
                    rf"\1self.{var_name}: {type_annotation} = \3",
                ),
                # Simple assignment: var = value
                (
                    rf"^(\s*)({re.escape(var_name)})\s*=\s*(.+)$",
                    rf"\1{var_name}: {type_annotation} = \3",
                ),
                # Dictionary comprehension or list comprehension
                (
                    rf"^(\s*)({re.escape(var_name)})\s*=\s*(\{{[^}}]*\}}|\[[^\]]*\])$",
                    rf"\1{var_name}: {type_annotation} = \3",
                ),
            ]

            modified_line = original_line
            for pattern, replacement in patterns:
                new_line = re.sub(pattern, replacement, original_line)
                if new_line != original_line:
                    modified_line = new_line
                    break

            if modified_line != original_line:
                lines[line_num - 1] = modified_line
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                print(
                    f"✓ Added type annotation to {var_name} in {file_path}:{line_num}"
                )
                return True
            else:
                print(
                    f"⚠️  Warning: Could not match pattern for {var_name} in {file_path}:{line_num}"
                )
                print(f"    Line: {original_line}")
                return False
        else:
            print(f"⚠️  Warning: Line {line_num} out of range in {file_path}")
            return False

    except Exception as e:
        print(f"❌ Error processing {file_path}:{line_num}: {e}")
        return False


def fix_var_annotated_errors(
    mypy_output_file: Path, dry_run: bool = False, limit: int | None = None
) -> dict[str, int]:
    """Fix var-annotated errors from MyPy output.

    Args:
        mypy_output_file: Path to MyPy output file
        dry_run: If True, only print what would be changed
        limit: Maximum number of errors to fix (None for all)

    Returns:
        Dictionary with statistics
    """
    stats = {"total_errors": 0, "fixed": 0, "skipped": 0, "files_modified": 0}

    errors = parse_var_annotated_errors(mypy_output_file)
    stats["total_errors"] = len(errors)

    if limit:
        errors = errors[:limit]

    files_modified = set()

    for error in errors:
        var_name = error["variable"]
        hint = error["hint"]
        type_annotation = extract_type_from_hint(hint, var_name)

        if not type_annotation:
            # Fallback to Any for variables without clear hints
            type_annotation = "Any"

        if dry_run:
            print(
                f"Would add '{var_name}: {type_annotation}' to {error['file']}:{error['line']}"
            )
            stats["fixed"] += 1
        else:
            if fix_variable_annotation(
                error["file"], error["line"], var_name, type_annotation
            ):
                stats["fixed"] += 1
                files_modified.add(error["file"])
            else:
                stats["skipped"] += 1

    stats["files_modified"] = len(files_modified)
    return stats


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fix var-annotated errors by adding type annotations"
    )
    parser.add_argument("mypy_output", type=Path, help="Path to MyPy output file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument("--limit", type=int, help="Maximum number of errors to fix")

    args = parser.parse_args()

    print(f"🔍 Scanning {args.mypy_output} for var-annotated errors...")
    stats = fix_var_annotated_errors(
        args.mypy_output, dry_run=args.dry_run, limit=args.limit
    )

    print("\n📊 Summary:")
    print(f"   Total errors found: {stats['total_errors']}")
    print(f"   Fixed: {stats['fixed']}")
    print(f"   Skipped: {stats['skipped']}")
    print(f"   Files modified: {stats['files_modified']}")

    if args.dry_run:
        print("\n⚠️  DRY RUN - No files were modified")
    elif stats["fixed"] > 0:
        print("\n✅ Done! Run MyPy again to verify the fixes.")


if __name__ == "__main__":
    main()
