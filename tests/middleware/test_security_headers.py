"""
Tests for Security Headers Middleware
Validates comprehensive security header implementation.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.middleware.security_headers import (
    CSPDirective,
    CSPSource,
    CSPViolationReport,
    Environment,
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
    create_security_txt_content,
    handle_csp_report,
    handle_ct_report,
    setup_security_headers,
)


class TestSecurityHeadersConfig:
    """Test security headers configuration."""

    def test_environment_detection(self):
        """Test environment detection from environment variables."""
        test_cases = [
            ("development", Environment.DEVELOPMENT),
            ("dev", Environment.DEVELOPMENT),
            ("testing", Environment.TESTING),
            ("test", Environment.TESTING),
            ("staging", Environment.STAGING),
            ("stage", Environment.STAGING),
            ("production", Environment.PRODUCTION),
            ("prod", Environment.PRODUCTION),
            ("unknown", Environment.DEVELOPMENT),  # Default
        ]

        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"ENVIRONMENT": env_value}):
                config = SecurityHeadersConfig()
                assert config.environment == expected

    def test_development_config(self):
        """Test development environment configuration."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = SecurityHeadersConfig()

            assert config.environment == Environment.DEVELOPMENT
            assert config.nonce_enabled is False
            assert config.csp_report_only is True
            assert config.strict_transport_security_enabled is False
            assert config.secure_cookies is False

    def test_production_config(self):
        """Test production environment configuration."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()

            assert config.environment == Environment.PRODUCTION
            assert config.nonce_enabled is True
            assert config.csp_report_only is False
            assert config.strict_transport_security_enabled is True
            assert config.secure_cookies is True
            assert config.expect_ct_enabled is True

    def test_csp_policy_development(self):
        """Test CSP policy for development environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = SecurityHeadersConfig()
            policy = config.get_csp_policy()

            # Development should allow unsafe-inline and localhost
            assert CSPSource.UNSAFE_INLINE in policy[CSPDirective.SCRIPT_SRC]
            assert CSPSource.UNSAFE_EVAL in policy[CSPDirective.SCRIPT_SRC]
            assert "http://localhost:*" in policy[CSPDirective.SCRIPT_SRC]
            assert CSPSource.SELF in policy[CSPDirective.DEFAULT_SRC]

    def test_csp_policy_production(self):
        """Test CSP policy for production environment."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            nonce = "test-nonce-123"
            policy = config.get_csp_policy(nonce)

            # Production should be strict
            assert CSPSource.NONE in policy[CSPDirective.DEFAULT_SRC]
            assert CSPSource.nonce(nonce) in policy[CSPDirective.SCRIPT_SRC]
            assert CSPSource.STRICT_DYNAMIC in policy[CSPDirective.SCRIPT_SRC]
            assert CSPSource.UNSAFE_INLINE not in policy.get(CSPDirective.SCRIPT_SRC, [])
            assert CSPSource.UNSAFE_EVAL not in policy.get(CSPDirective.SCRIPT_SRC, [])
            assert "" in policy[CSPDirective.UPGRADE_INSECURE_REQUESTS]
            assert "" in policy[CSPDirective.BLOCK_ALL_MIXED_CONTENT]

    def test_permissions_policy(self):
        """Test Permissions Policy configuration."""
        # Development environment
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = SecurityHeadersConfig()
            policy = config.get_permissions_policy()

            # Development should be permissive
            assert policy["camera"] == ["self"]
            assert policy["microphone"] == ["self"]
            assert policy["geolocation"] == ["self"]

        # Production environment
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            policy = config.get_permissions_policy()

            # Production should be restrictive
            assert policy["camera"] == []
            assert policy["microphone"] == []
            assert policy["geolocation"] == []

    def test_configuration_from_environment(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "ENVIRONMENT": "production",
            "CSP_ENABLED": "true",
            "CSP_REPORT_URI": "/custom/csp-report",
            "HSTS_MAX_AGE": "63072000",
            "HSTS_INCLUDE_SUBDOMAINS": "true",
            "HSTS_PRELOAD": "true",
            "X_FRAME_OPTIONS": "SAMEORIGIN",
            "REFERRER_POLICY": "no-referrer",
            "EXPECT_CT_MAX_AGE": "172800",
            "EXPECT_CT_ENFORCE": "true",
            "COEP": "require-corp",
            "COOP": "same-origin",
            "CORP": "same-origin",
            "COOKIE_SAMESITE": "strict",
        }

        with patch.dict(os.environ, env_vars):
            config = SecurityHeadersConfig()

            assert config.csp_enabled is True
            assert config.csp_report_uri == "/custom/csp-report"
            assert config.hsts_max_age == 63072000
            assert config.hsts_include_subdomains is True
            assert config.hsts_preload is True
            assert config.frame_options == "SAMEORIGIN"
            assert config.referrer_policy == "no-referrer"
            assert config.expect_ct_max_age == 172800
            assert config.expect_ct_enforce is True
            assert config.cross_origin_embedder_policy == "require-corp"
            assert config.cross_origin_opener_policy == "same-origin"
            assert config.cross_origin_resource_policy == "same-origin"
            assert config.cookie_samesite == "strict"


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @app.get("/api/test")
        async def api_test_endpoint():
            return {"message": "api test"}

        @app.post("/api/auth/logout")
        async def logout_endpoint():
            return {"message": "logged out"}

        return app

    def test_basic_security_headers(self, app):
        """Test that basic security headers are added."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            assert response.status_code == 200
            assert "X-Frame-Options" in response.headers
            assert "X-Content-Type-Options" in response.headers
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert "X-XSS-Protection" in response.headers
            assert response.headers["X-XSS-Protection"] == "1; mode=block"
            assert "Referrer-Policy" in response.headers

    def test_csp_header_development(self, app):
        """Test CSP header in development mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            # Development uses Report-Only mode
            assert "Content-Security-Policy-Report-Only" in response.headers
            assert "Content-Security-Policy" not in response.headers

            csp = response.headers["Content-Security-Policy-Report-Only"]
            assert "default-src 'self'" in csp
            assert "script-src" in csp
            assert "'unsafe-inline'" in csp
            assert "'unsafe-eval'" in csp

    def test_csp_header_production(self, app):
        """Test CSP header in production mode."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            # Production uses enforcing mode
            assert "Content-Security-Policy" in response.headers
            assert "Content-Security-Policy-Report-Only" not in response.headers

            csp = response.headers["Content-Security-Policy"]
            assert "default-src 'none'" in csp
            assert "upgrade-insecure-requests" in csp
            assert "block-all-mixed-content" in csp

    def test_hsts_header_production(self, app):
        """Test HSTS header in production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "HSTS_PRELOAD": "true"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            assert "Strict-Transport-Security" in response.headers
            hsts = response.headers["Strict-Transport-Security"]
            assert "max-age=31536000" in hsts
            assert "includeSubDomains" in hsts
            assert "preload" in hsts

    def test_no_hsts_development(self, app):
        """Test that HSTS is not added in development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            assert "Strict-Transport-Security" not in response.headers

    def test_permissions_policy_header(self, app):
        """Test Permissions-Policy header."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            assert "Permissions-Policy" in response.headers
            policy = response.headers["Permissions-Policy"]
            assert "camera=()" in policy
            assert "microphone=()" in policy
            assert "geolocation=()" in policy

    def test_cross_origin_headers(self, app):
        """Test Cross-Origin headers."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            assert "Cross-Origin-Embedder-Policy" in response.headers
            assert "Cross-Origin-Opener-Policy" in response.headers
            assert "Cross-Origin-Resource-Policy" in response.headers

    def test_clear_site_data_logout(self, app):
        """Test Clear-Site-Data header on logout."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.post("/api/auth/logout")

            assert "Clear-Site-Data" in response.headers
            assert response.headers["Clear-Site-Data"] == '"cache", "cookies", "storage"'

    def test_api_specific_headers(self, app):
        """Test API-specific headers."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/api/test")

            assert "X-API-Version" in response.headers
            assert response.headers["X-API-Version"] == "2.0.0"
            assert "X-Request-ID" in response.headers

    def test_nonce_generation(self, app):
        """Test CSP nonce generation."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)

            # Make multiple requests
            response1 = client.get("/test")
            response2 = client.get("/test")

            csp1 = response1.headers["Content-Security-Policy"]
            csp2 = response2.headers["Content-Security-Policy"]

            # Extract nonces
            import re
            nonce_pattern = r"'nonce-([^']+)'"
            nonce1_match = re.search(nonce_pattern, csp1)
            nonce2_match = re.search(nonce_pattern, csp2)

            # Nonces should be present and different
            assert nonce1_match is not None
            assert nonce2_match is not None
            assert nonce1_match.group(1) != nonce2_match.group(1)

    def test_expect_ct_header(self, app):
        """Test Expect-CT header in production."""
        env_vars = {
            "ENVIRONMENT": "production",
            "EXPECT_CT_ENFORCE": "true",
            "EXPECT_CT_MAX_AGE": "172800",
        }

        with patch.dict(os.environ, env_vars):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            assert "Expect-CT" in response.headers
            expect_ct = response.headers["Expect-CT"]
            assert "max-age=172800" in expect_ct
            assert "enforce" in expect_ct
            assert "report-uri=" in expect_ct

    def test_report_to_header(self, app):
        """Test Report-To header for reporting API."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            app.add_middleware(SecurityHeadersMiddleware, config=config)

            client = TestClient(app)
            response = client.get("/test")

            assert "Report-To" in response.headers
            report_to = json.loads(response.headers["Report-To"])

            assert isinstance(report_to, list)
            assert len(report_to) > 0
            assert report_to[0]["group"] == "csp-endpoint"
            assert report_to[0]["max_age"] == 86400
            assert report_to[0]["endpoints"][0]["url"] == "/api/security/csp-report"


