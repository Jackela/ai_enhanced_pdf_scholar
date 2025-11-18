import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.security_headers import (
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
)


def test_expect_ct_header_enabled():
    cfg = SecurityHeadersConfig(
        environment=(
            SecurityHeadersConfig.Environment.PRODUCTION
            if hasattr(SecurityHeadersConfig, "Environment")
            else None
        )
    )
    cfg.expect_ct_enabled = True
    cfg.expect_ct_max_age = 123
    cfg.expect_ct_enforce = True
    cfg.expect_ct_report_uri = "/ct-report"
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, config=cfg)

    @app.get("/ct")
    async def ct():
        return {"ok": True}

    res = TestClient(app).get("/ct")
    assert "Expect-CT" in res.headers


def test_report_to_header_present_with_reporting_enabled():
    cfg = SecurityHeadersConfig()
    cfg.enable_reporting = True
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, config=cfg)

    @app.get("/rt")
    async def rt():
        return {"ok": True}

    res = TestClient(app).get("/rt")
    assert "Report-To" in res.headers
