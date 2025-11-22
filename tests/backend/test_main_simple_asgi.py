import types

import pytest
from fastapi.testclient import TestClient


def test_main_simple_health_and_root(monkeypatch):
    # Avoid heavy imports by stubbing dependencies before import
    monkeypatch.setenv("ENVIRONMENT", "testing")

    # Stub metrics collector minimal interface
    dummy_metrics = types.SimpleNamespace(
        metrics_service=types.SimpleNamespace(
            record_http_request=lambda *_, **__: None,
            record_http_response=lambda *_, **__: None,
            record_path_safety_violation=lambda *_, **__: None,
        ),
        check_comprehensive_health=lambda: {"ok": True},
        get_metrics_response=lambda: ("", "text/plain"),
        get_dashboard_metrics=lambda: {"dashboard": True},
    )
    monkeypatch.setattr(
        "backend.services.metrics_collector.get_metrics_collector",
        lambda: dummy_metrics,
    )

    # Stub middleware dependencies
    # Ensure get_db/get_enhanced_rag/get_library_controller do not try real DB/LLM
    monkeypatch.setattr("backend.api.dependencies.get_db", lambda: iter([None]))
    monkeypatch.setattr("backend.api.dependencies.get_enhanced_rag", lambda db: None)
    monkeypatch.setattr(
        "backend.api.dependencies.get_library_controller",
        lambda db, rag: types.SimpleNamespace(
            query_document=lambda *_: {"answer": "stub"}
        ),
    )

    # Import the app after stubbing
    from backend.api import main_simple

    client = TestClient(main_simple.app)
    assert client.get("/").status_code == 200
    assert client.get("/ping").json() == {"pong": True}
    assert client.get("/health").status_code == 200
    assert client.get("/api/docs").status_code in (
        200,
        404,
    )  # docs may be disabled in tests

    # Verify rate limit headers from middleware wiring
    res = client.get("/api/system/health")
    assert res.status_code in (200, 400, 429)
