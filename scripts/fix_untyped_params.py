#!/usr/bin/env python3
"""
Auto-fix script for MyPy no-untyped-def errors (PARAMETER ANNOTATIONS).

This script adds type annotations to function parameters that are missing them:
- **kwargs without type → **kwargs: Any
- *args without type → *args: Any
- Regular parameters → inferred from name or Any

Usage:
    python scripts/fix_untyped_params.py <file_path> [--dry-run] [--verbose]
    python scripts/fix_untyped_params.py --batch <file_list.txt>
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


class ParameterTypeFixer(cst.CSTTransformer):
    """Transformer that adds type annotations to untyped function parameters."""

    METADATA_DEPENDENCIES = (metadata.ScopeProvider,)

    def __init__(self, conservative: bool = True) -> None:
        super().__init__()
        self.fixes_applied = 0
        self.functions_processed = 0
        self.conservative = conservative  # If True, use Any; if False, infer types

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Add parameter type annotations if missing."""
        self.functions_processed += 1

        func_name = updated_node.name.value

        # Fix parameters
        new_params = self._fix_parameters(updated_node.params, func_name)

        if new_params != updated_node.params:
            self.fixes_applied += 1
            logger.debug(f"Adding parameter types to {func_name}")
            return updated_node.with_changes(params=new_params)

        return updated_node

    def _fix_parameters(self, params: cst.Parameters, func_name: str) -> cst.Parameters:
        """Add type annotations to untyped parameters."""
        modified = False

        # Fix regular parameters
        new_params = []
        for param in params.params:
            if param.annotation is None and param.name.value not in ("self", "cls"):
                new_param = self._annotate_param(param, func_name)
                new_params.append(new_param)
                modified = True
            else:
                new_params.append(param)

        # Fix *args if present and untyped
        new_star_arg = params.star_arg
        if (
            params.star_arg
            and isinstance(params.star_arg, cst.Param)
            and params.star_arg.annotation is None
        ):
            new_star_arg = params.star_arg.with_changes(
                annotation=cst.Annotation(annotation=cst.Name("Any"))
            )
            modified = True
            logger.debug(f"  Adding type to *{params.star_arg.name.value}: Any")

        # Fix **kwargs if present and untyped
        new_kwarg = params.star_kwarg
        if params.star_kwarg and params.star_kwarg.annotation is None:
            new_kwarg = params.star_kwarg.with_changes(
                annotation=cst.Annotation(annotation=cst.Name("Any"))
            )
            modified = True
            logger.debug(f"  Adding type to **{params.star_kwarg.name.value}: Any")

        if not modified:
            return params

        return params.with_changes(
            params=new_params,
            star_arg=new_star_arg,
            star_kwarg=new_kwarg,
        )

    def _annotate_param(self, param: cst.Param, func_name: str) -> cst.Param:
        """Add annotation to a single parameter."""
        param_name = param.name.value

        # Infer type from parameter name (conservative approach)
        if self.conservative:
            inferred_type = "Any"
        else:
            inferred_type = self._infer_type_from_name(param_name)

        logger.debug(f"  Adding type to {param_name}: {inferred_type}")

        return param.with_changes(
            annotation=cst.Annotation(annotation=cst.Name(inferred_type))
        )

    def _infer_type_from_name(self, param_name: str) -> str:
        """
        Infer parameter type from name (aggressive mode).

        Conservative mode should use 'Any' for safety.
        """
        # Common parameter name patterns
        type_hints = {
            # IDs and counts
            "id": "int",
            "document_id": "int",
            "user_id": "int",
            "file_id": "int",
            "index_id": "int",
            "count": "int",
            "limit": "int",
            "offset": "int",
            "size": "int",
            "length": "int",
            # Strings
            "message": "str",
            "text": "str",
            "query": "str",
            "name": "str",
            "key": "str",
            "value": "str",
            "error": "str",
            "description": "str",
            # Booleans
            "enabled": "bool",
            "strict": "bool",
            "required": "bool",
            "valid": "bool",
            "success": "bool",
            # Paths
            "path": "Path",
            "file_path": "Path",
            "dir_path": "Path",
        }

        # Check exact match
        if param_name in type_hints:
            return type_hints[param_name]

        # Check patterns (ends with)
        if param_name.endswith("_id"):
            return "int"
        if param_name.endswith("_path"):
            return "Path"
        if param_name.endswith("_count") or param_name.endswith("_size"):
            return "int"

        # Default to Any for safety
        return "Any"


def fix_file(
    file_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
    conservative: bool = True,
) -> tuple[bool, int]:
    """
    Fix untyped parameters in a single file.

    Args:
        file_path: Path to Python file
        dry_run: If True, don't write changes to disk
        verbose: Enable verbose logging
        conservative: If True, use Any; if False, infer types

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
        fixer = ParameterTypeFixer(conservative=conservative)
        fixed_tree = wrapper.visit(fixer)

        if fixer.fixes_applied == 0:
            logger.info(
                f"✓ {file_path.name}: No fixes needed "
                f"({fixer.functions_processed} functions checked)"
            )
            return True, 0

        # Get fixed code
        fixed_code = fixed_tree.code

        if not dry_run:
            # Ensure typing imports are present
            if ": Any" in fixed_code or "-> Any" in fixed_code:
                if "from typing import" not in source_code:
                    # Add typing import at top
                    fixed_code = "from typing import Any\n\n" + fixed_code
                elif "Any" not in source_code:
                    # Add Any to existing typing import
                    fixed_code = re.sub(
                        r"from typing import ([^\n]+)",
                        lambda m: (
                            f"from typing import {m.group(1)}, Any"
                            if "Any" not in m.group(1)
                            else m.group(0)
                        ),
                        fixed_code,
                        count=1,
                    )

            # Add Path import if needed
            if ": Path" in fixed_code and "from pathlib import Path" not in source_code:
                if "from typing import" in fixed_code:
                    fixed_code = re.sub(
                        r"(from typing import [^\n]+)",
                        r"\1\nfrom pathlib import Path",
                        fixed_code,
                        count=1,
                    )
                else:
                    fixed_code = "from pathlib import Path\n" + fixed_code

            # Write back to file
            file_path.write_text(fixed_code, encoding="utf-8")

            logger.info(
                f"✓ {file_path.name}: Fixed {fixer.fixes_applied} functions "
                f"({fixer.functions_processed} total)"
            )
        else:
            logger.info(
                f"[DRY RUN] Would fix {fixer.fixes_applied} functions "
                f"in {file_path.name}"
            )

        return True, fixer.fixes_applied

    except Exception as e:
        logger.error(f"✗ {file_path.name}: {type(e).__name__}: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        return False, 0


def fix_files_batch(
    file_list_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
    conservative: bool = True,
) -> None:
    """
    Fix multiple files from a file list.

    Args:
        file_list_path: Path to text file with one file path per line
        dry_run: If True, don't write changes
        verbose: Enable verbose logging
        conservative: If True, use Any; if False, infer types
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

    for file_path in files:
        if not file_path.exists():
            logger.error(f"✗ File not found: {file_path}")
            total_failed += 1
            continue

        success, fixes = fix_file(
            file_path, dry_run=dry_run, verbose=verbose, conservative=conservative
        )
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
    parser = argparse.ArgumentParser(
        description="Auto-fix MyPy no-untyped-def parameter errors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on single file (conservative mode)
  python scripts/fix_untyped_params.py src/services/rag/exceptions.py --dry-run

  # Fix single file with Any types (safe)
  python scripts/fix_untyped_params.py src/services/rag/exceptions.py

  # Fix with type inference (aggressive)
  python scripts/fix_untyped_params.py src/services/rag/exceptions.py --infer

  # Fix batch of files
  python scripts/fix_untyped_params.py --batch wave1_files.txt

  # Verbose mode
  python scripts/fix_untyped_params.py src/services/rag/exceptions.py --verbose
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
    parser.add_argument(
        "--infer",
        action="store_true",
        help="Infer specific types from parameter names (default: use Any)",
    )

    args = parser.parse_args(argv)

    # Validate arguments
    if args.batch and args.file_path:
        logger.error("Cannot specify both file_path and --batch")
        return 1

    if not args.batch and not args.file_path:
        logger.error("Must specify either file_path or --batch")
        parser.print_help()
        return 1

    conservative = not args.infer

    try:
        if args.batch:
            fix_files_batch(
                args.batch,
                dry_run=args.dry_run,
                verbose=args.verbose,
                conservative=conservative,
            )
        else:
            if not args.file_path.exists():
                logger.error(f"File not found: {args.file_path}")
                return 1

            success, fixes = fix_file(
                args.file_path,
                dry_run=args.dry_run,
                verbose=args.verbose,
                conservative=conservative,
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
