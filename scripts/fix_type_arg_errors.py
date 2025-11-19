#!/usr/bin/env python3
"""
Auto-fix script for MyPy type-arg errors using libcst.

This script adds missing type parameters to generic types:
- dict → dict[str, Any]
- list → list[Any]
- deque → deque[Any]
- asyncio.Task → asyncio.Task[None]
- set → set[str]
- tuple → tuple[Any, ...]
- Callable → Callable[..., Any] (conservative)

Usage:
    python scripts/fix_type_arg_errors.py <file_path> [--dry-run] [--verbose]
    python scripts/fix_type_arg_errors.py --batch <file_list.txt>
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import libcst as cst
from libcst import metadata


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Type parameter mappings (conservative defaults)
TYPE_PARAM_DEFAULTS = {
    "dict": "[str, Any]",
    "list": "[Any]",
    "deque": "[Any]",
    "set": "[str]",
    "Task": "[None]",  # asyncio.Task
    "Callable": "[..., Any]",
    "PriorityQueue": "[Any]",
    "CircuitBreaker": "[Any]",
    "Generator": "[Any, None, None]",
    "Match": "[str]",  # re.Match
}


class TypeArgFixer(cst.CSTTransformer):
    """Transformer that adds missing type parameters to generic types."""

    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    def __init__(self) -> None:
        super().__init__()
        self.fixes_applied = 0
        self.types_fixed: dict[str, int] = {}

    def leave_Annotation(
        self, original_node: cst.Annotation, updated_node: cst.Annotation
    ) -> cst.Annotation:
        """Add type parameters to annotations missing them."""
        annotation = updated_node.annotation

        # Check if it's a simple Name (like 'dict', 'list') without subscript
        if isinstance(annotation, cst.Name):
            type_name = annotation.value
            if type_name in TYPE_PARAM_DEFAULTS:
                # Add type parameters
                params_str = TYPE_PARAM_DEFAULTS[type_name]
                new_annotation = self._add_type_params(annotation, params_str)
                self.fixes_applied += 1
                self.types_fixed[type_name] = self.types_fixed.get(type_name, 0) + 1
                logger.debug(f"  Fixed {type_name} → {type_name}{params_str}")
                return updated_node.with_changes(annotation=new_annotation)

        # Check for asyncio.Task or similar module.Type patterns
        elif isinstance(annotation, cst.Attribute):
            # Handle asyncio.Task, collections.deque, etc.
            if isinstance(annotation.value, cst.Name):
                module_name = annotation.value.value
                attr_name = annotation.attr.value

                if module_name == "asyncio" and attr_name == "Task":
                    params_str = TYPE_PARAM_DEFAULTS["Task"]
                    new_annotation = self._add_type_params_to_attribute(
                        annotation, params_str
                    )
                    self.fixes_applied += 1
                    self.types_fixed["Task"] = self.types_fixed.get("Task", 0) + 1
                    logger.debug(f"  Fixed asyncio.Task → asyncio.Task{params_str}")
                    return updated_node.with_changes(annotation=new_annotation)

        return updated_node

    def _add_type_params(self, name_node: cst.Name, params_str: str) -> cst.Subscript:
        """Convert Name to Subscript with type parameters."""
        # Parse the params_str to create proper CST nodes
        # For example: "[str, Any]" → Subscript with Index containing tuple

        # Remove brackets
        params_str = params_str.strip("[]")

        if params_str == "..., Any":
            # Special case for Callable[..., Any] - create tuple with ellipsis literal
            slice_node = cst.Index(
                value=cst.Tuple(
                    elements=[
                        cst.Element(cst.Ellipsis()),
                        cst.Element(cst.Name("Any")),
                    ]
                )
            )
        elif ", " in params_str:
            # Multiple parameters like "str, Any"
            param_parts = params_str.split(", ")
            slice_node = cst.Index(
                value=cst.Tuple(
                    elements=[
                        cst.Element(cst.Name(part.strip()))
                        for part in param_parts
                    ]
                )
            )
        else:
            # Single parameter like "Any"
            slice_node = cst.Index(cst.Name(params_str))

        return cst.Subscript(value=name_node, slice=slice_node)

    def _add_type_params_to_attribute(
        self, attr_node: cst.Attribute, params_str: str
    ) -> cst.Subscript:
        """Convert Attribute (like asyncio.Task) to Subscript with type parameters."""
        params_str = params_str.strip("[]")

        if ", " in params_str:
            param_parts = params_str.split(", ")
            slice_node = cst.Index(
                value=cst.Tuple(
                    elements=[
                        cst.Element(cst.Name(part.strip()))
                        for part in param_parts
                    ]
                )
            )
        else:
            slice_node = cst.Index(cst.Name(params_str))

        return cst.Subscript(value=attr_node, slice=slice_node)


def fix_file(
    file_path: Path, dry_run: bool = False, verbose: bool = False
) -> tuple[bool, int, dict[str, int]]:
    """
    Fix type-arg errors in a single file.

    Args:
        file_path: Path to Python file
        dry_run: If True, don't write changes to disk
        verbose: Enable verbose logging

    Returns:
        Tuple of (success, fixes_applied, types_fixed_dict)
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
        fixer = TypeArgFixer()
        fixed_tree = wrapper.visit(fixer)

        if fixer.fixes_applied == 0:
            logger.info(f"✓ {file_path.name}: No type-arg fixes needed")
            return True, 0, {}

        # Get fixed code
        fixed_code = fixed_tree.code

        if not dry_run:
            # Ensure typing imports are present
            needs_any = "Any" in fixed_code and "from typing import" in source_code
            needs_typing_import = (
                "Any" in fixed_code and "from typing import" not in source_code
            )

            if needs_typing_import:
                # Add typing import at top
                fixed_code = "from typing import Any\n\n" + fixed_code
            elif needs_any and "Any" not in source_code:
                # Add Any to existing typing import
                fixed_code = re.sub(
                    r"from typing import ([^\n]+)",
                    lambda m: f"from typing import {m.group(1)}, Any"
                    if "Any" not in m.group(1)
                    else m.group(0),
                    fixed_code,
                    count=1,
                )

            # Write back to file
            file_path.write_text(fixed_code, encoding="utf-8")

            types_summary = ", ".join(
                f"{k}({v})" for k, v in fixer.types_fixed.items()
            )
            logger.info(
                f"✓ {file_path.name}: Fixed {fixer.fixes_applied} type-arg errors "
                f"[{types_summary}]"
            )
        else:
            types_summary = ", ".join(
                f"{k}({v})" for k, v in fixer.types_fixed.items()
            )
            logger.info(
                f"[DRY RUN] Would fix {fixer.fixes_applied} type-arg errors "
                f"in {file_path.name} [{types_summary}]"
            )

        return True, fixer.fixes_applied, fixer.types_fixed

    except Exception as e:
        logger.error(f"✗ {file_path.name}: {type(e).__name__}: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        return False, 0, {}


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
            # Remove inline comments
            file_path_str = line.split("#")[0].strip()
            files.append(Path(file_path_str))

    logger.info(f"Processing {len(files)} files from {file_list_path.name}")

    total_fixes = 0
    total_success = 0
    total_failed = 0
    all_types_fixed: dict[str, int] = {}

    for file_path in files:
        if not file_path.exists():
            logger.error(f"✗ File not found: {file_path}")
            total_failed += 1
            continue

        success, fixes, types_dict = fix_file(
            file_path, dry_run=dry_run, verbose=verbose
        )
        if success:
            total_success += 1
            total_fixes += fixes
            for type_name, count in types_dict.items():
                all_types_fixed[type_name] = all_types_fixed.get(type_name, 0) + count
        else:
            total_failed += 1

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"Batch Processing Summary:")
    logger.info(f"  Total files: {len(files)}")
    logger.info(f"  Successful: {total_success}")
    logger.info(f"  Failed: {total_failed}")
    logger.info(f"  Total fixes: {total_fixes}")
    logger.info(f"  Types fixed: {dict(all_types_fixed)}")
    logger.info("=" * 60)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Auto-fix MyPy type-arg errors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on single file
  python scripts/fix_type_arg_errors.py src/services/error_recovery.py --dry-run

  # Fix single file
  python scripts/fix_type_arg_errors.py src/services/error_recovery.py

  # Fix batch of files
  python scripts/fix_type_arg_errors.py --batch batch_files.txt

  # Verbose mode
  python scripts/fix_type_arg_errors.py src/services/error_recovery.py --verbose
        """,
    )

    parser.add_argument("file_path", type=Path, nargs="?", help="Path to Python file to fix")
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

            success, fixes, types_dict = fix_file(
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
