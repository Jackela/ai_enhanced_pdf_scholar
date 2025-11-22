from typing import Any

#!/usr/bin/env python3
"""
Test simple server startup.
"""

import subprocess
import sys
import time
from pathlib import Path

import requests

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main() -> Any:
    """Test simple server."""
    print("Starting simple API server...")

    # Start server process
    server_process = subprocess.Popen(
        [sys.executable, "start_api_server_simple.py"],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(5)

    # Check if process is still alive
    if server_process.poll() is not None:
        # Process died
        output = server_process.stdout.read()
        print(f"Server died with code {server_process.returncode}")
        print(f"Output:\n{output}")
        return 1

    # Test endpoints
    print("\nTesting endpoints...")
    endpoints = [
        ("http://127.0.0.1:8000/", "Root"),
        ("http://127.0.0.1:8000/ping", "Ping"),
        ("http://127.0.0.1:8000/health", "Health"),
        ("http://127.0.0.1:8000/api/system/health", "System Health"),
    ]

    for url, name in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name}: OK")
                print(f"   Response: {response.json()}")
            else:
                print(f"⚠️  {name}: Status {response.status_code}")
        except Exception as e:
            print(f"❌ {name}: {e}")

    # Stop server
    print("\nStopping server...")
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
        print("Server stopped")
    except subprocess.TimeoutExpired:
        server_process.kill()
        print("Server force killed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
