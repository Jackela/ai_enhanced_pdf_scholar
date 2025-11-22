#!/usr/bin/env python3
"""
Simple regex-based type-arg error fixer.

This script uses regex patterns to add missing type parameters.
Safer and simpler than libcst for this specific task.

Usage:
    python scripts/fix_type_arg_simple.py <file_path> [--dry-run]
    python scripts/fix_type_arg_simple.py --batch <file_list.txt>
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Type parameter patterns
TYPE_FIXES = [
    # dict without params
    (r"\bdict\b(?!\[)", "dict[str, Any]"),
    # list without params (but not in comments or strings)
    (r"\blist\b(?!\[)", "list[Any]"),
    # deque without params
    (r"\bdeque\b(?!\[)", "deque[Any]"),
    # set without params
    (r"\bset\b(?!\[)", "set[str]"),
    # asyncio.Task without params
    (r"\basyncio\.Task\b(?!\[)", "asyncio.Task[None]"),
    # Callable without params
    (r"\bCallable\b(?!\[)", "Callable[..., Any]"),
    # PriorityQueue without params
    (r"\bPriorityQueue\b(?!\[)", "PriorityQueue[Any]"),
    # Match without params (re.Match)
    (r"\bMatch\b(?!\[)", "Match[str]"),
]


def fix_file_simple(file_path: Path, dry_run: bool = False) -> tuple[bool, int]:
    """Fix type-arg errors using regex replacement."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content
        fixes_applied = 0

        # Apply each fix pattern
        for pattern, replacement in TYPE_FIXES:
            matches = list(re.finditer(pattern, content))
            if matches:
                content = re.sub(pattern, replacement, content)
                fixes_applied += len(matches)
                logger.debug(
                    f"  Fixed {len(matches)} instances of {pattern} → {replacement}"
                )

        if fixes_applied == 0:
            logger.info(f"✓ {file_path.name}: No type-arg fixes needed")
            return True, 0

        # Ensure typing imports
        needs_any = "Any" in content and "Any" not in original_content
        needs_typing_import = "from typing import" not in content

        if needs_any and needs_typing_import:
            # Add typing import at top after docstring
            lines = content.split("\n")
            insert_idx = 0
            in_docstring = False

            for i, line in enumerate(lines):
                if '"""' in line or "'''" in line:
                    if not in_docstring:
                        in_docstring = True
                    else:
                        insert_idx = i + 1
                        break
                elif not in_docstring and line.strip() and not line.startswith("#"):
                    insert_idx = i
                    break

            lines.insert(insert_idx, "from typing import Any\n")
            content = "\n".join(lines)
        elif needs_any:
            # Add Any to existing typing import
            content = re.sub(
                r"from typing import ([^\n]+)",
                lambda m: (
                    f"from typing import {m.group(1)}, Any"
                    if "Any" not in m.group(1)
                    else m.group(0)
                ),
                content,
                count=1,
            )

        if not dry_run:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"✓ {file_path.name}: Fixed {fixes_applied} type-arg errors")
        else:
            logger.info(
                f"[DRY RUN] Would fix {fixes_applied} type-arg errors in {file_path.name}"
            )

        return True, fixes_applied

    except Exception as e:
        logger.error(f"✗ {file_path.name}: {e}")
        return False, 0


def fix_files_batch(file_list_path: Path, dry_run: bool = False) -> None:
    """Fix multiple files from a list."""
    files = []
    for line in file_list_path.read_text().strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            file_path_str = line.split("#")[0].strip()
            files.append(Path(file_path_str))

    logger.info(f"Processing {len(files)} files from {file_list_path.name}")

    total_fixes = 0
    total_success = 0
    total_failed = 0

    for file_path in files:
        if not file_path.exists():
            logger.error(f"✗ File not found: {file_path}")
            total_failed += 1
            continue

        success, fixes = fix_file_simple(file_path, dry_run=dry_run)
        if success:
            total_success += 1
            total_fixes += fixes
        else:
            total_failed += 1

    logger.info("")
    logger.info("=" * 60)
    logger.info("Batch Processing Summary:")
    logger.info(f"  Total files: {len(files)}")
    logger.info(f"  Successful: {total_success}")
    logger.info(f"  Failed: {total_failed}")
    logger.info(f"  Total fixes: {total_fixes}")
    logger.info("=" * 60)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simple type-arg error fixer")

    parser.add_argument("file_path", type=Path, nargs="?", help="File to fix")
    parser.add_argument("--batch", type=Path, help="Batch file list")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args(argv)

    if args.batch and args.file_path:
        logger.error("Cannot specify both file_path and --batch")
        return 1

    if not args.batch and not args.file_path:
        logger.error("Must specify either file_path or --batch")
        return 1

    try:
        if args.batch:
            fix_files_batch(args.batch, dry_run=args.dry_run)
        else:
            if not args.file_path.exists():
                logger.error(f"File not found: {args.file_path}")
                return 1
            success, fixes = fix_file_simple(args.file_path, dry_run=args.dry_run)
            return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
