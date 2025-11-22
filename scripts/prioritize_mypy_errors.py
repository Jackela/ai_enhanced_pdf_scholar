#!/usr/bin/env python3
"""
Analyze and categorize MyPy errors for prioritized fixing.

This script reads MyPy output and categorizes errors by:
- Fixability (auto, semi-auto, manual-simple, manual-complex)
- Risk level (high: backend/src, medium: tests, low: scripts)
- Error type frequency

Output:
- auto_fixable.txt: no-untyped-def errors (use fix_untyped_defs.py)
- semi_auto.txt: type-arg, assignment errors (batch fixable with patterns)
- manual_simple.txt: attr-defined (interface/protocol additions)
- manual_complex.txt: union-attr, unreachable, arg-type (require analysis)
- error_summary.json: Statistics and breakdown
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MyPyError:
    """Represents a single MyPy error."""

    file_path: str
    line_number: int
    error_type: str
    message: str
    severity: str = "normal"  # normal, note, error

    @property
    def risk_level(self) -> str:
        """Determine risk level based on file path."""
        if self.file_path.startswith(("backend/", "src/")):
            return "high"
        elif self.file_path.startswith("tests/"):
            return "medium"
        else:
            return "low"

    @property
    def fixability(self) -> str:
        """Categorize error by fixability."""
        # Auto-fixable errors
        if self.error_type in {"no-untyped-def", "no-untyped-call"}:
            return "auto"

        # Semi-auto fixable (pattern-based)
        if self.error_type in {
            "type-arg",
            "assignment",
            "return-value",
            "var-annotated",
        }:
            return "semi_auto"

        # Manual but simple (add to interfaces)
        if self.error_type in {
            "attr-defined",
            "name-defined",
            "misc",
        }:
            return "manual_simple"

        # Complex manual fixes
        return "manual_complex"


@dataclass
class ErrorAnalysis:
    """Analysis results for MyPy errors."""

    total_errors: int = 0
    total_files: int = 0
    errors_by_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_file: dict[str, list[MyPyError]] = field(
        default_factory=lambda: defaultdict(list)
    )
    errors_by_category: dict[str, list[MyPyError]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add_error(self, error: MyPyError) -> None:
        """Add an error to the analysis."""
        self.total_errors += 1
        self.errors_by_type[error.error_type] += 1
        self.errors_by_file[error.file_path].append(error)
        self.errors_by_category[error.fixability].append(error)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_errors": self.total_errors,
            "total_files": len(self.errors_by_file),
            "by_type": dict(
                sorted(self.errors_by_type.items(), key=lambda x: x[1], reverse=True)
            ),
            "by_category": {
                cat: len(errors) for cat, errors in self.errors_by_category.items()
            },
            "top_10_files": self._get_top_files(10),
        }

    def _get_top_files(self, n: int) -> list[dict[str, Any]]:
        """Get top N files with most errors."""
        file_counts = [
            {
                "file": file_path,
                "errors": len(errors),
                "risk": errors[0].risk_level if errors else "unknown",
            }
            for file_path, errors in self.errors_by_file.items()
        ]
        return sorted(file_counts, key=lambda x: x["errors"], reverse=True)[:n]


def parse_mypy_output(mypy_output_path: Path) -> ErrorAnalysis:
    """
    Parse MyPy output file and categorize errors.

    Args:
        mypy_output_path: Path to MyPy output file

    Returns:
        ErrorAnalysis object with categorized errors
    """
    analysis = ErrorAnalysis()

    # Regex pattern for MyPy errors
    # Format: file.py:123: error: Message [error-type]
    error_pattern = re.compile(
        r"^(?P<file>.*?):(?P<line>\d+):\s*(?P<severity>error|note|warning):\s*"
        r"(?P<message>.*?)\s*\[(?P<type>[\w-]+)\]"
    )

    content = mypy_output_path.read_text(encoding="utf-8")

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        match = error_pattern.match(line)
        if match:
            error = MyPyError(
                file_path=match.group("file"),
                line_number=int(match.group("line")),
                error_type=match.group("type"),
                message=match.group("message"),
                severity=match.group("severity"),
            )
            analysis.add_error(error)

    return analysis


def write_categorized_files(
    analysis: ErrorAnalysis, output_dir: Path, verbose: bool = False
) -> None:
    """
    Write categorized file lists for batch processing.

    Args:
        analysis: Error analysis results
        output_dir: Directory to write output files
        verbose: Enable verbose output
    """
    output_dir.mkdir(exist_ok=True)

    categories = {
        "auto": "auto_fixable.txt",
        "semi_auto": "semi_auto.txt",
        "manual_simple": "manual_simple.txt",
        "manual_complex": "manual_complex.txt",
    }

    for category, filename in categories.items():
        errors = analysis.errors_by_category.get(category, [])

        # Get unique files, sorted by error count
        file_error_counts: Any = defaultdict(int)
        for error in errors:
            file_error_counts[error.file_path] += 1

        sorted_files = sorted(
            file_error_counts.items(),
            key=lambda x: (
                # Sort by risk (high first), then by error count
                {"high": 0, "medium": 1, "low": 2}.get(
                    next(e.risk_level for e in errors if e.file_path == x[0]), 2
                ),
                -x[1],  # Descending error count
            ),
        )

        output_file = output_dir / filename
        with output_file.open("w", encoding="utf-8") as f:
            f.write(f"# {category.upper().replace('_', ' ')} FILES\n")
            f.write(f"# Total files: {len(sorted_files)}\n")
            f.write(f"# Total errors: {len(errors)}\n")
            f.write("# Format: file_path (error_count) [risk_level]\n\n")

            for file_path, count in sorted_files:
                risk = next(e.risk_level for e in errors if e.file_path == file_path)
                f.write(f"{file_path}  # {count} errors [{risk}]\n")

        if verbose:
            print(f"✓ {filename}: {len(sorted_files)} files, {len(errors)} errors")

    # Write summary JSON
    summary_file = output_dir / "error_summary.json"
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(analysis.get_summary(), f, indent=2)

    if verbose:
        print("✓ error_summary.json: Summary statistics")


def print_analysis(analysis: ErrorAnalysis) -> None:
    """Print analysis summary to console."""
    summary = analysis.get_summary()

    print("\n" + "=" * 70)
    print("MyPy Error Analysis Summary")
    print("=" * 70)
    print(f"Total Errors: {summary['total_errors']}")
    print(f"Total Files:  {summary['total_files']}")
    print()

    print("Errors by Category (Fixability):")
    print("-" * 70)
    for category, count in summary["by_category"].items():
        percentage = (count / summary["total_errors"]) * 100
        print(f"  {category:20s}: {count:5d} ({percentage:5.1f}%)")
    print()

    print("Top 10 Error Types:")
    print("-" * 70)
    for error_type, count in list(summary["by_type"].items())[:10]:
        percentage = (count / summary["total_errors"]) * 100
        print(f"  {error_type:30s}: {count:5d} ({percentage:5.1f}%)")
    print()

    print("Top 10 Files with Most Errors:")
    print("-" * 70)
    for file_info in summary["top_10_files"]:
        print(
            f"  [{file_info['risk']:6s}] "
            f"{file_info['file']:50s} {file_info['errors']:4d} errors"
        )
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze and categorize MyPy errors for prioritized fixing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "mypy_output",
        type=Path,
        help="Path to MyPy output file (e.g., mypy_baseline_day1.txt)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("mypy_analysis"),
        help="Output directory for categorized files (default: mypy_analysis/)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args(argv)

    if not args.mypy_output.exists():
        print(f"Error: MyPy output file not found: {args.mypy_output}", file=sys.stderr)
        return 1

    try:
        # Parse and analyze
        print(f"Analyzing {args.mypy_output}...")
        analysis = parse_mypy_output(args.mypy_output)

        # Write categorized files
        write_categorized_files(analysis, args.output_dir, verbose=args.verbose)

        # Print summary
        print_analysis(analysis)

        print(f"\n✓ Analysis complete. Output written to {args.output_dir}/")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
