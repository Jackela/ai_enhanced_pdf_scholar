#!/usr/bin/env python
"""
Direct API server starter for Windows compatibility.
This bypasses the module execution issues with python -m uvicorn.
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import uvicorn

    from backend.api.main import app
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

if __name__ == "__main__":
    try:
        # Start the server directly
        logger.info("Starting API server on http://0.0.0.0:8000")
        print("Starting API server on http://0.0.0.0:8000", flush=True)

        # Use simple uvicorn.run for better Windows compatibility
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True,
            reload=False  # Never use reload in production/tests
        )

    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
