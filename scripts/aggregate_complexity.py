from typing import Any

#!/usr/bin/env python3
"""Merge radon JSON outputs and report total complexity blocks."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: aggregate_complexity.py <json> [<json> ...]", file=sys.stderr)
        return 1

    merged: dict[str, list[Any]] = {}
    for path_str in sys.argv[1:]:
        path = Path(path_str)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        merged.update(data)

    Path("complexity.json").write_text(json.dumps(merged), encoding="utf-8")
    total = sum(len(blocks) for blocks in merged.values())
    print(total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
