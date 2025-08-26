#!/usr/bin/env python
"""
Quick test script for authentication API endpoints.
"""

import time

import requests

BASE_URL = "http://localhost:8000/api"

def test_authentication_flow():
    """Test the complete authentication flow."""

    print("=" * 60)
    print("Testing Authentication API Endpoints")
    print("=" * 60)

    # Test 1: Register a new user
    print("\n1. Testing user registration...")
    register_data = {
        "username": f"testuser_{int(time.time())}",
        "email": f"test_{int(time.time())}@example.com",
        "password": "SecureP@ssw0rd123",
        "full_name": "Test User"
    }

    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        print(f"   Status: {response.status_code}")
        if response.status_code == 201:
            user_data = response.json()
            print(f"   ✓ User registered: {user_data.get('username')}")
        else:
            print(f"   ✗ Registration failed: {response.text}")
            return
    except Exception as e:
        print(f"   ✗ Connection error: {e}")
        print("   Make sure the server is running: python -m uvicorn backend.api.main:app")
        return

    # Test 2: Login with the new user
    print("\n2. Testing user login...")
    login_data = {
        "username": register_data["username"],
        "password": register_data["password"],
        "remember_me": False
    }

    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        print("   ✓ Login successful")
        print(f"   Access token (first 50 chars): {access_token[:50]}...")
        print(f"   Token type: {token_data.get('token_type')}")
        print(f"   Expires in: {token_data.get('expires_in')} seconds")
    else:
        print(f"   ✗ Login failed: {response.text}")
        return

    # Test 3: Access protected endpoint
    print("\n3. Testing protected endpoint (GET /auth/me)...")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        user_profile = response.json()
        print("   ✓ User profile retrieved:")
        print(f"     - Username: {user_profile.get('username')}")
        print(f"     - Email: {user_profile.get('email')}")
        print(f"     - Role: {user_profile.get('role')}")
    else:
        print(f"   ✗ Failed to get profile: {response.text}")

    # Test 4: Refresh token
    print("\n4. Testing token refresh...")
    refresh_data = {"refresh_token": refresh_token}
    response = requests.post(f"{BASE_URL}/auth/refresh", json=refresh_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        new_token_data = response.json()
        new_access_token = new_token_data.get("access_token")
        print("   ✓ Token refreshed successfully")
        print(f"   New access token (first 50 chars): {new_access_token[:50]}...")
    else:
        print(f"   ✗ Token refresh failed: {response.text}")

    # Test 5: Logout
    print("\n5. Testing logout...")
    logout_data = {"refresh_token": refresh_token}
    response = requests.post(f"{BASE_URL}/auth/logout", json=logout_data, headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print("   ✓ Logged out successfully")
    else:
        print(f"   ✗ Logout failed: {response.text}")

    # Test 6: Try to use revoked refresh token
    print("\n6. Testing revoked token (should fail)...")
    response = requests.post(f"{BASE_URL}/auth/refresh", json=refresh_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print("   ✓ Revoked token correctly rejected")
    else:
        print("   ✗ Security issue: revoked token still works!")

    print("\n" + "=" * 60)
    print("Authentication API Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_authentication_flow()
