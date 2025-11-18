from typing import Any

#!/usr/bin/env python3
"""
Actual Dependency Verification Script
Tests the dependencies that the application actually uses based on its configuration.
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def load_configuration() -> Any:
    """Load application configuration."""
    try:
        # Load environment variables from .env file
        env_file = project_root / '.env'
        if env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                # Manual .env loading if python-dotenv not available
                with open(env_file, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
        return True
    except Exception as e:
        print(f"FAILURE: Configuration loading FAILED - {e}")
        return False


def test_sqlite_connection() -> Any:
    """Test SQLite database connection (the default database)."""
    try:
        # Get the database URL or use default
        db_url = os.getenv("DATABASE_URL", "sqlite:///./pdf_scholar.db")

        if not db_url.startswith("sqlite://"):
            # If PostgreSQL is configured, test that instead
            return test_configured_database()

        # Parse SQLite path
        if db_url.startswith("sqlite:///:memory:"):
            db_path = ":memory:"
        else:
            db_path = db_url.replace("sqlite:///", "")

        # Ensure directory exists for file-based SQLite
        if db_path != ":memory:":
            db_file = Path(db_path)
            db_file.parent.mkdir(parents=True, exist_ok=True)

        # Test SQLite connection
        connection = sqlite3.connect(db_path, timeout=10)
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if result and result[0] == 1:
            print("SUCCESS: Database connection OK")
            return True
        else:
            print("FAILURE: Database connection FAILED - Query returned unexpected result")
            return False

    except Exception as e:
        print(f"FAILURE: Database connection FAILED - {e}")
        return False


def test_configured_database() -> Any:
    """Test PostgreSQL if configured."""
    try:
        import psycopg2
        from psycopg2 import OperationalError as PGOperationalError

        # Get PostgreSQL connection parameters from environment
        pg_host = os.getenv('POSTGRES_HOST', 'localhost')
        pg_port = os.getenv('POSTGRES_PORT', '5432')
        pg_database = os.getenv('POSTGRES_DATABASE', 'ai_pdf_scholar')
        pg_user = os.getenv('POSTGRES_USER', 'postgres')
        pg_password = os.getenv('POSTGRES_PASSWORD', '')

        # Attempt PostgreSQL connection
        connection = psycopg2.connect(
            host=pg_host,
            port=int(pg_port),
            database=pg_database,
            user=pg_user,
            password=pg_password,
            connect_timeout=10
        )

        # Test the connection with a simple query
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if result and result[0] == 1:
            print("SUCCESS: Database connection OK")
            return True
        else:
            print("FAILURE: Database connection FAILED - Query returned unexpected result")
            return False

    except ImportError:
        print("FAILURE: Database connection FAILED - psycopg2 not installed (but PostgreSQL is configured)")
        return False
    except PGOperationalError as e:
        print(f"FAILURE: Database connection FAILED - {e}")
        return False
    except Exception as e:
        print(f"FAILURE: Database connection FAILED - {e}")
        return False


def test_optional_redis() -> Any:
    """Test Redis if configured, but don't fail if not available."""
    try:
        # Check if Redis is explicitly disabled or not configured
        redis_host = os.getenv('REDIS_HOST')
        if not redis_host:
            print("SUCCESS: Redis not configured - application will work without caching")
            return True

        # Test Redis connection if configured
        import redis
        from redis import ConnectionError as RedisConnectionError

        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_password = os.getenv('REDIS_PASSWORD')
        redis_db = int(os.getenv('REDIS_DB', '0'))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            health_check_interval=30
        )

        response = redis_client.ping()
        redis_client.close()

        if response:
            print("SUCCESS: Redis connection OK")
        else:
            print("SUCCESS: Redis not available - application will work without caching")
        return True

    except ImportError:
        print("SUCCESS: Redis not installed - application will work without caching")
        return True
    except RedisConnectionError:
        print("SUCCESS: Redis not running - application will work without caching")
        return True
    except Exception:
        print("SUCCESS: Redis not available - application will work without caching")
        return True


def main() -> None:
    """Main dependency verification function."""
    # Suppress all logging to keep output clean
    logging.getLogger().setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    logging.getLogger('redis').setLevel(logging.CRITICAL)
    logging.getLogger('psycopg2').setLevel(logging.CRITICAL)

    # Load configuration
    if not load_configuration():
        sys.exit(1)

    # Test database connection (SQLite by default)
    db_success = test_sqlite_connection()

    # Test optional Redis (doesn't fail if not available)
    redis_success = test_optional_redis()

    # Overall success if database is working (Redis is optional)
    if db_success:
        print("\nOVERALL: All required dependencies are working")
        sys.exit(0)
    else:
        print("\nOVERALL: Required dependency (database) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
