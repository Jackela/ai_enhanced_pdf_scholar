"""
PostgreSQL Database Configuration and Migration
Production-ready PostgreSQL setup with connection pooling and optimization.
"""

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import psycopg2
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# PostgreSQL Configuration
# ============================================================================


class PostgreSQLConfig:
    """PostgreSQL database configuration."""

    def __init__(self) -> None:
        """Initialize PostgreSQL configuration from environment."""
        # Connection parameters
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = os.getenv("POSTGRES_DB", "ai_pdf_scholar")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD", "")

        # Connection pool settings
        self.pool_size = int(os.getenv("POSTGRES_POOL_SIZE", "20"))
        self.max_overflow = int(os.getenv("POSTGRES_MAX_OVERFLOW", "40"))
        self.pool_timeout = int(os.getenv("POSTGRES_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("POSTGRES_POOL_RECYCLE", "3600"))

        # Performance settings
        self.statement_timeout = int(
            os.getenv("POSTGRES_STATEMENT_TIMEOUT", "30000")
        )  # ms
        self.lock_timeout = int(os.getenv("POSTGRES_LOCK_TIMEOUT", "10000"))  # ms
        self.idle_in_transaction_timeout = int(
            os.getenv("POSTGRES_IDLE_TIMEOUT", "60000")
        )  # ms

        # Read replica configuration
        self.read_replica_host = os.getenv("POSTGRES_READ_REPLICA_HOST", self.host)
        self.read_replica_port = int(
            os.getenv("POSTGRES_READ_REPLICA_PORT", str(self.port))
        )

        # SSL configuration
        self.ssl_mode = os.getenv(
            "POSTGRES_SSL_MODE", "prefer"
        )  # disable, allow, prefer, require
        self.ssl_cert = os.getenv("POSTGRES_SSL_CERT")
        self.ssl_key = os.getenv("POSTGRES_SSL_KEY")
        self.ssl_ca = os.getenv("POSTGRES_SSL_CA")

    def get_connection_url(
        self, async_mode: bool = False, read_only: bool = False
    ) -> str:
        """Get PostgreSQL connection URL."""
        if read_only:
            host = self.read_replica_host
            port = self.read_replica_port
        else:
            host = self.host
            port = self.port

        driver = "postgresql+asyncpg" if async_mode else "postgresql+psycopg2"

        return f"{driver}://{self.user}:{self.password}@{host}:{port}/{self.database}"

    def get_connection_params(self, read_only: bool = False) -> dict[str, Any]:
        """Get connection parameters dictionary."""
        if read_only:
            host = self.read_replica_host
            port = self.read_replica_port
        else:
            host = self.host
            port = self.port

        params = {
            "host": host,
            "port": port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "connect_timeout": 10,
            "options": f"-c statement_timeout={self.statement_timeout}",
        }

        # Add SSL parameters if configured
        if self.ssl_mode != "disable":
            params["sslmode"] = self.ssl_mode
            if self.ssl_cert:
                params["sslcert"] = self.ssl_cert
            if self.ssl_key:
                params["sslkey"] = self.ssl_key
            if self.ssl_ca:
                params["sslrootcert"] = self.ssl_ca

        return params


# ============================================================================
# Connection Pool Manager
# ============================================================================


class PostgreSQLConnectionPool:
    """
    PostgreSQL connection pool manager with read/write splitting.
    """

    def __init__(self, config: PostgreSQLConfig) -> None:
        """Initialize connection pools."""
        self.config = config

        # Create write pool (master)
        self.write_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=config.pool_size,
            **config.get_connection_params(read_only=False),
        )

        # Create read pool (replica)
        self.read_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=config.pool_size,
            **config.get_connection_params(read_only=True),
        )

        logger.info("PostgreSQL connection pools initialized")

    @contextmanager
    def get_connection(self, read_only: bool = False) -> Generator:
        """Get a connection from the appropriate pool."""
        pool = self.read_pool if read_only else self.write_pool
        conn = None

        try:
            conn = pool.getconn()
            yield conn
        finally:
            if conn:
                pool.putconn(conn)

    def close_all(self) -> None:
        """Close all connections in pools."""
        self.write_pool.closeall()
        self.read_pool.closeall()
        logger.info("All PostgreSQL connections closed")


# ============================================================================
# SQLAlchemy Engine Factory
# ============================================================================


