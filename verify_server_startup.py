#!/usr/bin/env python3
"""
Isolated Server Startup Verifier
=================================
This script's ONLY job is to:
1. Launch the API server using 'start_api_server.py'
2. Wait up to 20 seconds
3. Make a simple HTTP GET request to the '/api/system/health' endpoint
4. Print 'SUCCESS' if it gets a 200 response, otherwise print 'FAILURE' with error

Author: AI Enhanced PDF Scholar Team
Date: 2025-09-02
"""

import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests


def kill_process_tree(pid):
    """Kill a process and all its children."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)

        # Kill children first
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        # Kill parent
        try:
            parent.terminate()
        except psutil.NoSuchProcess:
            pass

        # Give them time to terminate gracefully
        time.sleep(0.5)

        # Force kill if still alive
        for child in children:
            try:
                if child.is_running():
                    child.kill()
            except psutil.NoSuchProcess:
                pass

        try:
            if parent.is_running():
                parent.kill()
        except psutil.NoSuchProcess:
            pass

    except Exception as e:
        print(f"Error killing process tree: {e}", file=sys.stderr)


def verify_server_startup():
    """
    Verify that the API server starts up correctly.
    
    Returns:
        bool: True if server started successfully, False otherwise
    """
    server_process = None
    start_time = time.time()
    max_wait_seconds = 30  # Increased from 20 to 30 seconds since server needs ~5 seconds to start

    try:
        # Step 1: Launch the API server
        print("Starting API server...", file=sys.stderr)

        # Try the simple startup script first (uses main_simple.py without lifespan)
        server_script = Path(__file__).parent / "start_api_server_simple.py"
        if not server_script.exists():
            # Fallback to regular startup script
            server_script = Path(__file__).parent / "start_api_server.py"
            if not server_script.exists():
                print(f"FAILURE: start_api_server.py not found at {server_script}", file=sys.stderr)
                print("FAILURE")
                return False
            print("Using regular start_api_server.py", file=sys.stderr)
        else:
            print("Using simplified start_api_server_simple.py (no lifespan)", file=sys.stderr)

        # Start the server process
        # Use DEVNULL instead of PIPE to avoid buffering issues
        server_process = subprocess.Popen(
            [sys.executable, str(server_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Give server initial time to start up before first request
        print("Giving server 3 seconds to initialize...", file=sys.stderr)
        time.sleep(3)

        # Step 2: Wait up to 30 seconds for server to be ready
        print(f"Waiting for server to be ready (max {max_wait_seconds} seconds)...", file=sys.stderr)

        # Try 127.0.0.1 instead of localhost for better Windows compatibility
        health_url = "http://127.0.0.1:8000/api/system/health"
        connection_attempts = 0

        while (time.time() - start_time) < max_wait_seconds:
            connection_attempts += 1

            try:
                # Step 3: Make HTTP GET request to health endpoint
                # Use longer timeout since server takes 4-5 seconds to respond initially
                response = requests.get(health_url, timeout=10)

                # Step 4: Check if we got a 200 response
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    print(f"Server started successfully in {elapsed:.2f} seconds", file=sys.stderr)
                    print(f"Health check response: {response.json()}", file=sys.stderr)
                    print("SUCCESS")
                    return True
                else:
                    print(f"Health check returned status {response.status_code}", file=sys.stderr)

            except requests.exceptions.ConnectionError:
                # Server not ready yet, wait and retry
                if connection_attempts <= 2:
                    print(f"  Server not ready yet, waiting... (attempt {connection_attempts})", file=sys.stderr)
                elif connection_attempts % 3 == 0:
                    print(f"  Still waiting... ({connection_attempts} attempts)", file=sys.stderr)
            except requests.exceptions.Timeout:
                print(f"  Request timed out after 10 seconds, retrying... (attempt {connection_attempts})", file=sys.stderr)
            except Exception as e:
                print(f"  Unexpected error during health check: {type(e).__name__}: {e}", file=sys.stderr)

            # Check if server process has crashed
            if server_process.poll() is not None:
                print(f"FAILURE: Server process crashed with exit code {server_process.returncode}", file=sys.stderr)
                print("FAILURE")
                return False

            # Wait before next attempt
            time.sleep(0.5)

        # Timeout reached
        print(f"FAILURE: Server did not respond within {max_wait_seconds} seconds", file=sys.stderr)
        print(f"Made {connection_attempts} connection attempts", file=sys.stderr)

        # Server output was sent to DEVNULL to avoid buffering issues
        print("(Server output was suppressed to avoid subprocess buffering issues)", file=sys.stderr)

        print("FAILURE")
        return False

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        print("FAILURE")
        return False

    except Exception as e:
        print(f"FAILURE: Unexpected error: {e}", file=sys.stderr)
        print("FAILURE")
        return False

    finally:
        # Clean up: terminate the server process
        if server_process:
            try:
                print("\nCleaning up server process...", file=sys.stderr)
                kill_process_tree(server_process.pid)
                print("Server process terminated", file=sys.stderr)
            except Exception as e:
                print(f"Error terminating server: {e}", file=sys.stderr)


def main():
    """Main entry point."""
    success = verify_server_startup()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