class TestCSPViolationReport:
    """Test CSP violation report handling."""

    def test_add_report(self):
        """Test adding CSP violation reports."""
        handler = CSPViolationReport(max_reports=10)

        report = {
            "blocked-uri": "https://evil.com/script.js",
            "violated-directive": "script-src",
            "document-uri": "https://example.com/page",
            "source-file": "https://example.com/app.js",
            "line-number": 42,
        }

        handler.add_report(report)

        assert len(handler.reports) == 1
        assert handler.reports[0]["blocked-uri"] == "https://evil.com/script.js"
        assert "timestamp" in handler.reports[0]
        assert handler.reports[0]["count"] == 1

    def test_report_deduplication(self):
        """Test that duplicate reports are counted."""
        handler = CSPViolationReport()

        report = {
            "blocked-uri": "https://evil.com/script.js",
            "violated-directive": "script-src",
            "document-uri": "https://example.com/page",
        }

        # Add the same report multiple times
        for _ in range(5):
            handler.add_report(report.copy())

        key = "https://example.com/page|script-src|https://evil.com/script.js"
        assert handler.report_counts[key] == 5

    def test_max_reports_limit(self):
        """Test that reports are limited to max_reports."""
        handler = CSPViolationReport(max_reports=5)

        for i in range(10):
            handler.add_report({
                "blocked-uri": f"https://evil{i}.com",
                "violated-directive": "script-src",
                "document-uri": "https://example.com/page",
            })

        assert len(handler.reports) == 5
        # Should keep the most recent reports
        assert "evil9.com" in handler.reports[-1]["blocked-uri"]

    def test_get_summary(self):
        """Test getting violation summary."""
        handler = CSPViolationReport()

        # Add various reports
        for i in range(3):
            handler.add_report({
                "blocked-uri": "https://evil1.com",
                "violated-directive": "script-src",
                "document-uri": "https://example.com/page1",
            })

        for i in range(2):
            handler.add_report({
                "blocked-uri": "https://evil2.com",
                "violated-directive": "style-src",
                "document-uri": "https://example.com/page2",
            })

        summary = handler.get_summary()

        assert summary["total_reports"] == 5
        assert summary["unique_violations"] == 2
        assert len(summary["top_violations"]) == 2

        # Check that violations are sorted by count
        assert summary["top_violations"][0]["count"] == 3
        assert summary["top_violations"][1]["count"] == 2

    def test_empty_summary(self):
        """Test summary with no reports."""
        handler = CSPViolationReport()
        summary = handler.get_summary()

        assert summary["total_reports"] == 0
        assert summary["unique_violations"] == 0
        assert summary["top_violations"] == []


