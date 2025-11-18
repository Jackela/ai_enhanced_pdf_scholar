from typing import Any

#!/usr/bin/env python
"""
Direct test of the health endpoint using FastAPI TestClient.
This bypasses the server startup and tests the endpoint directly.
"""

import sys

sys.path.insert(0, '.')

from fastapi.testclient import TestClient

from backend.api.main import app


def test_health_endpoint_direct() -> Any:
    """Test the health endpoint directly without starting the server."""

    print("Creating test client...")
    client = TestClient(app)

    print("Testing /api/system/health endpoint...")
    response = client.get('/api/system/health')

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        print("✅ SUCCESS! The health endpoint is working correctly!")
        data = response.json()

        import json
        print("\nResponse Data:")
        print(json.dumps(data, indent=2))

        # Verify expected fields
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
            return False
        else:
            print("\n✅ All expected fields are present!")
            return True
    else:
        print(f"❌ FAILED! Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Direct Health Endpoint Test (No Server Required)")
    print("=" * 60)

    try:
        success = test_health_endpoint_direct()

        print("\n" + "=" * 60)
        if success:
            print("TEST PASSED ✅")
            print("The health endpoint is working correctly!")
            print("\nThe fix successfully resolved the issue:")
            print("- Removed conflicting SystemHealthResponse import from multi_document_models")
            print("- Ensured correct model is used from backend.api.models")
            print("- Fixed the 500 error caused by missing 'components' field")
        else:
            print("TEST FAILED ❌")
            print("The endpoint returned a response but is missing expected fields.")
        print("=" * 60)

        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
