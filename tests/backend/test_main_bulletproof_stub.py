import types

from fastapi.testclient import TestClient


def test_main_bulletproof_basic(monkeypatch):
    # Stub dependencies used in main_bulletproof
    dummy_metrics = types.SimpleNamespace(
        metrics_service=types.SimpleNamespace(
            record_http_request=lambda *_, **__: None,
            record_http_response=lambda *_, **__: None,
            record_path_safety_violation=lambda *_, **__: None,
        ),
    )
    monkeypatch.setattr(
        "backend.services.metrics_collector.get_metrics_collector",
        lambda: dummy_metrics,
    )
    monkeypatch.setattr("backend.api.dependencies.get_db", lambda: iter([None]))
    monkeypatch.setattr(
        "backend.api.dependencies.get_enhanced_rag", lambda db=None: None
    )
    monkeypatch.setattr(
        "backend.api.dependencies.get_library_controller",
        lambda db=None, rag=None: types.SimpleNamespace(
            query_document=lambda *_: {"answer": "stub"}
        ),
    )

    from backend.api import main_bulletproof

    client = TestClient(main_bulletproof.app)
    assert client.get("/ping").status_code == 200
    assert client.get("/health").status_code == 200
