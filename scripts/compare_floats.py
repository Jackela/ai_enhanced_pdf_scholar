#!/usr/bin/env python3
"""Exit with success if first float >= second float."""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: compare_floats.py <value> <threshold>", file=sys.stderr)
        return 1
    try:
        value = float(sys.argv[1])
        threshold = float(sys.argv[2])
    except ValueError:
        print("Invalid float comparison inputs", file=sys.stderr)
        return 1
    return 0 if value >= threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
