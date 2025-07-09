#!/usr/bin/env python3
"""
Web UI Entry Point for AI Enhanced PDF Scholar

This script starts the web-based interface, providing the same functionality
as the desktop PyQt6 application but accessible through any web browser.

Usage:
    python web_main.py [--host HOST] [--port PORT] [--debug]

Examples:
    python web_main.py                    # Start on localhost:8000
    python web_main.py --port 3000        # Start on localhost:3000
    python web_main.py --host 0.0.0.0     # Start on all interfaces
"""

import sys
import argparse
import logging
import asyncio
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.controllers.application_controller import ApplicationController
from src.web.api_server import APIServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_arguments():
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
    
    return parser.parse_args()


async def main():
    """Main entry point for web application."""
    args = parse_arguments()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('src').setLevel(logging.DEBUG)
    
    logger.info("Starting AI Enhanced PDF Scholar - Web Interface")
    logger.info(f"Configuration: host={args.host}, port={args.port}, debug={args.debug}")
    
    try:
        # Initialize application controller
        logger.info("Initializing application controller...")
        
        # Create a minimal settings mock for web environment
        class WebSettings:
            def __init__(self):
                self._values = {}
            def value(self, key, default=None, type=None):
                return self._values.get(key, default)
            def setValue(self, key, value):
                self._values[key] = value
            def contains(self, key):
                return key in self._values
            def organizationName(self):
                return "AI Enhanced PDF Scholar"
            def applicationName(self):
                return "Web Settings"
            def allKeys(self):
                return list(self._values.keys())
        
        web_settings = WebSettings()
        app_controller = ApplicationController(web_settings)
        
        # Initialize application (this sets up services, state management, etc.)
        success = app_controller.initialize_application()
        if not success:
            logger.error("Failed to initialize application controller")
            return 1
        
        logger.info("Application controller initialized successfully")
        
        # Create and start API server
        logger.info(f"Starting web server on {args.host}:{args.port}")
        api_server = APIServer(app_controller, host=args.host, port=args.port)
        
        print(f"\n🚀 AI Enhanced PDF Scholar Web Interface")
        print(f"📄 Server starting on: http://{args.host}:{args.port}")
        print(f"🌐 Open your browser and navigate to the URL above")
        print(f"📋 Press Ctrl+C to stop the server\n")
        
        # Start the server (this will block)
        await api_server.start_server()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Error starting web application: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def run_web_app():
    """Synchronous wrapper for async main function."""
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run_web_app()) 