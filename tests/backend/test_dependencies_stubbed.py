import types
from contextlib import contextmanager

import backend.api.dependencies as deps


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
    deps._db_connection = None  # reset singleton


def test_get_enhanced_rag_stub(monkeypatch):
    enhanced = types.SimpleNamespace()
    monkeypatch.setattr(deps.Config, "get_gemini_api_key", staticmethod(lambda: "key"))

    def _enhanced(db_connection=None, api_key=None, **kwargs):
        return enhanced

    monkeypatch.setattr(deps, "EnhancedRAGService", _enhanced)
    deps._enhanced_rag_service = None
    result = deps.get_enhanced_rag(db=None)
    assert result is enhanced


def test_get_library_controller_stub(monkeypatch):
    ctrl = types.SimpleNamespace()
    monkeypatch.setattr(deps, "LibraryController", lambda *_args, **_k: ctrl)
    result = deps.get_library_controller(db=None, enhanced_rag=None)
    assert result is ctrl
