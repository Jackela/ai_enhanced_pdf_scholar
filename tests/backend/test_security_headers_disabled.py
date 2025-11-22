from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.security_headers import (
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
)


def test_security_headers_disabled_csp():
    cfg = SecurityHeadersConfig()
    cfg.csp_enabled = False
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, config=cfg)

    @app.get("/x")
    async def x():
        return {"ok": True}

    res = TestClient(app).get("/x")
    assert res.status_code == 200
    assert "Content-Security-Policy" not in res.headers
