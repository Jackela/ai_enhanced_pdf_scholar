#!/usr/bin/env python3
"""
Quick API Health Test
Tests basic API server startup and health endpoints.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_health_endpoints():
    """Test various health endpoints."""
    endpoints = [
        ("http://127.0.0.1:8000/", "Root endpoint"),
        ("http://127.0.0.1:8000/ping", "Ping endpoint"),
        ("http://127.0.0.1:8000/health", "Basic health"),
        ("http://127.0.0.1:8000/api/system/health", "System health"),
        ("http://127.0.0.1:8000/health/detailed", "Detailed health"),
    ]

    print("\n" + "=" * 60)
    print("TESTING API HEALTH ENDPOINTS")
    print("=" * 60)

    results = []
    async with aiohttp.ClientSession() as session:
        for url, description in endpoints:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    status = response.status
                    if status == 200:
                        data = await response.json()
                        print(f"✅ {description}: OK (status={status})")
                        results.append((description, True, data))
                    else:
                        text = await response.text()
                        print(f"⚠️  {description}: Status {status}")
                        results.append((description, False, f"Status {status}: {text[:100]}"))
            except Exception as e:
                print(f"❌ {description}: {type(e).__name__}: {str(e)[:100]}")
                results.append((description, False, str(e)))

    # Summary
    print("\n" + "-" * 60)
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"Results: {passed}/{total} endpoints responded successfully")

    if passed == total:
        print("✅ All health endpoints are working!")
        return True
    else:
        print("⚠️  Some endpoints failed")
        return False


async def main():
    """Main test function."""
    # First check if server is already running
    print("Checking if API server is already running...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:8000/ping", timeout=aiohttp.ClientTimeout(total=2)) as response:
                if response.status == 200:
                    print("✅ API server is already running")
                    # Test endpoints
                    success = await test_health_endpoints()
                    return 0 if success else 1
    except:
        print("API server is not running")

    # Try to start the server
    print("\nStarting API server...")
    server_process = subprocess.Popen(
        [sys.executable, "start_api_server.py", "--uvicorn"],
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for server to start
    print("Waiting for server to become ready...")
    for i in range(30):
        if server_process.poll() is not None:
            # Process died
            stdout, stderr = server_process.communicate()
            print(f"❌ Server process died with code {server_process.returncode}")
            if stdout:
                print(f"Stdout: {stdout[:500]}")
            if stderr:
                print(f"Stderr: {stderr[:500]}")
            return 1

        # Try to connect
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:8000/ping", timeout=aiohttp.ClientTimeout(total=1)) as response:
                    if response.status == 200:
                        print(f"✅ Server started successfully after {i+1} seconds")
                        break
        except:
            pass

        if i % 5 == 0 and i > 0:
            print(f"  Still waiting... ({i} seconds)")

        await asyncio.sleep(1)
    else:
        print("❌ Server failed to start within 30 seconds")
        server_process.terminate()
        return 1

    # Test endpoints
    success = await test_health_endpoints()

    # Stop server
    print("\nStopping API server...")
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
        print("✅ Server stopped")
    except subprocess.TimeoutExpired:
        server_process.kill()
        print("⚠️  Server force killed")

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