class PostgreSQLEngineFactory:
    """
    Factory for creating optimized SQLAlchemy engines.
    """

    @staticmethod
    def create_engine(
        config: PostgreSQLConfig, read_only: bool = False, async_mode: bool = False
    ) -> Engine:
        """Create optimized SQLAlchemy engine."""
        url = config.get_connection_url(async_mode, read_only)

        # Engine configuration
        engine_config = {
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "pool_timeout": config.pool_timeout,
            "pool_recycle": config.pool_recycle,
            "pool_pre_ping": True,  # Verify connections before using
            "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
            "future": True,  # Use SQLAlchemy 2.0 style
        }

        # Use NullPool for async to avoid conflicts with asyncpg
        if async_mode:
            engine_config["poolclass"] = NullPool
        else:
            engine_config["poolclass"] = QueuePool

        # Connection arguments
        connect_args = {
            "server_settings": {
                "application_name": "ai_pdf_scholar",
                "jit": "off",  # Disable JIT for consistent performance
            },
            "command_timeout": config.statement_timeout / 1000,  # Convert to seconds
        }

        if not async_mode:
            connect_args["options"] = f"-c statement_timeout={config.statement_timeout}"

        engine = create_engine(url, connect_args=connect_args, **engine_config)

        # Add event listeners for optimization
        PostgreSQLEngineFactory._setup_engine_events(engine, config)

        return engine

    @staticmethod
    def _setup_engine_events(engine: Engine, config: PostgreSQLConfig) -> None:
        """Setup engine event listeners for optimization."""

        @event.listens_for(engine, "connect")
        def set_postgresql_params(dbapi_conn, connection_record) -> None:
            """Set PostgreSQL session parameters on connect."""
            with dbapi_conn.cursor() as cursor:
                # Set performance parameters
                cursor.execute(
                    "SET statement_timeout = %s", (config.statement_timeout,)
                )
                cursor.execute("SET lock_timeout = %s", (config.lock_timeout,))
                cursor.execute(
                    "SET idle_in_transaction_session_timeout = %s",
                    (config.idle_in_transaction_timeout,),
                )

                # Set work_mem for better query performance
                cursor.execute("SET work_mem = '256MB'")

                # Enable parallel query execution
                cursor.execute("SET max_parallel_workers_per_gather = 4")

                # Set random_page_cost for SSD
                cursor.execute("SET random_page_cost = 1.1")

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ) -> None:
            """Log slow queries."""
            conn.info.setdefault("query_start_time", []).append(datetime.utcnow())

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ) -> None:
            """Log query execution time."""
            total_time = datetime.utcnow() - conn.info["query_start_time"].pop(-1)

            # Log slow queries (> 1 second)
            if total_time.total_seconds() > 1:
                logger.warning(
                    f"Slow query detected ({total_time.total_seconds():.2f}s): "
                    f"{statement[:100]}..."
                )


# ============================================================================
# Database Migration
# ============================================================================


