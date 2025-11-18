from typing import Any

#!/usr/bin/env python3
"""
Simple API server starter - minimal initialization for testing.
"""

import logging
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

def main() -> None:
    """Start the API server with minimal configuration."""
    try:
        import uvicorn

        from backend.api.main_simple import app

        logger.info("Starting simplified API server on http://0.0.0.0:8000")
        print("Starting simplified API server on http://0.0.0.0:8000", flush=True)

        # Run with minimal configuration
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=False,  # Disable access log for cleaner output
            reload=False,
            loop="asyncio",
            use_colors=False
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server crashed: {e}")
        sys.exit(1)
