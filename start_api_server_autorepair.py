#!/usr/bin/env python3
"""
AUTONOMOUS REPAIR: Simplified API server startup script.
Forces uvicorn on Windows and includes robust error handling.
"""

import sys
import os
import time
import uvicorn
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def start_server():
    """Start the API server with maximum stability."""
    print("[AUTO-REPAIR] Starting API server with autonomous repair configuration...")
    
    # Force uvicorn on Windows
    if sys.platform == "win32":
        print("[AUTO-REPAIR] Windows detected - using uvicorn for stability")
        
    # Configure uvicorn
    config = uvicorn.Config(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload for stability
        workers=1,     # Single worker for simplicity
        log_level="info",
        access_log=True
    )
    
    server = uvicorn.Server(config)
    
    try:
        print(f"[AUTO-REPAIR] Server starting on http://0.0.0.0:8000")
        server.run()
    except Exception as e:
        print(f"[AUTO-REPAIR] Server failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server()
