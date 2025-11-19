#!/usr/bin/env python3
"""Fix B904: Add 'from' clause to raise statements in except blocks.

This script automatically adds exception chaining to raise statements
inside except blocks to preserve the original exception context.
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import Any


class ExceptionChainingFixer(ast.NodeTransformer):
    """AST transformer to add exception chaining."""

    def __init__(self) -> None:
        self.fixes_applied = 0
        self.current_exception_var: str | None = None
        self.in_except_handler = False

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        """Track when we're inside an except handler."""
        old_in_except = self.in_except_handler
        old_exception_var = self.current_exception_var

        self.in_except_handler = True
        self.current_exception_var = node.name if node.name else "e"

        # Visit children
        self.generic_visit(node)

        self.in_except_handler = old_in_except
        self.current_exception_var = old_exception_var

        return node

    def visit_Raise(self, node: ast.Raise) -> Any:
        """Add 'from' clause to raise statements if missing."""
        # Only process raise statements inside except handlers
        if not self.in_except_handler:
            return node

        # Skip if already has 'from' clause
        if node.cause is not None:
            return node

        # Skip bare 're-raise' statements
        if node.exc is None:
            return node

        # Add 'from' clause using the caught exception variable
        if self.current_exception_var:
            node.cause = ast.Name(id=self.current_exception_var, ctx=ast.Load())
            self.fixes_applied += 1

        return node


def fix_exception_chaining_in_file(file_path: Path, dry_run: bool = False) -> int:
    """Fix exception chaining in a Python file.

    Args:
        file_path: Path to Python file
        dry_run: If True, don't write changes

    Returns:
        Number of fixes applied
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"⚠️  Syntax error in {file_path}: {e}")
        return 0
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return 0

    # Apply fixes
    fixer = ExceptionChainingFixer()
    new_tree = fixer.visit(tree)

    if fixer.fixes_applied == 0:
        return 0

    # Convert back to source code
    try:
        import astor  # type: ignore

        new_source = astor.to_source(new_tree)
    except ImportError:
        # Fallback: use ast.unparse (Python 3.9+)
        try:
            new_source = ast.unparse(new_tree)
        except AttributeError:
            print(
                "⚠️  Cannot convert AST back to source. Install 'astor' or use Python 3.9+"
            )
            return 0

    if dry_run:
        print(
            f"Would fix {fixer.fixes_applied} exception chaining issues in {file_path}"
        )
    else:
        file_path.write_text(new_source, encoding="utf-8")
        print(f"✓ Fixed {fixer.fixes_applied} issues in {file_path}")

    return fixer.fixes_applied


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fix B904 exception chaining issues")
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Python files or directories to fix",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes",
    )

    args = parser.parse_args()

    total_fixes = 0
    files_modified = 0

    for path in args.paths:
        if path.is_file() and path.suffix == ".py":
            fixes = fix_exception_chaining_in_file(path, args.dry_run)
            if fixes > 0:
                total_fixes += fixes
                files_modified += 1
        elif path.is_dir():
            for py_file in path.rglob("*.py"):
                fixes = fix_exception_chaining_in_file(py_file, args.dry_run)
                if fixes > 0:
                    total_fixes += fixes
                    files_modified += 1

    print("\n📊 Summary:")
    print(f"   Files modified: {files_modified}")
    print(f"   Total fixes: {total_fixes}")

    if args.dry_run:
        print("\n⚠️  DRY RUN - No files were modified")
    elif total_fixes > 0:
        print("\n✅ Done! Run ruff check to verify.")


if __name__ == "__main__":
    main()
