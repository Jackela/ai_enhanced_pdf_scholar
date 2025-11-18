import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.security_headers import (
    Environment,
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
)


def _client_with_config(config: SecurityHeadersConfig) -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, config=config)

    @app.get("/test")
    async def test():
        return {"ok": True}

    return TestClient(app)


def test_report_only_mode_headers():
    cfg = SecurityHeadersConfig(environment=Environment.DEVELOPMENT)
    cfg.csp_enabled = True
    cfg.csp_report_only = True
    client = _client_with_config(cfg)

    res = client.get("/test")
    assert res.status_code == 200
    assert "Content-Security-Policy-Report-Only" in res.headers
    assert "Content-Security-Policy" not in res.headers


def test_reporting_disabled():
    cfg = SecurityHeadersConfig(environment=Environment.TESTING)
    cfg.enable_reporting = False
    client = _client_with_config(cfg)
    res = client.get("/test")
    assert res.status_code == 200
    assert "Report-To" not in res.headers


def test_hsts_disabled_in_dev():
    cfg = SecurityHeadersConfig(environment=Environment.DEVELOPMENT)
    client = _client_with_config(cfg)
    res = client.get("/test")
    assert "Strict-Transport-Security" not in res.headers
