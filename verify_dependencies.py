#!/usr/bin/env python3
"""
Dependency Verification Script
Standalone script to test PostgreSQL and Redis connections independently.
Does NOT start the web server - only tests dependency connections.
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def load_configuration():
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

def test_postgresql_connection():
    """Test PostgreSQL database connection."""
    try:
        # Import PostgreSQL adapter
        import psycopg2
        from psycopg2 import OperationalError as PGOperationalError

        # Get PostgreSQL connection parameters from environment or defaults
        pg_host = os.getenv('POSTGRES_HOST', os.getenv('DATABASE_HOST', 'localhost'))
        pg_port = os.getenv('POSTGRES_PORT', os.getenv('DATABASE_PORT', '5432'))
        pg_database = os.getenv('POSTGRES_DATABASE', os.getenv('DATABASE_NAME', 'ai_pdf_scholar'))
        pg_user = os.getenv('POSTGRES_USER', os.getenv('DATABASE_USER', 'postgres'))
        pg_password = os.getenv('POSTGRES_PASSWORD', os.getenv('DATABASE_PASSWORD', ''))

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
        else:
            print("FAILURE: Database connection FAILED - Query returned unexpected result")

    except ImportError:
        print("FAILURE: Database connection FAILED - psycopg2 not installed")
    except PGOperationalError as e:
        print(f"FAILURE: Database connection FAILED - {e}")
    except ValueError as e:
        print(f"FAILURE: Database connection FAILED - Invalid port number: {e}")
    except Exception as e:
        print(f"FAILURE: Database connection FAILED - {e}")

def test_redis_connection():
    """Test Redis server connection."""
    try:
        # Import Redis
        import redis
        from redis import ConnectionError as RedisConnectionError
        from redis import TimeoutError as RedisTimeoutError

        # Get Redis connection parameters from environment or defaults
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_password = os.getenv('REDIS_PASSWORD')
        redis_db = int(os.getenv('REDIS_DB', '0'))

        # Create Redis connection with timeout settings
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            health_check_interval=30
        )

        # Test the connection with ping
        response = redis_client.ping()

        # Close the connection
        redis_client.close()

        if response:
            print("SUCCESS: Redis connection OK")
        else:
            print("FAILURE: Redis connection FAILED - Ping returned False")

    except ImportError:
        print("FAILURE: Redis connection FAILED - redis package not installed")
    except RedisConnectionError as e:
        print(f"FAILURE: Redis connection FAILED - {e}")
    except RedisTimeoutError as e:
        print(f"FAILURE: Redis connection FAILED - Connection timeout: {e}")
    except ValueError as e:
        print(f"FAILURE: Redis connection FAILED - Invalid configuration: {e}")
    except Exception as e:
        print(f"FAILURE: Redis connection FAILED - {e}")

def main():
    """Main dependency verification function."""
    # Suppress all logging to keep output clean
    logging.getLogger().setLevel(logging.CRITICAL)

    # Suppress specific loggers that might interfere
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    logging.getLogger('redis').setLevel(logging.CRITICAL)
    logging.getLogger('psycopg2').setLevel(logging.CRITICAL)

    # Load configuration
    if not load_configuration():
        sys.exit(1)

    # Test PostgreSQL connection
    test_postgresql_connection()

    # Test Redis connection
    test_redis_connection()

if __name__ == "__main__":
    main()
