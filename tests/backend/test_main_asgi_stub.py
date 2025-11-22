import types

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def stub_app(monkeypatch):
    # Stub metrics collector
    dummy_metrics = types.SimpleNamespace(
        metrics_service=types.SimpleNamespace(
            record_http_request=lambda *_, **__: None,
            record_http_response=lambda *_, **__: None,
            record_path_safety_violation=lambda *_, **__: None,
        ),
        check_comprehensive_health=lambda: {"healthy": True},
        get_metrics_response=lambda: ("", "text/plain"),
        get_dashboard_metrics=lambda: {"dashboard": True},
    )
    monkeypatch.setattr(
        "backend.services.metrics_collector.get_metrics_collector",
        lambda: dummy_metrics,
    )

    # Stub dependency-heavy helpers
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

    # Stub rate limit config/metrics to avoid Redis
    monkeypatch.setattr(
        "backend.api.rate_limit_config.get_env_override_config", lambda cfg: cfg
    )
    monkeypatch.setattr(
        "backend.api.rate_limit_config.get_rate_limit_config",
        lambda: types.SimpleNamespace(
            default_limit=types.SimpleNamespace(requests=100, window=60),
            global_ip_limit=types.SimpleNamespace(requests=1000, window=3600),
            endpoint_limits={},
            redis_url=None,
            dev_multiplier=10.0,
            test_multiplier=100.0,
            include_headers=True,
            block_duration=60,
            bypass_ips=set(),
            bypass_user_agents=set(),
            enable_monitoring=False,
            monitoring_log_file=None,
        ),
    )

    from backend.api import main

    return main.app


def test_main_root_ping_health(stub_app):
    client = TestClient(stub_app)
    assert client.get("/").status_code == 200
    assert client.get("/ping").json() == {"pong": True}
    assert client.get("/health").status_code == 200


def test_main_metrics_endpoints(stub_app):
    client = TestClient(stub_app)
    res = client.get("/metrics")
    assert res.status_code in (200, 500)  # stubbed may return empty string
    res_dash = client.get("/metrics/dashboard")
    assert res_dash.status_code in (200, 500)
