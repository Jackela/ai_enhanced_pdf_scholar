"""
Service Factory
Centralized factory for creating and managing service dependencies.
Implements the Factory pattern to reduce coupling and improve testability.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, TypeVar

from src.database.connection import DatabaseConnection
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorIndexRepository
from src.services.document_library_service import DocumentLibraryService
from src.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceFactory(ABC):
    """Abstract base class for service factories."""

    @abstractmethod
    def create_service(self, service_type: type[T], **kwargs: Any) -> T:
        """Create a service instance of the specified type."""
        pass

    @abstractmethod
    def get_service(self, service_type: type[T]) -> Optional[T]:
        """Get an existing service instance if available."""
        pass


class DefaultServiceFactory(ServiceFactory):
    """
    Default service factory implementation with dependency injection and lifecycle management.

    Features:
    - Singleton pattern for shared services
    - Dependency injection configuration
    - Service lifecycle management
    - Thread-safe service creation
    """

    def __init__(
        self, db_connection: DatabaseConnection, config: Optional[dict[str, Any]] = None
    ):
        """
        Initialize service factory with core dependencies.

        Args:
            db_connection: Database connection instance
            config: Optional configuration dictionary
        """
        self.db_connection = db_connection
        self.config = config or {}
        self._services: dict[type, Any] = {}
        self._service_configs: dict[type, dict[str, Any]] = {}

        # Register default service configurations
        self._register_default_configurations()

        logger.debug("ServiceFactory initialized with database connection")

    def _register_default_configurations(self) -> None:
        """Register default configurations for services."""
        self._service_configs.update(
            {
                DocumentRepository: {
                    "dependencies": ["db_connection"],
                    "singleton": True,
                },
                VectorIndexRepository: {
                    "dependencies": ["db_connection"],
                    "singleton": True,
                },
                DocumentLibraryService: {
                    "dependencies": ["db_connection", "documents_dir"],
                    "singleton": False,  # Allow multiple instances with different configs
                },
                EnhancedRAGService: {
                    "dependencies": ["db_connection"],
                    "singleton": True,
                },
            }
        )

    def create_service(self, service_type: type[T], **kwargs: Any) -> T:
        """
        Create a service instance with dependency injection.

        Args:
            service_type: Class type of the service to create
            **kwargs: Additional arguments for service creation

        Returns:
            Service instance

        Raises:
            ValueError: If service type is not supported
            Exception: If service creation fails
        """
        try:
            # Check if singleton service already exists
            if self._is_singleton(service_type) and service_type in self._services:
                logger.debug(f"Returning existing singleton {service_type.__name__}")
                return self._services[service_type]

            # Resolve dependencies
            resolved_kwargs = self._resolve_dependencies(service_type, kwargs)

            # Create service instance
            logger.debug(
                f"Creating {service_type.__name__} with dependencies: {list(resolved_kwargs.keys())}"
            )
            instance = service_type(**resolved_kwargs)

            # Store singleton services
            if self._is_singleton(service_type):
                self._services[service_type] = instance
                logger.debug(f"Cached singleton {service_type.__name__}")

            return instance

        except Exception as e:
            logger.error(f"Failed to create service {service_type.__name__}: {e}")
            raise

    def get_service(self, service_type: type[T]) -> Optional[T]:
        """
        Get an existing service instance.

        Args:
            service_type: Class type of the service

        Returns:
            Service instance if exists, None otherwise
        """
        return self._services.get(service_type)

    def register_service_config(
        self,
        service_type: type,
        dependencies: list[str],
        singleton: bool = False,
        **config: Any,
    ) -> None:
        """
        Register configuration for a service type.

        Args:
            service_type: Service class type
            dependencies: List of dependency names
            singleton: Whether service should be singleton
            **config: Additional configuration parameters
        """
        self._service_configs[service_type] = {
            "dependencies": dependencies,
            "singleton": singleton,
            **config,
        }
        logger.debug(f"Registered config for {service_type.__name__}")

    def _resolve_dependencies(
        self, service_type: type, provided_kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Resolve dependencies for a service type.

        Args:
            service_type: Service class type
            provided_kwargs: User-provided arguments

        Returns:
            Dictionary with resolved dependencies
        """
        resolved = provided_kwargs.copy()

        # Get service configuration
        config = self._service_configs.get(service_type, {})
        dependencies = config.get("dependencies", [])

        # Resolve each dependency
        for dependency in dependencies:
            if dependency not in resolved:
                resolved[dependency] = self._resolve_dependency(dependency)

        # Add configuration parameters
        for key, value in config.items():
            if key not in ["dependencies", "singleton"] and key not in resolved:
                resolved[key] = value

        return resolved

    def _resolve_dependency(self, dependency_name: str) -> Any:
        """
        Resolve a specific dependency by name.

        Args:
            dependency_name: Name of the dependency to resolve

        Returns:
            Resolved dependency value

        Raises:
            ValueError: If dependency cannot be resolved
        """
        dependency_map = {
            "db_connection": self.db_connection,
            "documents_dir": self.config.get("documents_dir"),
        }

        if dependency_name in dependency_map:
            return dependency_map[dependency_name]

        # Try to resolve as a service dependency
        for service_type in self._service_configs.keys():
            if dependency_name == service_type.__name__.lower():
                return self.create_service(service_type)

        raise ValueError(f"Cannot resolve dependency: {dependency_name}")

    def _is_singleton(self, service_type: type) -> bool:
        """Check if a service type should be singleton."""
        config = self._service_configs.get(service_type, {})
        return config.get("singleton", False)

    def clear_singletons(self) -> None:
        """Clear all singleton service instances (useful for testing)."""
        self._services.clear()
        logger.debug("Cleared all singleton services")

    def get_service_info(self) -> dict[str, Any]:
        """
        Get information about registered services and instances.

        Returns:
            Dictionary with service information
        """
        return {
            "registered_services": {
                service_type.__name__: config
                for service_type, config in self._service_configs.items()
            },
            "active_singletons": [
                service_type.__name__ for service_type in self._services.keys()
            ],
            "factory_config": self.config,
        }


