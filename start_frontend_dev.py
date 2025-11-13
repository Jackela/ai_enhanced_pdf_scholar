#!/usr/bin/env python3
"""Helper script to run the Vite dev server with consistent logging."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
LOG_PATH = PROJECT_ROOT / "frontend_server.log"


def main() -> int:
    if not FRONTEND_DIR.exists():
        print(f"[FRONTEND] Missing frontend directory: {FRONTEND_DIR}", file=sys.stderr)
        return 1

    log_handle = LOG_PATH.open("w", encoding="utf-8")

    try:
        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(FRONTEND_DIR),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError:
        print("[FRONTEND] npm is not installed or not on PATH", file=sys.stderr)
        log_handle.close()
        return 1

    print(
        f"[FRONTEND] Dev server started (PID={process.pid}). Logs -> {LOG_PATH}",
        flush=True,
    )

    try:
        process.wait()
    finally:
        log_handle.close()

    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
