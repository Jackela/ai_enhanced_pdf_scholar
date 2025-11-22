import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.middleware.security_headers import (
    CSPViolationReport,
    Environment,
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
    handle_csp_report,
    handle_ct_report,
    setup_security_headers,
)


def _build_app(env: Environment = Environment.PRODUCTION) -> TestClient:
    app = FastAPI()
    config = SecurityHeadersConfig(environment=env)
    setup_security_headers(app, config)

    @app.get("/api/test")
    async def test_endpoint():
        return {"ok": True}

    return TestClient(app)


def test_security_headers_added_for_api_route():
    client = _build_app(Environment.PRODUCTION)
    response = client.get("/api/test")

    # Core headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-XSS-Protection"].startswith("1;")
    assert response.headers["X-API-Version"] == "2.0.0"
    # CSP enforcing mode in production
    assert "Content-Security-Policy" in response.headers
    # HSTS present in production mode
    assert "Strict-Transport-Security" in response.headers
    # Reporting enabled by default
    assert "Report-To" in response.headers


def test_security_txt_endpoint_and_headers():
    client = _build_app(Environment.PRODUCTION)
    response = client.get("/.well-known/security.txt")

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") == "max-age=86400"
    assert "Contact:" in response.text


def test_csp_violation_report_handler(monkeypatch):
    report_handler = CSPViolationReport(max_reports=2)
    # Replace global handler in module for isolation
    monkeypatch.setattr(
        "backend.api.middleware.security_headers.csp_violation_handler",
        report_handler,
        raising=True,
    )
    client = _build_app(Environment.TESTING)

    payload = {
        "csp-report": {
            "document-uri": "https://app",
            "violated-directive": "script-src",
            "blocked-uri": "https://bad",
        }
    }
    res = client.post("/api/security/csp-report", json=payload)
    assert res.status_code == 204
    summary = report_handler.get_summary()
    assert summary["total_reports"] == 1
    assert summary["unique_violations"] == 1


def test_ct_report_handler():
    client = _build_app(Environment.TESTING)
    payload = {"sct": "bad-proof"}
    res = client.post("/api/security/ct-report", json=payload)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_handle_csp_report_direct():
    class DummyRequest:
        def __init__(self, body_bytes: bytes):
            self._body = body_bytes

        async def body(self):
            return self._body

        @property
        def url(self):
            class DummyURL:
                path = "/api/security/csp-report"

            return DummyURL()

    request = DummyRequest(json.dumps({"csp-report": {"document-uri": "x"}}).encode())
    response = await handle_csp_report(request)  # type: ignore[arg-type]
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_handle_ct_report_direct():
    class DummyRequest:
        def __init__(self, body_bytes: bytes):
            self._body = body_bytes

        async def body(self):
            return self._body

        @property
        def url(self):
            class DummyURL:
                path = "/api/security/ct-report"

            return DummyURL()

    request = DummyRequest(json.dumps({"ct": "bad"}).encode())
    response = await handle_ct_report(request)  # type: ignore[arg-type]
    assert response.status_code == 204


def test_nonce_added_when_enabled():
    # Ensure nonce creation path is exercised
    app = FastAPI()
    config = SecurityHeadersConfig(environment=Environment.PRODUCTION)
    app.add_middleware(SecurityHeadersMiddleware, config=config)

    @app.get("/api/nonce-test")
    async def endpoint(request: Request):
        # The middleware injects csp_nonce into request.state
        return {"nonce": getattr(request.state, "csp_nonce", None)}

    client = TestClient(app)
    res = client.get("/api/nonce-test")
    assert res.status_code == 200
    assert res.json()["nonce"]
    assert "Content-Security-Policy" in res.headers
