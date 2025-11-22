import types

import pytest

from src.services.service_factory import (
    DefaultServiceFactory,
    ServiceFactory,
    TestServiceFactory,
    create_service,
    get_service_factory,
    initialize_service_factory,
)


class _DummyDB:
    def __init__(self):
        self.closed = False

    def close_all_connections(self):
        self.closed = True


class _DummyService:
    def __init__(self, db_connection, extra=None):
        self.db = db_connection
        self.extra = extra


def test_default_factory_singleton_and_dependencies(monkeypatch):
    dummy_db = _DummyDB()
    factory = DefaultServiceFactory(dummy_db, config={"documents_dir": "/tmp/docs"})

    # Register a simple service with dependencies and singleton behavior
    factory.register_service_config(
        _DummyService, dependencies=["db_connection"], singleton=True, extra="cfg"
    )

    instance_a = factory.create_service(_DummyService)
    instance_b = factory.create_service(_DummyService)

    assert instance_a is instance_b  # singleton cached
    assert instance_a.db is dummy_db
    assert instance_a.extra == "cfg"

    # Non-singleton: override and ensure new instance
    factory.register_service_config(
        _DummyService, dependencies=["db_connection"], singleton=False, extra="other"
    )
    instance_c = factory.create_service(_DummyService)
    assert instance_c is not instance_a
    assert instance_c.extra == "other"


def test_test_factory_mocks_and_overrides():
    dummy_db = _DummyDB()
    factory = TestServiceFactory(dummy_db, config={"documents_dir": "/tmp/docs"})
    factory.register_service_config(
        _DummyService, dependencies=["db_connection"], singleton=True, extra="cfg"
    )

    mock_service = _DummyService(db_connection="mock-db", extra="mock")
    factory.set_mock_service(_DummyService, mock_service)

    result = factory.create_service(_DummyService)
    assert result is mock_service

    factory.override_dependency("db_connection", "override-db")
    factory.register_service_config(
        _DummyService, dependencies=["db_connection"], singleton=False, extra=None
    )
    factory._mocks.pop(_DummyService)  # remove mock so override path is exercised
    result_override = factory.create_service(_DummyService)
    assert result_override.db == "override-db"

    factory.reset_test_state()
    assert factory.get_service(_DummyService) is None


def test_global_factory_lifecycle(monkeypatch):
    dummy_db = _DummyDB()
    monkeypatch.setattr(
        "src.services.service_factory._service_factory", None, raising=False
    )

    initialize_service_factory(dummy_db, config={"documents_dir": "/tmp"})
    factory = get_service_factory()
    assert isinstance(factory, ServiceFactory)

    factory.register_service_config(
        _DummyService, dependencies=["db_connection"], singleton=True, extra=None
    )
    created = create_service(_DummyService)
    assert created.db is dummy_db

    # Clean up global
    monkeypatch.setattr(
        "src.services.service_factory._service_factory", None, raising=False
    )
