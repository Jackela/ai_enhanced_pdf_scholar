from typing import Any

#!/usr/bin/env python
"""
Test script to verify the health endpoint is working correctly.
This tests the fix for the 500 error caused by conflicting SystemHealthResponse models.
"""

import json
import subprocess
import sys
import time

import requests


def test_health_endpoint() -> Any:
    """Test the health endpoint after fixing the model import issue."""

    print("Starting API server...")
    # Start the server
    proc = subprocess.Popen(
        [sys.executable, 'start_api_server.py', '--uvicorn'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(10)

    try:
        print("Testing /api/system/health endpoint...")
        response = requests.get('http://localhost:8000/api/system/health', timeout=10)

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ SUCCESS! The health endpoint is working correctly!")
            data = response.json()
            print("\nResponse Data:")
            print(json.dumps(data, indent=2))

            # Verify expected fields are present
            expected_fields = [
                'status',
                'database_connected',
                'rag_service_available',
                'api_key_configured',
                'storage_health',
                'uptime_seconds'
            ]

            missing_fields = [f for f in expected_fields if f not in data]
            if missing_fields:
                print(f"\n⚠️ Warning: Missing fields: {missing_fields}")
            else:
                print("\n✅ All expected fields are present!")

            return True
        else:
            print(f"❌ FAILED! Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ FAILED! Could not connect to server.")
        print("The server may have failed to start. Check the logs above.")
        return False
    except Exception as e:
        print(f"❌ FAILED! Error: {e}")
        return False
    finally:
        print("\nStopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print("Server stopped.")


if __name__ == "__main__":
    print("=" * 60)
    print("Health Endpoint Test")
    print("=" * 60)
    print("\nThis test verifies the fix for the 500 error on /api/system/health")
    print("The issue was caused by conflicting SystemHealthResponse models.")
    print("The fix ensures the correct model is imported from backend.api.models")
    print("-" * 60)

    success = test_health_endpoint()

    print("\n" + "=" * 60)
    if success:
        print("TEST PASSED ✅")
        print("The health endpoint is now working correctly!")
    else:
        print("TEST FAILED ❌")
        print("Please check the error messages above.")
    print("=" * 60)

    sys.exit(0 if success else 1)
