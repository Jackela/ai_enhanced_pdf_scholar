#!/usr/bin/env python
"""Test script to verify hypercorn can serve a basic endpoint."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def main():
    """Test hypercorn with minimal FastAPI app."""
    from fastapi import FastAPI
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    # Create minimal FastAPI app
    app = FastAPI()

    @app.get("/test")
    async def test():
        return {"status": "ok", "message": "Hypercorn is working"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    # Configure Hypercorn
    config = Config()
    config.bind = ["0.0.0.0:8001"]  # Use different port for testing
    config.loglevel = "INFO"
    config.accesslog = "-"

    print("Starting test server on http://0.0.0.0:8001")
    print("Test endpoints:")
    print("  - http://127.0.0.1:8001/test")
    print("  - http://127.0.0.1:8001/health")

    await serve(app, config)

if __name__ == "__main__":
    asyncio.run(main())
