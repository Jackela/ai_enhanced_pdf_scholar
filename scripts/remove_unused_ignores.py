#!/usr/bin/env python3
"""Remove unused type: ignore comments reported by MyPy.

This script parses MyPy output for 'Unused "type: ignore" comment' errors
and removes the type: ignore comments from the specified lines.

Usage:
    python scripts/remove_unused_ignores.py mypy_output.txt
"""

import argparse
import re
from pathlib import Path


def remove_unused_ignores(
    mypy_output_file: Path, dry_run: bool = False
) -> dict[str, int]:
    """Parse MyPy output and remove unused type: ignore comments.

    Args:
        mypy_output_file: Path to MyPy output file
        dry_run: If True, only print what would be changed without modifying files

    Returns:
        Dictionary with statistics: {'files_modified': int, 'ignores_removed': int}
    """
    stats = {"files_modified": 0, "ignores_removed": 0}
    files_processed = set()

    if not mypy_output_file.exists():
        print(f"❌ Error: File not found: {mypy_output_file}")
        return stats

    with open(mypy_output_file, encoding="utf-8") as f:
        for line in f:
            if 'Unused "type: ignore"' in line or "Unused type: ignore" in line:
                # Parse: file.py:123: error: Unused "type: ignore" comment
                match = re.match(r"^(.+?):(\d+):", line.strip())
                if match:
                    file_path_str, line_num_str = match.groups()
                    file_path = Path(file_path_str)
                    line_num = int(line_num_str)

                    if dry_run:
                        print(f"Would remove type: ignore from {file_path}:{line_num}")
                    else:
                        if remove_ignore_from_file(file_path, line_num):
                            stats["ignores_removed"] += 1
                            files_processed.add(file_path)

    stats["files_modified"] = len(files_processed)
    return stats


def remove_ignore_from_file(file_path: Path, line_num: int) -> bool:
    """Remove type: ignore comment from specific line.

    Args:
        file_path: Path to the file to modify
        line_num: Line number (1-indexed) containing the unused ignore

    Returns:
        True if comment was removed, False otherwise
    """
    if not file_path.exists():
        print(f"⚠️  Warning: File not found: {file_path}")
        return False

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()

        if 0 < line_num <= len(lines):
            original_line = lines[line_num - 1]

            # Remove type: ignore comment (various formats)
            # Matches: "# type: ignore", "# type: ignore[error-code]", etc.
            modified_line = re.sub(
                r"\s*#\s*type:\s*ignore(?:\[[\w-]+\])?\s*$", "", original_line
            )

            if original_line != modified_line:
                lines[line_num - 1] = modified_line
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                print(f"✓ Removed unused ignore from {file_path}:{line_num}")
                return True
            else:
                print(
                    f"⚠️  Warning: No type: ignore found on line {line_num} in {file_path}"
                )
                return False
        else:
            print(f"⚠️  Warning: Line {line_num} out of range in {file_path}")
            return False

    except Exception as e:
        print(f"❌ Error processing {file_path}:{line_num}: {e}")
        return False


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Remove unused type: ignore comments from MyPy output"
    )
    parser.add_argument("mypy_output", type=Path, help="Path to MyPy output file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )

    args = parser.parse_args()

    print(f"🔍 Scanning {args.mypy_output} for unused type: ignore comments...")
    stats = remove_unused_ignores(args.mypy_output, dry_run=args.dry_run)

    print("\n📊 Summary:")
    print(f"   Files modified: {stats['files_modified']}")
    print(f"   Ignores removed: {stats['ignores_removed']}")

    if args.dry_run:
        print("\n⚠️  DRY RUN - No files were modified")
    elif stats["ignores_removed"] > 0:
        print("\n✅ Done! Run MyPy again to verify the fixes.")


if __name__ == "__main__":
    main()
