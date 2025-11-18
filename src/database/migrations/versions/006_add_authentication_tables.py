"""
Migration 006: Add Authentication Tables

Creates comprehensive authentication and user management tables including:
- users table with security features
- refresh_tokens table for JWT token management
- user_sessions table for session tracking
- login_attempts table for security monitoring
- audit_log table for security auditing
"""

import logging

try:
    from ..base import BaseMigration
except ImportError:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).parent.parent))
    from base import BaseMigration

logger = logging.getLogger(__name__)


class AddAuthenticationTablesMigration(BaseMigration):
    """
    Creates authentication and user management system tables.

    This migration establishes a comprehensive authentication system with:
    - JWT-based authentication with refresh tokens
    - Session management and tracking
    - Security monitoring and audit trails
    - Account lockout and password security
    """

    @property
    def version(self) -> int:
        return 6

    @property
    def description(self) -> str:
        return "Add authentication tables for JWT-based user management system"

    @property
    def rollback_supported(self) -> bool:
        return True

    def up(self) -> None:
        """Apply the authentication tables migration."""
        logger.info("Creating authentication and user management tables")

        # Create core authentication tables
        self._create_users_table()
        self._create_refresh_tokens_table()
        self._create_user_sessions_table()
        self._create_login_attempts_table()
        self._create_audit_log_table()

        # Create performance indexes
        self._create_authentication_indexes()

        # Create default admin user
        self._create_default_admin_user()

        logger.info("Authentication tables migration completed successfully")

    def down(self) -> None:
        """Rollback the authentication tables migration."""
        logger.info("Rolling back authentication tables migration")

        # Drop tables in reverse order (respecting foreign keys)
        tables_to_drop = [
            "audit_log",
            "login_attempts",
            "user_sessions",
            "refresh_tokens",
            "users",
        ]

        for table in tables_to_drop:
            try:
                self.execute_sql(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Could not drop table {table}: {e}")

        logger.info("Authentication tables rollback completed")

    def _create_users_table(self) -> None:
        """Create the users table with comprehensive security features."""
        users_sql = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            role VARCHAR(20) DEFAULT 'user' NOT NULL,
            is_active BOOLEAN DEFAULT 1 NOT NULL,
            is_verified BOOLEAN DEFAULT 0 NOT NULL,
            account_status VARCHAR(30) DEFAULT 'pending_verification' NOT NULL,
            failed_login_attempts INTEGER DEFAULT 0 NOT NULL,
            last_failed_login DATETIME,
            account_locked_until DATETIME,
            password_changed_at DATETIME,
            password_reset_token VARCHAR(255),
            password_reset_expires DATETIME,
            email_verification_token VARCHAR(255),
            email_verified_at DATETIME,
            refresh_token_version INTEGER DEFAULT 0 NOT NULL,
            last_login DATETIME,
            last_activity DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            security_metadata TEXT
        )
        """
        self.execute_sql(users_sql)
        logger.info("Created users table")

    def _create_refresh_tokens_table(self) -> None:
        """Create the refresh_tokens table for JWT token management."""
        refresh_tokens_sql = """
        CREATE TABLE refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_jti VARCHAR(255) UNIQUE NOT NULL,
            token_family VARCHAR(255) NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            revoked_at DATETIME,
            revoked_reason VARCHAR(255),
            device_info VARCHAR(500),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
        self.execute_sql(refresh_tokens_sql)
        logger.info("Created refresh_tokens table")

    def _create_user_sessions_table(self) -> None:
        """Create the user_sessions table for session tracking."""
        user_sessions_sql = """
        CREATE TABLE user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token VARCHAR(255) UNIQUE NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            ended_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
        self.execute_sql(user_sessions_sql)
        logger.info("Created user_sessions table")

    def _create_login_attempts_table(self) -> None:
        """Create the login_attempts table for security monitoring."""
        login_attempts_sql = """
        CREATE TABLE login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(255) NOT NULL,
            ip_address VARCHAR(45),
            user_agent TEXT,
            success BOOLEAN NOT NULL,
            failure_reason VARCHAR(255),
            attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
        self.execute_sql(login_attempts_sql)
        logger.info("Created login_attempts table")

    def _create_audit_log_table(self) -> None:
        """Create the audit_log table for security auditing."""
        audit_log_sql = """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50),
            resource_id INTEGER,
            details TEXT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        """
        self.execute_sql(audit_log_sql)
        logger.info("Created audit_log table")

    def _create_authentication_indexes(self) -> None:
        """Create indexes for authentication table performance."""
        auth_indexes = [
            # Users table indexes
            "CREATE INDEX idx_users_username ON users(username)",
            "CREATE INDEX idx_users_email ON users(email)",
            "CREATE INDEX idx_users_role ON users(role)",
            "CREATE INDEX idx_users_is_active ON users(is_active)",
            "CREATE INDEX idx_users_last_login ON users(last_login DESC)",
            "CREATE INDEX idx_users_created_at ON users(created_at DESC)",
            # Refresh tokens indexes
            "CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id)",
            "CREATE INDEX idx_refresh_tokens_jti ON refresh_tokens(token_jti)",
            "CREATE INDEX idx_refresh_tokens_family ON refresh_tokens(token_family)",
            "CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at)",
            "CREATE INDEX idx_refresh_tokens_revoked ON refresh_tokens(revoked_at)",
            # User sessions indexes
            "CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id)",
            "CREATE INDEX idx_user_sessions_token ON user_sessions(session_token)",
            "CREATE INDEX idx_user_sessions_active ON user_sessions(ended_at) WHERE ended_at IS NULL",
            # Login attempts indexes
            "CREATE INDEX idx_login_attempts_username ON login_attempts(username)",
            "CREATE INDEX idx_login_attempts_ip ON login_attempts(ip_address)",
            "CREATE INDEX idx_login_attempts_time ON login_attempts(attempted_at DESC)",
            "CREATE INDEX idx_login_attempts_success ON login_attempts(success)",
            # Audit log indexes
            "CREATE INDEX idx_audit_log_user_id ON audit_log(user_id)",
            "CREATE INDEX idx_audit_log_action ON audit_log(action)",
            "CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id)",
            "CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC)",
        ]

        for index_sql in auth_indexes:
            try:
                self.execute_sql(index_sql)
            except Exception as e:
                logger.warning(f"Could not create auth index: {e}")

        logger.info("Created authentication indexes")

    def _create_default_admin_user(self) -> None:
        """Create default admin user with secure password."""
        try:
            # Import bcrypt for password hashing
            import bcrypt
            import os
            import secrets
            import string

            # Get default admin password from environment variable or generate a secure one
            default_password = os.getenv("DEFAULT_ADMIN_PASSWORD")
            if not default_password:
                # Generate a secure random password if not provided
                alphabet = string.ascii_letters + string.digits + string.punctuation
                default_password = "".join(secrets.choice(alphabet) for _ in range(16))
                print(
                    f"WARNING: No DEFAULT_ADMIN_PASSWORD environment variable set. "
                    f"Generated temporary password: {default_password}"
                )
                print(
                    "IMPORTANT: Please change this password immediately after first login!"
                )

            password_hash = bcrypt.hashpw(
                default_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
            ).decode("utf-8")

            admin_user_sql = """
            INSERT INTO users (
                username, email, password_hash, full_name, role,
                is_active, is_verified, account_status, email_verified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            self.execute_sql(
                admin_user_sql,
                (
                    "admin",
                    "admin@localhost",
                    password_hash,
                    "System Administrator",
                    "admin",
                    1,  # is_active
                    1,  # is_verified
                    "active",
                ),
            )

            logger.info(
                "Created default admin user (username: admin, password: admin123!)"
            )
            logger.warning(
                "⚠️ IMPORTANT: Change the default admin password immediately!"
            )

        except ImportError:
            logger.error("bcrypt not available - cannot create default admin user")
            logger.info(
                "You will need to create admin user manually after installing bcrypt"
            )
        except Exception as e:
            logger.warning(
                f"Could not create default admin user (may already exist): {e}"
            )

    def pre_migrate_checks(self) -> bool:
        """Perform pre-migration validation."""
        if not super().pre_migrate_checks():
            return False

        # Check if authentication tables already exist
        existing_tables = []
        try:
            results = self.db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
                "('users', 'refresh_tokens', 'user_sessions', 'login_attempts', 'audit_log')"
            )
            existing_tables = [row["name"] for row in results]
        except Exception as e:
            logger.warning(f"Could not check existing tables: {e}")

        if existing_tables:
            logger.warning(
                f"Some authentication tables already exist: {existing_tables}"
            )
            return False  # Skip if already applied

        return True

    def post_migrate_checks(self) -> bool:
        """Validate migration completed successfully."""
        required_tables = [
            "users",
            "refresh_tokens",
            "user_sessions",
            "login_attempts",
            "audit_log",
        ]

        try:
            for table in required_tables:
                result = self.db.fetch_one(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                )
                if not result:
                    logger.error(f"Required table {table} was not created")
                    return False

            # Check that admin user was created
            admin_count = self.db.fetch_one(
                "SELECT COUNT(*) as count FROM users WHERE username='admin'"
            )
            if admin_count and admin_count["count"] > 0:
                logger.info("Default admin user was created successfully")
            else:
                logger.warning("Default admin user was not created")

            logger.info("Post-migration validation passed")
            return True

        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return False
