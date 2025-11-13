#!/usr/bin/env python3
"""Run Ruff on Python files changed relative to a base ref or staged changes.

This script is used by `make lint-staged` to keep new code clean even though the
full repository still carries historical lint debt.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "origin/main"
DEFAULT_PATHS = ("src", "backend", "tests", "scripts")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Ruff on Python files changed vs. a git base reference",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help=("Git base reference for the diff (ignored when --staged is used)"),
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Use staged changes (git diff --cached) instead of a base ref",
    )
    parser.add_argument(
        "--ruff-bin",
        default="ruff",
        help="Executable used to invoke Ruff",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_PATHS,
        help="Path prefixes to include when searching for changed files",
    )
    parser.add_argument(
        "ruff_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments forwarded to Ruff (prefix with --)",
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
    result = run(["git", "rev-parse", "--verify", "--quiet", ref])
    return result.returncode == 0


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


def main() -> int:
    args = parse_args()

    changed_files = gather_changed_files(args.base, args.staged, args.paths)
    if not changed_files:
        print("No Python files changed. Ruff skipped.")
        return 0

    ruff_cmd = [args.ruff_bin, "check", "--force-exclude", *changed_files]
    if args.ruff_args:
        ruff_cmd.extend(args.ruff_args)

    print("Running:", " ".join(ruff_cmd))
    completed = subprocess.run(ruff_cmd, cwd=PROJECT_ROOT)  # noqa: S603
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