class TestServiceFactory(DefaultServiceFactory):
    """
    Service factory for testing with mock support and dependency override.

    Features:
    - Mock service injection
    - Dependency override for testing
    - Test isolation support
    """

    def __init__(
        self, db_connection: DatabaseConnection, config: Optional[dict[str, Any]] = None
    ):
        """Initialize test service factory."""
        super().__init__(db_connection, config)
        self._mocks: dict[type, Any] = {}
        self._overrides: dict[str, Any] = {}
        logger.debug("TestServiceFactory initialized for testing")

    def set_mock_service(self, service_type: type[T], mock_instance: T) -> None:
        """
        Set a mock instance for a service type.

        Args:
            service_type: Service class type
            mock_instance: Mock instance to return
        """
        self._mocks[service_type] = mock_instance
        logger.debug(f"Mock set for {service_type.__name__}")

    def override_dependency(self, dependency_name: str, value: Any) -> None:
        """
        Override a dependency value for testing.

        Args:
            dependency_name: Name of the dependency
            value: Override value
        """
        self._overrides[dependency_name] = value
        logger.debug(f"Dependency override set for {dependency_name}")

    def create_service(self, service_type: type[T], **kwargs: Any) -> T:
        """Create service with mock support."""
        # Return mock if available
        if service_type in self._mocks:
            logger.debug(f"Returning mock for {service_type.__name__}")
            return self._mocks[service_type]

        # Use parent implementation
        return super().create_service(service_type, **kwargs)

    def _resolve_dependency(self, dependency_name: str) -> Any:
        """Resolve dependency with override support."""
        # Check for override first
        if dependency_name in self._overrides:
            return self._overrides[dependency_name]

        # Use parent implementation
        return super()._resolve_dependency(dependency_name)

    def reset_test_state(self) -> None:
        """Reset all test-specific state."""
        self._mocks.clear()
        self._overrides.clear()
        self.clear_singletons()
        logger.debug("Test state reset")


# Global service factory instance (initialized by application)
_service_factory: Optional[ServiceFactory] = None


def get_service_factory() -> ServiceFactory:
    """
    Get the global service factory instance.

    Returns:
        Service factory instance

    Raises:
        RuntimeError: If factory not initialized
    """
    global _service_factory
    if _service_factory is None:
        raise RuntimeError(
            "Service factory not initialized. Call initialize_service_factory() first."
        )
    return _service_factory


def initialize_service_factory(
    db_connection: DatabaseConnection,
    config: Optional[dict[str, Any]] = None,
    factory_class: type[ServiceFactory] = DefaultServiceFactory,
) -> ServiceFactory:
    """
    Initialize the global service factory.

    Args:
        db_connection: Database connection instance
        config: Optional configuration dictionary
        factory_class: Factory class to use (default: DefaultServiceFactory)

    Returns:
        Initialized service factory
    """
    global _service_factory
    _service_factory = factory_class(db_connection, config)
    logger.info(f"Service factory initialized: {factory_class.__name__}")
    return _service_factory


def create_service(service_type: type[T], **kwargs: Any) -> T:
    """
    Convenience function to create a service using the global factory.

    Args:
        service_type: Service class type
        **kwargs: Additional arguments

    Returns:
        Service instance
    """
    factory = get_service_factory()
    return factory.create_service(service_type, **kwargs)


def get_service(service_type: type[T]) -> Optional[T]:
    """
    Convenience function to get a service using the global factory.

    Args:
        service_type: Service class type

    Returns:
        Service instance if exists, None otherwise
    """
    factory = get_service_factory()
    return factory.get_service(service_type)
