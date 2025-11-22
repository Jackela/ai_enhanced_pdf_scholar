from typing import Any

#!/usr/bin/env python3
"""
Web UI Entry Point for AI Enhanced PDF Scholar

This script starts the FastAPI web application for AI Enhanced PDF Scholar.

Usage:
    python web_main.py [--host HOST] [--port PORT] [--debug]

Examples:
    python web_main.py                    # Start on localhost:8000
    python web_main.py --port 3000        # Start on localhost:3000
    python web_main.py --host 0.0.0.0     # Start on all interfaces
"""

import argparse
import logging
import sys

import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_arguments() -> Any:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AI Enhanced PDF Scholar - Web Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     Start on localhost:8000
  %(prog)s --port 3000         Start on localhost:3000
  %(prog)s --host 0.0.0.0      Start on all interfaces (accessible from network)
  %(prog)s --debug             Enable debug logging
        """
    )

    parser.add_argument(
        '--host',
        default='localhost',
        help='Host address to bind to (default: localhost)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port number to bind to (default: 8000)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    parser.add_argument(
        '--reload',
        action='store_true',
        help='Enable auto-reload for development'
    )

    return parser.parse_args()


def main() -> Any:
    """Main entry point for web application."""
    args = parse_arguments()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        log_level = "debug"
    else:
        log_level = "info"

    logger.info("Starting AI Enhanced PDF Scholar - Web Interface")
    logger.info(f"Configuration: host={args.host}, port={args.port}, debug={args.debug}")

    print("\n🚀 AI Enhanced PDF Scholar Web Interface")
    print(f"📄 Server starting on: http://{args.host}:{args.port}")
    print("🌐 Open your browser and navigate to the URL above")
    print("📋 Press Ctrl+C to stop the server\n")

    try:
        # Start uvicorn server with the FastAPI app from backend.api.main
        uvicorn.run(
            "backend.api.main:app",
            host=args.host,
            port=args.port,
            log_level=log_level,
            reload=args.reload,
            reload_dirs=["src", "backend"] if args.reload else None
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error starting web application: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
