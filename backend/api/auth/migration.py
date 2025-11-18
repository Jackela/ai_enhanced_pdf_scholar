"""
Authentication Database Migration
Creates tables for users and refresh tokens.
"""

import logging

logger = logging.getLogger(__name__)


class AuthenticationMigration:
    """Migration for authentication tables."""

    @staticmethod
    def get_migration_sql() -> list[str]:
        """
        Get SQL statements for creating authentication tables.

        Returns:
            List of SQL CREATE TABLE statements
        """
        return [
            # Users table
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(20) DEFAULT 'user' NOT NULL,

                -- Security fields
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                is_verified BOOLEAN DEFAULT 0 NOT NULL,
                account_status VARCHAR(30) DEFAULT 'pending_verification' NOT NULL,
                failed_login_attempts INTEGER DEFAULT 0 NOT NULL,
                last_failed_login TIMESTAMP,
                account_locked_until TIMESTAMP,

                -- Password management
                password_changed_at TIMESTAMP,
                password_reset_token VARCHAR(255),
                password_reset_expires TIMESTAMP,

                -- Email verification
                email_verification_token VARCHAR(255),
                email_verified_at TIMESTAMP,

                -- Session management
                refresh_token_version INTEGER DEFAULT 0 NOT NULL,
                last_login TIMESTAMP,
                last_activity TIMESTAMP,

                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                security_metadata TEXT,

                -- Indexes included
                CHECK (role IN ('admin', 'user', 'viewer', 'moderator')),
                CHECK (account_status IN ('active', 'inactive', 'locked', 'suspended', 'pending_verification'))
            )
            """,
            # Create indexes for users table
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            # Refresh tokens table
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_jti VARCHAR(255) NOT NULL UNIQUE,
                token_family VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP,
                revoked_reason VARCHAR(255),
                device_info VARCHAR(500),

                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            # Create indexes for refresh_tokens table
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_jti ON refresh_tokens(token_jti)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_family ON refresh_tokens(token_family)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked_at ON refresh_tokens(revoked_at)",
            # Password history table (for future use)
            """
            CREATE TABLE IF NOT EXISTS password_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            # Create index for password_history
            "CREATE INDEX IF NOT EXISTS idx_password_history_user_id ON password_history(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_password_history_created_at ON password_history(created_at)",
            # Login attempts table (for audit logging)
            """
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(255) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                user_agent VARCHAR(500),
                success BOOLEAN NOT NULL,
                failure_reason VARCHAR(255),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            # Create indexes for login_attempts
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON login_attempts(username)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_address ON login_attempts(ip_address)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_timestamp ON login_attempts(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_success ON login_attempts(success)",
            # User sessions table (for tracking active sessions)
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id VARCHAR(255) NOT NULL UNIQUE,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,

                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            # Create indexes for user_sessions
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at)",
        ]

    @staticmethod
    def migrate(db_connection) -> bool:
        """
        Run the authentication migration.

        Args:
            db_connection: Database connection object with execute method

        Returns:
            True if successful, False otherwise
        """
        try:
            sql_statements = AuthenticationMigration.get_migration_sql()

            for sql in sql_statements:
                try:
                    db_connection.execute(sql)
                    db_connection.commit()
                except Exception as e:
                    # Table might already exist, log and continue
                    if "already exists" not in str(e).lower():
                        logger.error(f"Migration statement failed: {str(e)}")
                        logger.error(f"SQL: {sql[:100]}...")
                        return False

            logger.info("Authentication tables migration completed successfully")
            return True

        except Exception as e:
            logger.error(f"Authentication migration failed: {str(e)}")
            return False

    @staticmethod
    def rollback(db_connection) -> bool:
        """
        Rollback the authentication migration.

        Args:
            db_connection: Database connection object

        Returns:
            True if successful, False otherwise
        """
        try:
            tables = [
                "user_sessions",
                "login_attempts",
                "password_history",
                "refresh_tokens",
                "users",
            ]

            for table in tables:
                try:
                    db_connection.execute(f"DROP TABLE IF EXISTS {table}")
                    db_connection.commit()
                except Exception as e:
                    logger.error(f"Failed to drop table {table}: {str(e)}")

            logger.info("Authentication tables rollback completed")
            return True

        except Exception as e:
            logger.error(f"Authentication rollback failed: {str(e)}")
            return False
