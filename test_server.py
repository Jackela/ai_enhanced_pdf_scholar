#!/usr/bin/env python
"""Test that the server starts and responds to requests."""

import subprocess
import sys
import time

import requests


def test_server():
    """Start server and test endpoints."""
    # Start the server
    print("Starting server...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app",
         "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(5)

    try:
        # Test root endpoint
        print("\nTesting root endpoint...")
        response = requests.get("http://127.0.0.1:8000/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        # Test health endpoint
        print("\nTesting health endpoint...")
        response = requests.get("http://127.0.0.1:8000/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        # Test API docs
        print("\nTesting API docs endpoint...")
        response = requests.get("http://127.0.0.1:8000/api/docs")
        print(f"Status: {response.status_code}")
        print(f"Docs available: {response.status_code == 200}")

        print("\n✅ Server is running and responding correctly!")
        return True

    except Exception as e:
        print(f"\n❌ Error testing server: {e}")
        return False

    finally:
        # Stop the server
        print("\nStopping server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

if __name__ == "__main__":
    success = test_server()
    sys.exit(0 if success else 1)