class TestCSPReportEndpoints:
    """Test CSP report collection endpoints."""

    @pytest.mark.asyncio
    async def test_handle_csp_report(self):
        """Test handling CSP violation reports."""
        request = MagicMock(spec=Request)

        report_data = {
            "csp-report": {
                "blocked-uri": "https://evil.com/script.js",
                "violated-directive": "script-src",
                "document-uri": "https://example.com/page",
            }
        }

        async def mock_body():
            return json.dumps(report_data).encode()

        request.body = mock_body

        response = await handle_csp_report(request)

        assert response.status_code == 204
        assert response.body is None

    @pytest.mark.asyncio
    async def test_handle_invalid_csp_report(self):
        """Test handling invalid CSP reports."""
        request = MagicMock(spec=Request)

        async def mock_body():
            return b"invalid json"

        request.body = mock_body

        response = await handle_csp_report(request)

        assert response.status_code == 400
        body = json.loads(response.body)
        assert body["error"] == "Invalid CSP report"

    @pytest.mark.asyncio
    async def test_handle_ct_report(self):
        """Test handling Certificate Transparency reports."""
        request = MagicMock(spec=Request)

        report_data = {
            "hostname": "example.com",
            "port": 443,
            "effective-expiration-date": "2024-12-31T23:59:59Z",
        }

        async def mock_body():
            return json.dumps(report_data).encode()

        request.body = mock_body

        response = await handle_ct_report(request)

        assert response.status_code == 204
        assert response.body is None


