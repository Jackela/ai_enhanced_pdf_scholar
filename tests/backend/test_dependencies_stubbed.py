import types

import pytest

import backend.api.dependencies as deps


@pytest.fixture(autouse=True)
def isolate_singleton_state():
    """Save and restore global singleton state to prevent test pollution in parallel runs."""
    # Save original state
    original_db = deps._db_connection
    original_rag = deps._enhanced_rag_service
    original_library_ctrl = deps._library_controller

    # Reset for test isolation
    deps._db_connection = None
    deps._enhanced_rag_service = None
    deps._library_controller = None

    yield

    # Restore original state
    deps._db_connection = original_db
    deps._enhanced_rag_service = original_rag
    deps._library_controller = original_library_ctrl


class _DummyDB(types.SimpleNamespace):
    def close_all_connections(self):
        self.closed = True


def test_get_db_generator(monkeypatch):
    dummy_db = _DummyDB()

    class _DBConn:
        @staticmethod
        def get_instance(path):
            return dummy_db

        def __init__(self, path, enable_monitoring=False):
            pass

    monkeypatch.setattr(deps, "DatabaseConnection", _DBConn)
    db = deps.get_db()
    assert db is dummy_db


def test_get_enhanced_rag_stub(monkeypatch):
    enhanced = types.SimpleNamespace()
    monkeypatch.setattr(deps.Config, "get_gemini_api_key", staticmethod(lambda: "key"))

    def _enhanced(db_connection=None, api_key=None, **kwargs):
        return enhanced

    monkeypatch.setattr(deps, "EnhancedRAGService", _enhanced)
    result = deps.get_enhanced_rag(db=None)
    assert result is enhanced


def test_get_library_controller_stub(monkeypatch):
    ctrl = types.SimpleNamespace()
    monkeypatch.setattr(deps, "LibraryController", lambda *_args, **_k: ctrl)
    result = deps.get_library_controller(db=None, enhanced_rag=None)
    assert result is ctrl
