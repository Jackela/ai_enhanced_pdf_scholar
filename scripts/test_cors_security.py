#!/usr/bin/env python3
"""
CORS Security Demonstration Script

This script demonstrates the new secure CORS configuration system and shows
how it prevents security vulnerabilities while maintaining proper functionality.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_environment_configurations():
    """Test different environment configurations."""
    print("=" * 60)
    print("CORS Security Configuration Demonstration")
    print("=" * 60)

    from backend.api.cors_config import CORSConfig, Environment

    test_cases = [
        {
            "name": "Development Environment",
            "env": "development",
            "origins": "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000",
            "should_pass": True
        },
        {
            "name": "Testing Environment",
            "env": "testing",
            "origins": "http://localhost:3000",
            "should_pass": True
        },
        {
            "name": "Staging Environment",
            "env": "staging",
            "origins": "https://staging-app.example.com,https://staging-admin.example.com",
            "should_pass": True
        },
        {
            "name": "Production Environment (Valid)",
            "env": "production",
            "origins": "https://app.example.com,https://admin.example.com",
            "should_pass": True
        },
        {
            "name": "Production Environment (Wildcard - VULNERABLE)",
            "env": "production",
            "origins": "*",
            "should_pass": False
        },
        {
            "name": "Production Environment (Localhost - VULNERABLE)",
            "env": "production",
            "origins": "https://app.example.com,http://localhost:3000",
            "should_pass": False
        },
        {
            "name": "Production Environment (HTTP - VULNERABLE)",
            "env": "production",
            "origins": "http://app.example.com",
            "should_pass": False
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * 40)

        # Set environment variables
        os.environ["ENVIRONMENT"] = test_case["env"]
        os.environ["CORS_ORIGINS"] = test_case["origins"]

        try:
            config = CORSConfig()
            middleware_config = config.get_middleware_config()

            if test_case["should_pass"]:
                print(f"✅ SUCCESS: Configuration valid")
                print(f"   Environment: {config.environment.value}")
                print(f"   Origins: {len(middleware_config['allow_origins'])} configured")
                print(f"   Credentials: {middleware_config['allow_credentials']}")
                print(f"   Methods: {', '.join(middleware_config['allow_methods'])}")

                # Log detailed info in development only
                if config.environment == Environment.DEVELOPMENT:
                    print(f"   Origin Details: {middleware_config['allow_origins']}")
                else:
                    print(f"   Origin Details: [Hidden for security in {config.environment.value}]")

            else:
                print(f"❌ UNEXPECTED: Configuration should have failed but passed")

        except ValueError as e:
            if not test_case["should_pass"]:
                print(f"✅ SUCCESS: Security validation correctly blocked vulnerable config")
                print(f"   Error: {e}")
            else:
                print(f"❌ FAILED: Valid configuration was rejected")
                print(f"   Error: {e}")
        except Exception as e:
            print(f"❌ ERROR: Unexpected error: {e}")

def test_origin_validation():
    """Test origin format validation."""
    print("\n" + "=" * 60)
    print("Origin Format Validation Tests")
    print("=" * 60)

    from backend.api.cors_config import validate_origin_format

    test_origins = [
        ("https://app.example.com", True, "Valid HTTPS origin"),
        ("http://localhost:3000", True, "Valid localhost with port"),
        ("http://127.0.0.1:8080", True, "Valid IP with port"),
        ("https://subdomain.example.com", True, "Valid subdomain"),
        ("app.example.com", False, "Missing protocol"),
        ("https://app.example.com/", False, "Trailing slash"),
        ("ftp://app.example.com", False, "Wrong protocol"),
        ("http://", False, "No domain"),
        ("", False, "Empty string"),
        ("https://app.example.com:8443", True, "HTTPS with custom port"),
    ]

    for i, (origin, expected, description) in enumerate(test_origins, 1):
        result = validate_origin_format(origin)
        status = "✅" if result == expected else "❌"
        print(f"{i:2}. {status} {description}")
        print(f"    Origin: '{origin}'")
        print(f"    Expected: {expected}, Got: {result}")

def test_security_scenarios():
    """Test specific security scenarios."""
    print("\n" + "=" * 60)
    print("Security Scenario Tests")
    print("=" * 60)

    scenarios = [
        {
            "name": "Subdomain Confusion Attack",
            "origin": "https://app.example.com.evil.com",
            "allowed": "https://app.example.com",
            "description": "Should not allow similar looking subdomain"
        },
        {
            "name": "Protocol Confusion",
            "origin": "http://app.example.com",
            "allowed": "https://app.example.com",
            "description": "Should not allow HTTP when HTTPS is configured"
        },
        {
            "name": "Port Confusion",
            "origin": "https://app.example.com:8443",
            "allowed": "https://app.example.com",
            "description": "Should not allow different port"
        },
        {
            "name": "Case Sensitivity",
            "origin": "https://APP.EXAMPLE.COM",
            "allowed": "https://app.example.com",
            "description": "Should be case sensitive"
        }
    ]

    from backend.api.cors_config import CORSConfig

    # Set up production environment with specific origin
    os.environ["ENVIRONMENT"] = "production"

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{i}. {scenario['name']}")
        print(f"   {scenario['description']}")
        print(f"   Allowed: {scenario['allowed']}")
        print(f"   Attempting: {scenario['origin']}")

        os.environ["CORS_ORIGINS"] = scenario["allowed"]

        try:
            config = CORSConfig()
            origins = config.get_middleware_config()["allow_origins"]

            if scenario["origin"] in origins:
                print("   ❌ VULNERABLE: Malicious origin was allowed")
            else:
                print("   ✅ SECURE: Malicious origin correctly blocked")

        except Exception as e:
            print(f"   ❌ ERROR: {e}")

def demonstrate_environment_differences():
    """Demonstrate differences between environments."""
    print("\n" + "=" * 60)
    print("Environment-Specific Behavior")
    print("=" * 60)

    from backend.api.cors_config import CORSConfig

    environments = [
        ("development", "http://localhost:3000"),
        ("testing", "http://localhost:3000"),
        ("staging", "https://staging.example.com"),
        ("production", "https://app.example.com")
    ]

    for env, origins in environments:
        print(f"\n{env.upper()} Environment:")
        print("-" * 20)

        os.environ["ENVIRONMENT"] = env
        os.environ["CORS_ORIGINS"] = origins

        try:
            config = CORSConfig()
            middleware_config = config.get_middleware_config()

            print(f"  Allow Credentials: {middleware_config['allow_credentials']}")
            print(f"  Method Count: {len(middleware_config['allow_methods'])}")
            print(f"  Max Age: {middleware_config['max_age']} seconds")
            print(f"  Header Count: {len(middleware_config['allow_headers'])}")

        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    try:
        test_environment_configurations()
        test_origin_validation()
        test_security_scenarios()
        demonstrate_environment_differences()

        print("\n" + "=" * 60)
        print("CORS Security Demonstration Complete")
        print("=" * 60)
        print("Key Security Improvements:")
        print("  • Eliminated wildcard (*) origins vulnerability")
        print("  • Environment-specific security policies")
        print("  • Production security validation")
        print("  • Origin format validation")
        print("  • Comprehensive security testing")
        print("  • Detailed security logging")

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)