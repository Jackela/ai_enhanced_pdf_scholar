"""
Production Database Configuration and Optimization
Advanced database configuration with connection pooling, performance tuning,
read/write splitting, and monitoring integration.
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Union
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import asyncpg as asyncpg_dialect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import QueuePool

from ..config.production import ProductionConfig
from ..services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


@dataclass
class DatabasePerformanceConfig:
    """Database performance optimization configuration."""

    # Connection pool configuration
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True

    # Connection management
    connect_timeout: int = 10
    command_timeout: int = 30
    server_settings: dict[str, str] = field(
        default_factory=lambda: {
            "application_name": "ai_pdf_scholar_prod",
            "timezone": "UTC",
            "statement_timeout": "30s",
            "idle_in_transaction_session_timeout": "60s",
            "lock_timeout": "10s",
        }
    )

    # Performance tuning
    echo: bool = False
    echo_pool: bool = False
    enable_query_cache: bool = True
    query_cache_size: int = 1000

    # Read/write splitting
    enable_read_write_split: bool = False
    read_replica_urls: list[str] = field(default_factory=list)
    read_weight: float = 0.7  # 70% reads go to replicas

    # Monitoring
    enable_connection_monitoring: bool = True
    slow_query_threshold: float = 1.0  # Log queries slower than 1 second
    enable_query_logging: bool = False  # Disable in production for performance


@dataclass
class DatabaseConnectionStats:
    """Database connection statistics."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    slow_queries: int = 0
    total_queries: int = 0
    avg_query_time: float = 0.0
    connection_errors: list[str] = field(default_factory=list)


