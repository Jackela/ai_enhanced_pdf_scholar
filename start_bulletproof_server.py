#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn
    print("[BULLETPROOF] Starting bulletproof API server...")
    uvicorn.run(
        "backend.api.main_bulletproof:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
        log_level="info"
    )