class SQLiteToPostgresMigration:
    """
    Migrate data from SQLite to PostgreSQL.
    """

    def __init__(
        self,
        sqlite_path: str,
        postgres_config: PostgreSQLConfig,
        batch_size: int = 1000,
    ) -> None:
        """Initialize migration."""
        self.sqlite_path = sqlite_path
        self.postgres_config = postgres_config
        self.batch_size = batch_size

        # Create engines
        self.sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
        self.postgres_engine = PostgreSQLEngineFactory.create_engine(postgres_config)

    def migrate_schema(self) -> None:
        """Migrate database schema to PostgreSQL."""
        logger.info("Starting schema migration...")

        # Get SQLite metadata
        sqlite_metadata = MetaData()
        sqlite_metadata.reflect(bind=self.sqlite_engine)

        # Create PostgreSQL schema
        postgres_metadata = MetaData()

        for table_name in sqlite_metadata.tables:
            sqlite_table = sqlite_metadata.tables[table_name]

            # Create corresponding PostgreSQL table
            columns = []
            for column in sqlite_table.columns:
                # Convert SQLite types to PostgreSQL types
                pg_column = self._convert_column(column)
                columns.append(pg_column)

            # Create table
            pg_table = Table(table_name, postgres_metadata, *columns)

            # Add indexes
            for index in sqlite_table.indexes:
                self._create_index(pg_table, index)

        # Create all tables in PostgreSQL
        postgres_metadata.create_all(self.postgres_engine)

        logger.info("Schema migration completed")

    def migrate_data(self) -> None:
        """Migrate data from SQLite to PostgreSQL."""
        logger.info("Starting data migration...")

        sqlite_session = sessionmaker(bind=self.sqlite_engine)()
        postgres_session = sessionmaker(bind=self.postgres_engine)()

        try:
            # Get all tables
            metadata = MetaData()
            metadata.reflect(bind=self.sqlite_engine)

            for table_name in metadata.tables:
                logger.info(f"Migrating table: {table_name}")

                # Count records
                count_query = text(f"SELECT COUNT(*) FROM {table_name}")
                total_records = sqlite_session.execute(count_query).scalar()

                if total_records == 0:
                    continue

                # Migrate in batches
                offset = 0
                while offset < total_records:
                    # Read batch from SQLite
                    select_query = text(
                        f"SELECT * FROM {table_name} "
                        f"LIMIT {self.batch_size} OFFSET {offset}"
                    )
                    rows = sqlite_session.execute(select_query).fetchall()

                    if not rows:
                        break

                    # Insert into PostgreSQL
                    self._insert_batch(postgres_session, table_name, rows)

                    offset += self.batch_size

                    # Log progress
                    progress = min(100, (offset / total_records) * 100)
                    logger.info(
                        f"  {table_name}: {progress:.1f}% ({offset}/{total_records})"
                    )

                # Update sequences for auto-increment columns
                self._update_sequences(postgres_session, table_name)

            postgres_session.commit()
            logger.info("Data migration completed")

        except Exception as e:
            postgres_session.rollback()
            logger.error(f"Data migration failed: {e}")
            raise
        finally:
            sqlite_session.close()
            postgres_session.close()

    def verify_migration(self) -> dict[str, Any]:
        """Verify migration integrity."""
        logger.info("Verifying migration...")

        sqlite_session = sessionmaker(bind=self.sqlite_engine)()
        postgres_session = sessionmaker(bind=self.postgres_engine)()

        results = {
            "tables": {},
            "total_records": {"sqlite": 0, "postgres": 0},
            "success": True,
        }

        try:
            metadata = MetaData()
            metadata.reflect(bind=self.sqlite_engine)

            for table_name in metadata.tables:
                # Count records in both databases
                sqlite_count = sqlite_session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()

                postgres_count = postgres_session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                ).scalar()

                results["tables"][table_name] = {
                    "sqlite": sqlite_count,
                    "postgres": postgres_count,
                    "match": sqlite_count == postgres_count,
                }

                results["total_records"]["sqlite"] += sqlite_count
                results["total_records"]["postgres"] += postgres_count

                if sqlite_count != postgres_count:
                    results["success"] = False
                    logger.error(
                        f"Record count mismatch in {table_name}: "
                        f"SQLite={sqlite_count}, PostgreSQL={postgres_count}"
                    )

            logger.info(
                f"Migration verification: {'PASSED' if results['success'] else 'FAILED'}"
            )

        finally:
            sqlite_session.close()
            postgres_session.close()

        return results

    def _convert_column(self, sqlite_column) -> Any:
        """Convert SQLite column to PostgreSQL column."""

        # Map SQLite types to PostgreSQL types
        type_mapping = {
            "INTEGER": Integer,
            "TEXT": Text,
            "REAL": Float,
            "BLOB": psycopg2.Binary,
            "BOOLEAN": Boolean,
            "DATETIME": DateTime,
            "JSON": JSON,
        }

        # Get PostgreSQL type
        sqlite_type = str(sqlite_column.type)
        pg_type = type_mapping.get(sqlite_type.upper(), String)

        # Create PostgreSQL column
        pg_column = Column(
            sqlite_column.name,
            pg_type,
            primary_key=sqlite_column.primary_key,
            nullable=sqlite_column.nullable,
            unique=sqlite_column.unique,
            default=sqlite_column.default,
            autoincrement=sqlite_column.autoincrement,
        )

        return pg_column

    def _create_index(self, table, sqlite_index) -> None:
        """Create PostgreSQL index from SQLite index."""
        columns = [table.c[col.name] for col in sqlite_index.columns]

        Index(sqlite_index.name, *columns, unique=sqlite_index.unique)

    def _insert_batch(self, session, table_name: str, rows) -> None:
        """Insert batch of rows into PostgreSQL."""
        if not rows:
            return

        # Convert rows to dictionaries
        row_dicts = [dict[str, Any](row) for row in rows]

        # Use PostgreSQL COPY for better performance
        insert_query = text(
            f"INSERT INTO {table_name} ({','.join(row_dicts[0].keys())}) "
            f"VALUES ({','.join([':' + k for k in row_dicts[0].keys()])})"
        )

        session.execute(insert_query, row_dicts)

    def _update_sequences(self, session, table_name: str) -> None:
        """Update PostgreSQL sequences for auto-increment columns."""
        try:
            # Find primary key column
            result = session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :table_name AND column_default LIKE 'nextval%'"
                ),
                {"table_name": table_name},
            ).fetchone()

            if result:
                column_name = result[0]

                # Get max value
                max_value = session.execute(
                    text(f"SELECT MAX({column_name}) FROM {table_name}")
                ).scalar()

                if max_value:
                    # Update sequence
                    session.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{table_name}', '{column_name}'), "
                            f"{max_value}, true)"
                        )
                    )
        except Exception as e:
            logger.warning(f"Could not update sequence for {table_name}: {e}")


# ============================================================================
# Database Optimization
# ============================================================================


class PostgreSQLOptimizer:
    """
    PostgreSQL database optimization utilities.
    """

    def __init__(self, engine: Engine) -> None:
        """Initialize optimizer."""
        self.engine = engine

    def analyze_tables(self) -> None:
        """Run ANALYZE on all tables to update statistics."""
        with self.engine.connect() as conn:
            tables = conn.execute(
                text("SELECT tablename FROM pg_tables " "WHERE schemaname = 'public'")
            ).fetchall()

            for table in tables:
                # Safe: table names come from system catalog, not user input
                conn.execute(text(f"ANALYZE {table[0]}"))
                logger.info(f"Analyzed table: {table[0]}")

    def create_missing_indexes(self) -> None:
        """Create recommended indexes based on query patterns."""
        recommended_indexes = [
            # User tables
            ("users", ["email"], True),
            ("users", ["created_at"], False),
            # Document tables
            ("documents", ["user_id", "created_at"], False),
            ("documents", ["content_hash"], True),
            # Audit tables
            ("audit_logs", ["user_id", "timestamp"], False),
            ("audit_logs", ["event_type", "timestamp"], False),
            # Session tables
            ("sessions", ["token"], True),
            ("sessions", ["user_id", "expires_at"], False),
        ]

        with self.engine.connect() as conn:
            for table, columns, unique in recommended_indexes:
                index_name = f"idx_{table}_{'_'.join(columns)}"

                # Check if index exists
                exists = conn.execute(
                    text("SELECT 1 FROM pg_indexes " "WHERE indexname = :index_name"),
                    {"index_name": index_name},
                ).fetchone()

                if not exists:
                    # Create index
                    unique_clause = "UNIQUE" if unique else ""
                    columns_str = ", ".join(columns)

                    conn.execute(
                        text(
                            f"CREATE {unique_clause} INDEX CONCURRENTLY "
                            f"{index_name} ON {table} ({columns_str})"
                        )
                    )

                    logger.info(f"Created index: {index_name}")

    def vacuum_analyze(self) -> None:
        """Run VACUUM ANALYZE on all tables."""
        with self.engine.connect() as conn:
            conn.execute(
                text("SET statement_timeout = 0")
            )  # No timeout for maintenance

            tables = conn.execute(
                text("SELECT tablename FROM pg_tables " "WHERE schemaname = 'public'")
            ).fetchall()

            for table in tables:
                # Safe: table names come from system catalog, not user input
                conn.execute(text(f"VACUUM ANALYZE {table[0]}"))
                logger.info(f"Vacuumed and analyzed table: {table[0]}")

    def get_slow_queries(self, min_duration_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries from pg_stat_statements."""
        with self.engine.connect() as conn:
            # Enable pg_stat_statements if not already enabled
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))
            except:
                pass

            # Get slow queries
            result = conn.execute(
                text(
                    """
                    SELECT
                        query,
                        calls,
                        total_exec_time,
                        mean_exec_time,
                        stddev_exec_time,
                        rows
                    FROM pg_stat_statements
                    WHERE mean_exec_time > :min_duration
                    ORDER BY mean_exec_time DESC
                    LIMIT 20
                    """
                ),
                {"min_duration": min_duration_ms},
            ).fetchall()

            return [
                {
                    "query": row[0],
                    "calls": row[1],
                    "total_time": row[2],
                    "mean_time": row[3],
                    "stddev_time": row[4],
                    "rows": row[5],
                }
                for row in result
            ]


if __name__ == "__main__":
    # Example migration
    pass
