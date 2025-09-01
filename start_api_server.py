#!/usr/bin/env python
"""
Direct API server starter for Windows compatibility.
This bypasses the module execution issues with python -m uvicorn.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn

from backend.api.main import app

if __name__ == "__main__":
    # Start the server directly
    print("Starting API server on http://0.0.0.0:8000")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )
