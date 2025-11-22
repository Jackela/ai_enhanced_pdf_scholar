#!/usr/bin/env python3
"""Run mypy against only the Python files changed relative to a base ref."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "origin/main"
DEFAULT_PATHS = ("src", "backend", "tests", "scripts")
ERROR_PATTERN = re.compile(r"Found (\d+) errors?")


class MypyResult(NamedTuple):
    returncode: int
    errors: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run mypy on changed Python files vs a base reference",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help="Git base reference to compare against (ignored when --staged is set)",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Use staged changes instead of a base reference",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=DEFAULT_PATHS,
        help="Path prefixes to include when searching for changed files",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50,
        help="Maximum number of files to pass to mypy at once",
    )
    parser.add_argument(
        "--count-file",
        type=Path,
        help="Optional file to write the total error count to",
    )
    parser.add_argument(
        "mypy_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments forwarded to mypy (prefix with --)",
    )
    parser.add_argument(
        "--allow-prefix",
        action="append",
        default=[],
        help=(
            "Only include changed files whose path starts with one of these prefixes. "
            "When not provided, all changed Python files are considered."
        ),
    )
    return parser.parse_args()


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )


def ref_exists(ref: str) -> bool:
    return run(["git", "rev-parse", "--verify", "--quiet", ref]).returncode == 0


def resolve_base_ref(base: str) -> str:
    if ref_exists(base):
        return base

    if base == DEFAULT_BASE and ref_exists("main"):
        print("Base 'origin/main' not found. Falling back to 'main'.")
        return "main"

    print(
        f"Base ref '{base}' not found. Use --base <ref> to specify an existing branch.",
        file=sys.stderr,
    )
    sys.exit(1)


def gather_changed_files(base: str, staged: bool, paths: Iterable[str]) -> list[str]:
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"]
    if staged:
        cmd.append("--cached")
    else:
        resolved = resolve_base_ref(base)
        cmd.append(f"{resolved}...HEAD")
    cmd.append("--")
    cmd.extend(paths)
    result = run(cmd)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip(), file=sys.stderr)
        sys.exit(result.returncode)
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [f for f in files if f.endswith(".py")]


def run_mypy_chunk(files: list[str], extra_args: list[str]) -> MypyResult:
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--ignore-missing-imports",
        "--hide-error-context",
        "--follow-imports=skip",
        *extra_args,
        *files,
    ]
    completed = subprocess.run(  # noqa: S603
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )

    # Re-emit stdout/stderr so GitHub logs show the mypy diagnostics.
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    errors = 0
    match = ERROR_PATTERN.search(f"{completed.stdout}\n{completed.stderr}")
    if match:
        errors = int(match.group(1))
    elif completed.returncode != 0:
        errors = -1  # Unable to determine exact count

    return MypyResult(completed.returncode, errors)


def write_count(count_file: Path | None, count: int) -> None:
    if count_file:
        count_file.parent.mkdir(parents=True, exist_ok=True)
        count_file.write_text(str(count), encoding="utf-8")


def main() -> int:
    args = parse_args()
    changed_files = gather_changed_files(args.base, args.staged, args.paths)

    if args.allow_prefix:
        allowed = tuple(args.allow_prefix)
        changed_files = [path for path in changed_files if path.startswith(allowed)]

    if not changed_files:
        print("No Python files changed. MyPy skipped.")
        write_count(args.count_file, 0)
        return 0

    total_errors = 0
    return_code = 0

    for i in range(0, len(changed_files), args.chunk_size):
        chunk = changed_files[i : i + args.chunk_size]
        result = run_mypy_chunk(chunk, args.mypy_args)
        if result.returncode != 0:
            return_code = result.returncode
        if result.errors == -1:
            total_errors = -1
        elif total_errors != -1:
            total_errors += result.errors

    write_count(args.count_file, total_errors if total_errors >= 0 else 9999)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