class TestSecurityTxt:
    """Test security.txt content generation."""

    def test_create_security_txt_content(self):
        """Test security.txt content creation."""
        content = create_security_txt_content()

        assert "# Security Policy" in content
        assert "Contact: mailto:security@example.com" in content
        assert "Expires:" in content
        assert "Encryption:" in content
        assert "Preferred-Languages: en, zh" in content
        assert "Policy:" in content

        # Check RFC compliance
        assert "# This security.txt file is compliant with RFC 9116" in content


class TestSetupSecurityHeaders:
    """Test setup_security_headers function."""

    def test_setup_security_headers(self):
        """Test setting up security headers on FastAPI app."""
        app = FastAPI()

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = SecurityHeadersConfig()
            setup_security_headers(app, config)

            client = TestClient(app)

            # Test CSP report endpoint
            response = client.post(
                "/api/security/csp-report",
                json={"csp-report": {"blocked-uri": "test"}},
            )
            assert response.status_code == 204

            # Test CT report endpoint
            response = client.post(
                "/api/security/ct-report",
                json={"hostname": "example.com"},
            )
            assert response.status_code == 204

            # Test security.txt endpoint
            response = client.get("/.well-known/security.txt")
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/plain; charset=utf-8"
            assert "Contact:" in response.text

            # Test CSP violations summary endpoint
            response = client.get("/api/admin/security/csp-violations")
            assert response.status_code == 200
            data = response.json()
            assert "total_reports" in data
            assert "unique_violations" in data


class TestEnvironmentSpecificBehavior:
    """Test environment-specific security behavior."""

    @pytest.fixture
    def create_app_with_env(self):
        """Factory to create app with specific environment."""
        def _create(env: str):
            app = FastAPI()

            @app.get("/test")
            async def test_endpoint():
                return {"message": "test"}

            with patch.dict(os.environ, {"ENVIRONMENT": env}):
                config = SecurityHeadersConfig()
                app.add_middleware(SecurityHeadersMiddleware, config=config)

            return app, TestClient(app)

        return _create

    def test_development_relaxed_security(self, create_app_with_env):
        """Test relaxed security in development."""
        app, client = create_app_with_env("development")
        response = client.get("/test")

        # No HSTS in development
        assert "Strict-Transport-Security" not in response.headers

        # CSP is report-only
        assert "Content-Security-Policy-Report-Only" in response.headers
        assert "Content-Security-Policy" not in response.headers

        # CSP allows unsafe practices
        csp = response.headers["Content-Security-Policy-Report-Only"]
        assert "'unsafe-inline'" in csp
        assert "'unsafe-eval'" in csp

    def test_staging_moderate_security(self, create_app_with_env):
        """Test moderate security in staging."""
        app, client = create_app_with_env("staging")
        response = client.get("/test")

        # HSTS enabled in staging
        assert "Strict-Transport-Security" in response.headers

        # CSP is report-only for testing
        assert "Content-Security-Policy-Report-Only" in response.headers

        # CSP is stricter than development
        csp = response.headers["Content-Security-Policy-Report-Only"]
        assert "default-src 'none'" in csp
        assert "upgrade-insecure-requests" in csp

    def test_production_strict_security(self, create_app_with_env):
        """Test strict security in production."""
        app, client = create_app_with_env("production")
        response = client.get("/test")

        # HSTS enabled
        assert "Strict-Transport-Security" in response.headers

        # CSP is enforcing
        assert "Content-Security-Policy" in response.headers
        assert "Content-Security-Policy-Report-Only" not in response.headers

        # Strict CSP
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp
        assert "upgrade-insecure-requests" in csp
        assert "block-all-mixed-content" in csp

        # All security headers present
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers
        assert "Cross-Origin-Embedder-Policy" in response.headers
        assert "Cross-Origin-Opener-Policy" in response.headers
        assert "Cross-Origin-Resource-Policy" in response.headers
