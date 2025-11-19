#!/usr/bin/env python3
"""Fix incompatible None defaults by adding | None to type annotations.

This script parses MyPy output for 'Incompatible default for argument' errors
where default is None but type annotation doesn't include | None.

Usage:
    python scripts/fix_optional_defaults.py mypy_output.txt
"""

import argparse
import re
from pathlib import Path
from typing import Any


def parse_optional_default_errors(mypy_output_file: Path) -> list[dict[str, Any]]:
    """Parse MyPy output for incompatible None default errors.

    Args:
        mypy_output_file: Path to MyPy output file

    Returns:
        List of error dictionaries with file, line, argument, and type info
    """
    errors = []

    if not mypy_output_file.exists():
        print(f"❌ Error: File not found: {mypy_output_file}")
        return errors

    with open(mypy_output_file, encoding="utf-8") as f:
        for line in f:
            if (
                "Incompatible default for argument" in line
                and 'default has type "None"' in line
            ):
                # Parse: file.py:123: error: Incompatible default for argument "arg_name" (default has type "None", argument has type "str")  [assignment]
                match = re.match(
                    r'^(.+?):(\d+):\s+error:\s+Incompatible default for argument "([^"]+)"\s+\(default has type "None", argument has type "([^"]+)"\)',
                    line,
                )
                if match:
                    file_path_str, line_num_str, arg_name, arg_type = match.groups()
                    errors.append(
                        {
                            "file": Path(file_path_str),
                            "line": int(line_num_str),
                            "argument": arg_name,
                            "type": arg_type,
                        }
                    )

    return errors


def fix_optional_default(
    file_path: Path, line_num: int, arg_name: str, arg_type: str
) -> bool:
    """Add | None to argument type annotation.

    Args:
        file_path: Path to the file to modify
        line_num: Line number (1-indexed) containing the argument
        arg_name: Argument name
        arg_type: Current type annotation (without | None)

    Returns:
        True if annotation was modified, False otherwise
    """
    if not file_path.exists():
        print(f"⚠️  Warning: File not found: {file_path}")
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()

        if 0 < line_num <= len(lines):
            original_line = lines[line_num - 1]

            # Escape special regex characters in arg_type
            escaped_type = re.escape(arg_type)

            # Pattern: arg_name: Type = None → arg_name: Type | None = None
            # Multiple patterns to handle various formatting
            patterns = [
                # Standard: arg_name: Type = None
                (
                    rf"(\b{re.escape(arg_name)}):\s*({escaped_type})\s*=\s*None",
                    r"\1: \2 | None = None",
                ),
                # With trailing comma: arg_name: Type = None,
                (
                    rf"(\b{re.escape(arg_name)}):\s*({escaped_type})\s*=\s*None,",
                    r"\1: \2 | None = None,",
                ),
                # At end of line: arg_name: Type = None)
                (
                    rf"(\b{re.escape(arg_name)}):\s*({escaped_type})\s*=\s*None\)",
                    r"\1: \2 | None = None)",
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
                    f"✓ Added | None to {arg_name}: {arg_type} in {file_path}:{line_num}"
                )
                return True
            else:
                print(
                    f"⚠️  Warning: Could not match pattern for {arg_name}: {arg_type} in {file_path}:{line_num}"
                )
                print(f"    Line: {original_line}")
                return False
        else:
            print(f"⚠️  Warning: Line {line_num} out of range in {file_path}")
            return False

    except Exception as e:
        print(f"❌ Error processing {file_path}:{line_num}: {e}")
        return False


def fix_optional_default_errors(
    mypy_output_file: Path, dry_run: bool = False, limit: int | None = None
) -> dict[str, int]:
    """Fix optional default errors from MyPy output.

    Args:
        mypy_output_file: Path to MyPy output file
        dry_run: If True, only print what would be changed
        limit: Maximum number of errors to fix (None for all)

    Returns:
        Dictionary with statistics
    """
    stats = {"total_errors": 0, "fixed": 0, "skipped": 0, "files_modified": 0}

    errors = parse_optional_default_errors(mypy_output_file)
    stats["total_errors"] = len(errors)

    if limit:
        errors = errors[:limit]

    files_modified = set()

    for error in errors:
        if dry_run:
            print(
                f"Would add | None to '{error['argument']}: {error['type']}' in {error['file']}:{error['line']}"
            )
            stats["fixed"] += 1
        else:
            if fix_optional_default(
                error["file"], error["line"], error["argument"], error["type"]
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
        description="Fix incompatible None defaults by adding | None to type annotations"
    )
    parser.add_argument("mypy_output", type=Path, help="Path to MyPy output file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument("--limit", type=int, help="Maximum number of errors to fix")

    args = parser.parse_args()

    print(f"🔍 Scanning {args.mypy_output} for incompatible None defaults...")
    stats = fix_optional_default_errors(
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