class ProductionDatabaseManager:
    """
    Production-ready database manager with advanced connection pooling,
    performance monitoring, and high availability features.
    """

    def __init__(
        self,
        database_url: str,
        performance_config: DatabasePerformanceConfig | None = None,
        metrics_service: MetricsService | None = None,
    ):
        """Initialize production database manager."""
        self.database_url = database_url
        self.performance_config = performance_config or DatabasePerformanceConfig()
        self.metrics_service = metrics_service

        # Connection management
        self.master_engine: AsyncEngine | None = None
        self.read_engines: list[AsyncEngine] = []
        self.session_factory: async_sessionmaker | None = None

        # Statistics and monitoring
        self.connection_stats = DatabaseConnectionStats()
        self.query_times: list[float] = []

        # Connection pools
        self._connection_pools: dict[str, Any] = {}

        logger.info("Production database manager initialized")

    async def initialize(self) -> None:
        """Initialize database connections and engines."""
        try:
            # Create master (read/write) engine
            await self._create_master_engine()

            # Create read replica engines if configured
            if (
                self.performance_config.enable_read_write_split
                and self.performance_config.read_replica_urls
            ):
                await self._create_read_engines()

            # Create session factory
            self._create_session_factory()

            # Set up monitoring
            await self._setup_monitoring()

            # Test connections
            await self._test_connections()

            logger.info("Database initialization completed successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def _create_master_engine(self) -> None:
        """Create master database engine for read/write operations."""
        # Parse database URL for connection parameters
        parsed_url = urlparse(self.database_url)

        # Build connection arguments
        connect_args = {
            "command_timeout": self.performance_config.command_timeout,
            "server_settings": self.performance_config.server_settings,
        }

        # Add SSL configuration for production
        if (
            parsed_url.scheme == "postgresql+asyncpg"
            and "sslmode" not in self.database_url
        ):
            connect_args["ssl"] = "require"

        # Create engine with optimized pool configuration
        self.master_engine = create_async_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=self.performance_config.pool_size,
            max_overflow=self.performance_config.max_overflow,
            pool_timeout=self.performance_config.pool_timeout,
            pool_recycle=self.performance_config.pool_recycle,
            pool_pre_ping=self.performance_config.pool_pre_ping,
            connect_args=connect_args,
            echo=self.performance_config.echo,
            echo_pool=self.performance_config.echo_pool,
            future=True,
            # Use asyncpg for best performance
            module=asyncpg_dialect.AsyncAdapt_asyncpg_dialect,
        )

        # Set up connection event listeners
        self._setup_connection_events(self.master_engine, "master")

        logger.info("Master database engine created")

    async def _create_read_engines(self) -> None:
        """Create read replica engines for read-only operations."""
        for i, replica_url in enumerate(self.performance_config.read_replica_urls):
            try:
                # Similar configuration as master but potentially smaller pool
                connect_args = {
                    "command_timeout": self.performance_config.command_timeout,
                    "server_settings": {
                        **self.performance_config.server_settings,
                        "default_transaction_read_only": "on",  # Ensure read-only
                    },
                }

                # Create read engine with smaller pool
                read_engine = create_async_engine(
                    replica_url,
                    poolclass=QueuePool,
                    pool_size=max(5, self.performance_config.pool_size // 2),
                    max_overflow=max(10, self.performance_config.max_overflow // 2),
                    pool_timeout=self.performance_config.pool_timeout,
                    pool_recycle=self.performance_config.pool_recycle,
                    pool_pre_ping=self.performance_config.pool_pre_ping,
                    connect_args=connect_args,
                    echo=self.performance_config.echo,
                    future=True,
                )

                # Set up monitoring for read replicas
                self._setup_connection_events(read_engine, f"replica_{i}")

                self.read_engines.append(read_engine)
                logger.info(f"Read replica engine {i} created: {replica_url[:30]}...")

            except Exception as e:
                logger.error(f"Failed to create read replica {i}: {e}")
                # Continue with other replicas

    def _create_session_factory(self) -> None:
        """Create async session factory."""
        self.session_factory = async_sessionmaker(
            bind=self.master_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )

        logger.info("Database session factory created")

    def _setup_connection_events(self, engine: AsyncEngine, engine_name: str) -> None:
        """Set up connection pool event listeners for monitoring."""
        if not self.performance_config.enable_connection_monitoring:
            return

        @sa.event.listens_for(engine.sync_engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            """Handle new database connection."""
            self.connection_stats.total_connections += 1
            if self.metrics_service:
                self.metrics_service.record_db_query(
                    operation="connect", table="connection", duration=0, success=True
                )
            logger.debug(f"New connection established to {engine_name}")

        @sa.event.listens_for(engine.sync_engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            """Handle connection checkout from pool."""
            self.connection_stats.active_connections += 1
            if self.connection_stats.idle_connections > 0:
                self.connection_stats.idle_connections -= 1

        @sa.event.listens_for(engine.sync_engine, "checkin")
        def on_checkin(dbapi_connection, connection_record):
            """Handle connection checkin to pool."""
            if self.connection_stats.active_connections > 0:
                self.connection_stats.active_connections -= 1
            self.connection_stats.idle_connections += 1

        @sa.event.listens_for(engine.sync_engine, "invalidate")
        def on_invalidate(dbapi_connection, connection_record, exception):
            """Handle connection invalidation."""
            self.connection_stats.failed_connections += 1
            error_msg = f"Connection invalidated: {str(exception)}"
            self.connection_stats.connection_errors.append(error_msg)
            logger.warning(f"Connection invalidated on {engine_name}: {exception}")

    async def _setup_monitoring(self) -> None:
        """Set up database performance monitoring."""
        if not self.metrics_service:
            return

        # Update connection metrics
        def update_connection_metrics():
            self.metrics_service.update_db_connections(
                "postgresql", self.connection_stats.total_connections
            )

        # Schedule periodic metrics updates
        import asyncio

        asyncio.create_task(self._periodic_metrics_update())

    async def _periodic_metrics_update(self) -> None:
        """Periodically update database metrics."""
        while True:
            try:
                if self.metrics_service and self.master_engine:
                    # Get pool statistics
                    pool = self.master_engine.pool
                    pool_status = {
                        "size": pool.size(),
                        "checked_in": pool.checkedin(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow(),
                        "total": pool.size() + pool.overflow(),
                    }

                    # Update metrics
                    self.metrics_service.update_db_connections(
                        "postgresql", pool_status["total"]
                    )

                    # Calculate and update performance metrics
                    if self.query_times:
                        avg_query_time = sum(self.query_times[-100:]) / len(
                            self.query_times[-100:]
                        )
                        self.connection_stats.avg_query_time = avg_query_time

                        # Clear old query times to prevent memory growth
                        if len(self.query_times) > 1000:
                            self.query_times = self.query_times[-100:]

                await asyncio.sleep(30)  # Update every 30 seconds

            except Exception as e:
                logger.error(f"Metrics update failed: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def _test_connections(self) -> None:
        """Test database connections."""
        # Test master connection
        try:
            async with self.master_engine.begin() as conn:
                result = await conn.execute(sa.text("SELECT version()"))
                version = result.scalar()
                logger.info(f"Master database connection successful: {version}")
        except Exception as e:
            logger.error(f"Master database connection failed: {e}")
            raise

        # Test read replica connections
        for i, read_engine in enumerate(self.read_engines):
            try:
                async with read_engine.begin() as conn:
                    result = await conn.execute(sa.text("SELECT 1"))
                    await result.scalar()
                    logger.info(f"Read replica {i} connection successful")
            except Exception as e:
                logger.error(f"Read replica {i} connection failed: {e}")
                # Don't fail initialization for read replica failures

    # ========================================================================
    # Session Management
    # ========================================================================

    @asynccontextmanager
    async def get_session(
        self, read_only: bool = False
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session with automatic cleanup.

        Args:
            read_only: If True, prefer read replica for the session

        Yields:
            Database session
        """
        # Choose engine based on read_only flag and availability
        engine = self._choose_engine(read_only)

        # Create session factory for chosen engine if needed
        if engine != self.master_engine:
            session_factory = async_sessionmaker(
                bind=engine, class_=AsyncSession, expire_on_commit=False
            )
        else:
            session_factory = self.session_factory

        session = session_factory()
        start_time = time.time()

        try:
            yield session
            await session.commit()

        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

            # Record session metrics
            session_time = time.time() - start_time
            self.query_times.append(session_time)

            if session_time > self.performance_config.slow_query_threshold:
                self.connection_stats.slow_queries += 1
                logger.warning(f"Slow session detected: {session_time:.2f}s")

    def _choose_engine(self, read_only: bool = False) -> AsyncEngine:
        """Choose appropriate engine based on read/write requirements."""
        if (
            read_only
            and self.performance_config.enable_read_write_split
            and self.read_engines
        ):
            # Use read replica based on weight
            import random

            if random.random() < self.performance_config.read_weight:
                return random.choice(self.read_engines)

        return self.master_engine

    # ========================================================================
    # Query Execution with Monitoring
    # ========================================================================

    async def execute_query(
        self,
        query: Union[str, sa.text],
        parameters: dict[str, Any] | None = None,
        read_only: bool = False,
    ) -> Any:
        """
        Execute query with performance monitoring.

        Args:
            query: SQL query to execute
            parameters: Query parameters
            read_only: If True, use read replica if available

        Returns:
            Query result
        """
        start_time = time.time()

        async with self.get_session(read_only=read_only) as session:
            try:
                if isinstance(query, str):
                    query = sa.text(query)

                if parameters:
                    result = await session.execute(query, parameters)
                else:
                    result = await session.execute(query)

                # Record successful query
                duration = time.time() - start_time
                self.connection_stats.total_queries += 1

                if self.metrics_service:
                    self.metrics_service.record_db_query(
                        operation="select" if read_only else "write",
                        table="unknown",
                        duration=duration,
                        success=True,
                    )

                # Log slow queries
                if duration > self.performance_config.slow_query_threshold:
                    logger.warning(
                        f"Slow query ({duration:.2f}s): {str(query)[:100]}..."
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                self.connection_stats.failed_connections += 1

                if self.metrics_service:
                    self.metrics_service.record_db_query(
                        operation="select" if read_only else "write",
                        table="unknown",
                        duration=duration,
                        success=False,
                    )

                logger.error(f"Query execution failed ({duration:.2f}s): {e}")
                raise

    # ========================================================================
    # Health Monitoring and Statistics
    # ========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Perform comprehensive database health check."""
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "connections": {},
            "performance": {},
            "configuration": {},
        }

        try:
            # Check master connection
            start_time = time.time()
            async with self.master_engine.begin() as conn:
                await conn.execute(sa.text("SELECT 1"))
            master_latency = time.time() - start_time

            health_status["connections"]["master"] = {
                "status": "healthy",
                "latency_ms": round(master_latency * 1000, 2),
            }

            # Check read replicas
            replica_health = []
            for i, read_engine in enumerate(self.read_engines):
                try:
                    start_time = time.time()
                    async with read_engine.begin() as conn:
                        await conn.execute(sa.text("SELECT 1"))
                    replica_latency = time.time() - start_time

                    replica_health.append(
                        {
                            "replica_id": i,
                            "status": "healthy",
                            "latency_ms": round(replica_latency * 1000, 2),
                        }
                    )
                except Exception as e:
                    replica_health.append(
                        {"replica_id": i, "status": "unhealthy", "error": str(e)}
                    )
                    health_status["status"] = "degraded"

            health_status["connections"]["replicas"] = replica_health

            # Connection pool statistics
            if self.master_engine and hasattr(self.master_engine, "pool"):
                pool = self.master_engine.pool
                health_status["connections"]["pool"] = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "utilization_percent": round(
                        (pool.checkedout() / (pool.size() + pool.overflow())) * 100, 2
                    ),
                }

            # Performance statistics
            health_status["performance"] = {
                "total_queries": self.connection_stats.total_queries,
                "slow_queries": self.connection_stats.slow_queries,
                "failed_connections": self.connection_stats.failed_connections,
                "avg_query_time_ms": round(
                    self.connection_stats.avg_query_time * 1000, 2
                ),
                "slow_query_rate": round(
                    (
                        self.connection_stats.slow_queries
                        / max(self.connection_stats.total_queries, 1)
                    )
                    * 100,
                    2,
                ),
            }

            # Configuration info
            health_status["configuration"] = {
                "read_write_split_enabled": self.performance_config.enable_read_write_split,
                "read_replicas_count": len(self.read_engines),
                "pool_size": self.performance_config.pool_size,
                "max_overflow": self.performance_config.max_overflow,
                "connection_timeout": self.performance_config.connect_timeout,
            }

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            logger.error(f"Database health check failed: {e}")

        return health_status

    def get_connection_statistics(self) -> dict[str, Any]:
        """Get detailed connection statistics."""
        stats = {
            "total_connections": self.connection_stats.total_connections,
            "active_connections": self.connection_stats.active_connections,
            "idle_connections": self.connection_stats.idle_connections,
            "failed_connections": self.connection_stats.failed_connections,
            "total_queries": self.connection_stats.total_queries,
            "slow_queries": self.connection_stats.slow_queries,
            "avg_query_time": self.connection_stats.avg_query_time,
            "recent_errors": self.connection_stats.connection_errors[
                -10:
            ],  # Last 10 errors
            "performance_config": {
                "pool_size": self.performance_config.pool_size,
                "max_overflow": self.performance_config.max_overflow,
                "pool_timeout": self.performance_config.pool_timeout,
                "slow_query_threshold": self.performance_config.slow_query_threshold,
            },
        }

        if self.master_engine and hasattr(self.master_engine, "pool"):
            pool = self.master_engine.pool
            stats["pool_status"] = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

        return stats

    # ========================================================================
    # Cleanup and Shutdown
    # ========================================================================

    async def close(self) -> None:
        """Close all database connections and clean up resources."""
        try:
            # Close master engine
            if self.master_engine:
                await self.master_engine.dispose()
                logger.info("Master database engine closed")

            # Close read replica engines
            for i, read_engine in enumerate(self.read_engines):
                try:
                    await read_engine.dispose()
                    logger.info(f"Read replica {i} engine closed")
                except Exception as e:
                    logger.error(f"Error closing read replica {i}: {e}")

            logger.info("All database connections closed")

        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")


# ============================================================================
# Factory Functions and Integration
# ============================================================================


def create_production_database_manager(
    production_config: ProductionConfig, metrics_service: MetricsService | None = None
) -> ProductionDatabaseManager:
    """
    Create production database manager with optimized configuration.

    Args:
        production_config: Production configuration
        metrics_service: Optional metrics service for monitoring

    Returns:
        Configured ProductionDatabaseManager instance
    """
    # Create performance configuration from production config
    perf_config = DatabasePerformanceConfig(
        pool_size=production_config.database.pool_size,
        max_overflow=production_config.database.max_overflow,
        pool_timeout=production_config.database.connection_timeout,
        pool_recycle=production_config.database.pool_recycle,
        pool_pre_ping=production_config.database.pool_pre_ping,
        connect_timeout=production_config.database.connection_timeout,
        enable_read_write_split=production_config.database.enable_read_write_split,
        read_replica_urls=production_config.database.read_replica_urls,
        echo=production_config.database.echo,
    )

    # Get optimized database URL
    database_url = production_config.get_database_url()

    return ProductionDatabaseManager(
        database_url=database_url,
        performance_config=perf_config,
        metrics_service=metrics_service,
    )


async def initialize_production_database(
    production_config: ProductionConfig, metrics_service: MetricsService | None = None
) -> ProductionDatabaseManager:
    """
    Initialize production database with full configuration.

    Args:
        production_config: Production configuration
        metrics_service: Optional metrics service

    Returns:
        Initialized ProductionDatabaseManager instance
    """
    db_manager = create_production_database_manager(production_config, metrics_service)
    await db_manager.initialize()
    return db_manager
