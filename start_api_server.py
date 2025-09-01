#!/usr/bin/env python
"""
Direct API server starter using Hypercorn for Windows compatibility.
Hypercorn provides better Windows support than uvicorn.
"""

import asyncio
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
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    from backend.api.main import app
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

async def main():
    """Run the API server with Hypercorn."""
    try:
        # Configure Hypercorn
        config = Config()
        config.bind = ["0.0.0.0:8000"]
        config.loglevel = "INFO"
        config.accesslog = "-"  # Log to stdout
        config.errorlog = "-"   # Log errors to stderr

        # Start the server
        logger.info("Starting API server with Hypercorn on http://0.0.0.0:8000")
        print("Starting API server with Hypercorn on http://0.0.0.0:8000", flush=True)

        await serve(app, config)

    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server crashed: {e}")
        sys.exit(1)
