#!/usr/bin/env python3
"""
AI Enhanced PDF Scholar - Test Runner Utility

Provides different test execution modes for various development scenarios.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd: list[str], description: str) -> int:
    """Run a command and return its exit code."""
    print(f"\n🚀 {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        return result.returncode
    except KeyboardInterrupt:
        print("\n❌ Test execution interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Test runner for AI Enhanced PDF Scholar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick smoke tests
  python scripts/test_runner.py --quick
  
  # Full test suite without coverage
  python scripts/test_runner.py --full
  
  # Unit tests only
  python scripts/test_runner.py --unit
  
  # Integration tests only
  python scripts/test_runner.py --integration
  
  # With coverage (slower)
  python scripts/test_runner.py --coverage
  
  # Specific test file
  python scripts/test_runner.py --file tests/test_database_connection.py
        """
    )
    
    parser.add_argument("--quick", action="store_true", 
                       help="Run quick smoke tests only")
    parser.add_argument("--full", action="store_true", 
                       help="Run full test suite without coverage")
    parser.add_argument("--unit", action="store_true", 
                       help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", 
                       help="Run integration tests only")
    parser.add_argument("--coverage", action="store_true", 
                       help="Run tests with coverage analysis")
    parser.add_argument("--file", type=str, 
                       help="Run specific test file")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug output")
    parser.add_argument("--sequential", action="store_true", 
                       help="Run tests sequentially (no parallelization)")
    parser.add_argument("--maxfail", type=int, default=5,
                       help="Stop after N failures (default: 5)")
    
    args = parser.parse_args()
    
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]
    
    if args.debug:
        base_cmd.extend(["--tb=long", "-v", "--log-cli-level=DEBUG"])
    else:
        base_cmd.extend(["--tb=short", "-v"])
    
    # Add maxfail option
    base_cmd.extend(["--maxfail", str(args.maxfail)])
    
    # Configure parallelization
    if args.sequential:
        # No parallel execution
        pass
    else:
        base_cmd.extend(["-n", "auto", "--dist=loadfile"])
    
    # Disable coverage by default unless explicitly requested
    if args.coverage:
        base_cmd.extend([
            "--cov=src",
            "--cov-report=html:coverage_html",
            "--cov-report=term-missing:skip-covered",
            "--cov-report=xml:coverage.xml",
            "--cov-fail-under=20"
        ])
    else:
        base_cmd.append("--no-cov")
    
    exit_code = 0
    
    if args.quick:
        # Quick smoke tests
        cmd = base_cmd + [
            "tests/unit/test_smoke.py",
            "tests/test_database_connection.py",
            "-k", "not slow"
        ]
        exit_code = run_command(cmd, "Running quick smoke tests")
    
    elif args.unit:
        # Unit tests only
        cmd = base_cmd + ["tests/unit/"]
        exit_code = run_command(cmd, "Running unit tests")
    
    elif args.integration:
        # Integration tests only
        cmd = base_cmd + ["tests/integration/"]
        exit_code = run_command(cmd, "Running integration tests")
    
    elif args.file:
        # Specific test file
        cmd = base_cmd + [args.file]
        exit_code = run_command(cmd, f"Running tests from {args.file}")
    
    elif args.full:
        # Full test suite
        cmd = base_cmd + [
            "tests/",
            "--ignore=tests/services/test_enhanced_rag_service.py",
            "--ignore=tests/services/test_document_library_service.py", 
            "--ignore=tests/services/test_rag_cache_service.py",
            "--ignore=tests/security/test_penetration_testing.py"
        ]
        exit_code = run_command(cmd, "Running full test suite")
    
    else:
        # Default: run basic tests
        cmd = base_cmd + [
            "tests/test_database_connection.py",
            "tests/unit/",
            "tests/repositories/",
            "--maxfail=10"
        ]
        exit_code = run_command(cmd, "Running basic test suite")
    
    # Summary
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✅ All tests passed successfully!")
    else:
        print(f"❌ Tests failed with exit code {exit_code}")
    print("=" * 60)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())