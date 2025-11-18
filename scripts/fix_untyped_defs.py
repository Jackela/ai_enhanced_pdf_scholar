#!/usr/bin/env python3
"""
Auto-fix script for MyPy no-untyped-def errors using libcst.

This script automatically adds type annotations to functions that are missing them:
- Functions without return statements: -> None
- __init__, __new__, __enter__, __exit__ methods: -> None
- Other functions without annotations: -> Any (requires manual refinement)

Usage:
    python scripts/fix_untyped_defs.py <file_path> [--dry-run] [--verbose]
    python scripts/fix_untyped_defs.py --batch <file_list.txt>
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import libcst as cst
from libcst import metadata

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class UntypedDefFixer(cst.CSTTransformer):
    """Transformer that adds type annotations to untyped function definitions."""

    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    def __init__(self) -> None:
        super().__init__()
        self.fixes_applied = 0
        self.functions_processed = 0

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Add return type annotation if missing."""
        self.functions_processed += 1

        # Skip if already has return type annotation
        if updated_node.returns is not None:
            return updated_node

        func_name = updated_node.name.value

        # Determine appropriate return type
        if self._should_be_none_return(func_name, updated_node):
            return_annotation = self._create_none_annotation()
            logger.debug(f"Adding '-> None' to {func_name}")
        else:
            return_annotation = self._create_any_annotation()
            logger.debug(f"Adding '-> Any' to {func_name} (needs manual review)")

        self.fixes_applied += 1
        return updated_node.with_changes(returns=return_annotation)

    def _should_be_none_return(self, func_name: str, node: cst.FunctionDef) -> bool:
        """Check if function should have -> None annotation."""
        # Special methods that always return None
        none_methods = {
            "__init__",
            "__new__",
            "__del__",
            "__enter__",
            "__aenter__",
            "__exit__",
            "__aexit__",
            "__setattr__",
            "__delattr__",
            "__setitem__",
            "__delitem__",
        }

        if func_name in none_methods:
            return True

        # Check if function has explicit return statements with values
        has_return_value = self._has_return_with_value(node)

        return not has_return_value

    def _has_return_with_value(self, node: cst.FunctionDef) -> bool:
        """Check if function contains return statements with values."""

        class ReturnVisitor(cst.CSTVisitor):
            def __init__(self) -> None:
                self.has_value_return = False

            def visit_Return(self, node: cst.Return) -> None:
                # Return with value (not just 'return' or 'return None')
                if node.value is not None:
                    if (
                        not isinstance(node.value, cst.Name)
                        or node.value.value != "None"
                    ):
                        self.has_value_return = True

        visitor = ReturnVisitor()
        node.body.visit(visitor)
        return visitor.has_value_return

    def _create_none_annotation(self) -> cst.Annotation:
        """Create '-> None' annotation."""
        return cst.Annotation(annotation=cst.Name("None"))

    def _create_any_annotation(self) -> cst.Annotation:
        """Create '-> Any' annotation."""
        return cst.Annotation(annotation=cst.Name("Any"))


def fix_file(
    file_path: Path, dry_run: bool = False, verbose: bool = False
) -> tuple[bool, int]:
    """
    Fix untyped definitions in a single file.

    Args:
        file_path: Path to Python file
        dry_run: If True, don't write changes to disk
        verbose: Enable verbose logging

    Returns:
        Tuple of (success, fixes_applied)
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    try:
        # Read source file
        source_code = file_path.read_text(encoding="utf-8")

        # Parse to CST
        source_tree = cst.parse_module(source_code)

        # Apply fixes
        wrapper = metadata.MetadataWrapper(source_tree)
        fixer = UntypedDefFixer()
        fixed_tree = wrapper.visit(fixer)

        if fixer.fixes_applied == 0:
            logger.info(
                f"✓ {file_path.name}: No fixes needed ({fixer.functions_processed} functions checked)"
            )
            return True, 0

        # Check if Any was added (needs manual review)
        fixed_code = fixed_tree.code
        needs_review = "-> Any" in fixed_code and "-> Any" not in source_code

        if not dry_run:
            # Add typing import if not present
            if fixer.fixes_applied > 0 and "from typing import" not in source_code:
                fixed_code = "from typing import Any\n\n" + fixed_code

            # Write back to file
            file_path.write_text(fixed_code, encoding="utf-8")

            status = "⚠" if needs_review else "✓"
            logger.info(
                f"{status} {file_path.name}: Fixed {fixer.fixes_applied} functions "
                f"({fixer.functions_processed} total)"
            )
            if needs_review:
                logger.warning(
                    "  ⚠ Contains '-> Any' - requires manual type refinement"
                )
        else:
            logger.info(
                f"[DRY RUN] Would fix {fixer.fixes_applied} functions in {file_path.name}"
            )

        return True, fixer.fixes_applied

    except Exception as e:
        logger.error(f"✗ {file_path.name}: {type(e).__name__}: {e}")
        return False, 0


def fix_files_batch(
    file_list_path: Path, dry_run: bool = False, verbose: bool = False
) -> None:
    """
    Fix multiple files from a file list.

    Args:
        file_list_path: Path to text file with one file path per line
        dry_run: If True, don't write changes
        verbose: Enable verbose logging
    """
    files = []
    for line in file_list_path.read_text().strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            files.append(Path(line))

    logger.info(f"Processing {len(files)} files from {file_list_path.name}")

    total_fixes = 0
    total_success = 0
    total_failed = 0

    for file_path in files:
        if not file_path.exists():
            logger.error(f"✗ File not found: {file_path}")
            total_failed += 1
            continue

        success, fixes = fix_file(file_path, dry_run=dry_run, verbose=verbose)
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


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Auto-fix MyPy no-untyped-def errors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on single file
  python scripts/fix_untyped_defs.py src/services/document_service.py --dry-run

  # Fix single file
  python scripts/fix_untyped_defs.py src/services/document_service.py

  # Fix batch of files
  python scripts/fix_untyped_defs.py --batch files_to_fix.txt

  # Verbose mode
  python scripts/fix_untyped_defs.py src/services/document_service.py --verbose
        """,
    )

    parser.add_argument(
        "file_path", type=Path, nargs="?", help="Path to Python file to fix"
    )
    parser.add_argument(
        "--batch", type=Path, help="Path to file containing list of files to fix"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args(argv)

    # Validate arguments
    if args.batch and args.file_path:
        logger.error("Cannot specify both file_path and --batch")
        return 1

    if not args.batch and not args.file_path:
        logger.error("Must specify either file_path or --batch")
        parser.print_help()
        return 1

    try:
        if args.batch:
            fix_files_batch(args.batch, dry_run=args.dry_run, verbose=args.verbose)
        else:
            if not args.file_path.exists():
                logger.error(f"File not found: {args.file_path}")
                return 1

            success, fixes = fix_file(
                args.file_path, dry_run=args.dry_run, verbose=args.verbose
            )
            return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
