"""
CORS Security Tests

Comprehensive tests for CORS security configuration and enforcement.
Validates that CORS policies are properly configured and enforced across different environments.
"""

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.api.cors_config import (
    CORSConfig,
    Environment,
    get_cors_config,
    get_safe_cors_origins,
    validate_origin_format,
)


class TestCORSConfig:
    """Test CORS configuration module."""

    def test_detect_environment_development(self):
        """Test environment detection for development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = CORSConfig()
            assert config.environment == Environment.DEVELOPMENT

    def test_detect_environment_production(self):
        """Test environment detection for production."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            config = CORSConfig()
            assert config.environment == Environment.PRODUCTION

    def test_detect_environment_aliases(self):
        """Test environment detection with common aliases."""
        aliases = {
            "dev": Environment.DEVELOPMENT,
            "test": Environment.TESTING,
            "stage": Environment.STAGING,
            "prod": Environment.PRODUCTION,
        }

        for alias, expected in aliases.items():
            env_vars = {"ENVIRONMENT": alias}
            # Production requires CORS_ORIGINS
            if expected == Environment.PRODUCTION:
                env_vars["CORS_ORIGINS"] = "https://app.example.com"

            with patch.dict(os.environ, env_vars):
                config = CORSConfig()
                assert config.environment == expected

    def test_parse_origins_basic(self):
        """Test basic origin parsing."""
        config = CORSConfig()
        origins = config._parse_origins("http://localhost:3000,https://example.com")
        assert origins == ["http://localhost:3000", "https://example.com"]

    def test_parse_origins_with_spaces(self):
        """Test origin parsing with spaces."""
        config = CORSConfig()
        origins = config._parse_origins("http://localhost:3000, https://example.com , http://test.com")
        assert origins == ["http://localhost:3000", "https://example.com", "http://test.com"]

    def test_parse_origins_empty(self):
        """Test parsing empty origins string."""
        config = CORSConfig()
        origins = config._parse_origins("")
        assert origins == []

    def test_development_config(self):
        """Test development environment configuration."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000,http://localhost:8000"
        }):
            config = CORSConfig()
            middleware_config = config.get_middleware_config()

            assert "http://localhost:3000" in middleware_config["allow_origins"]
            assert "http://localhost:8000" in middleware_config["allow_origins"]
            assert middleware_config["allow_credentials"] is True
            assert "GET" in middleware_config["allow_methods"]
            assert "POST" in middleware_config["allow_methods"]

    def test_testing_config(self):
        """Test testing environment configuration."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "testing",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            config = CORSConfig()
            middleware_config = config.get_middleware_config()

            assert middleware_config["allow_origins"] == ["http://localhost:3000"]
            assert middleware_config["allow_credentials"] is False
            assert len(middleware_config["allow_methods"]) <= 5  # More restrictive

    def test_production_config_with_origins(self):
        """Test production environment configuration with proper origins."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com,https://admin.example.com"
        }):
            config = CORSConfig()
            middleware_config = config.get_middleware_config()

            assert "https://app.example.com" in middleware_config["allow_origins"]
            assert "https://admin.example.com" in middleware_config["allow_origins"]
            assert middleware_config["allow_credentials"] is True

    def test_production_config_no_origins_raises_error(self):
        """Test that production without origins raises error."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": ""
        }):
            with pytest.raises(ValueError, match="CORS_ORIGINS environment variable is required"):
                CORSConfig()

    def test_production_security_validation_wildcard(self):
        """Test that wildcard origins are rejected in production."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "*"
        }):
            with pytest.raises(ValueError, match="Wildcard.*origins are not allowed"):
                CORSConfig()

    def test_production_security_validation_localhost(self):
        """Test that localhost origins are rejected in production."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com,http://localhost:3000"
        }):
            with pytest.raises(ValueError, match="Localhost origin.*should not be used"):
                CORSConfig()

    def test_production_security_validation_http(self):
        """Test that HTTP origins are flagged in production."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "http://app.example.com"
        }):
            with pytest.raises(ValueError, match="should use HTTPS in production"):
                CORSConfig()

    def test_staging_config(self):
        """Test staging environment configuration."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "staging",
            "CORS_ORIGINS": "https://staging.example.com"
        }):
            config = CORSConfig()
            middleware_config = config.get_middleware_config()

            assert middleware_config["allow_origins"] == ["https://staging.example.com"]
            assert middleware_config["allow_credentials"] is True
            assert middleware_config["max_age"] == 3600  # More restrictive than dev


class TestCORSValidation:
    """Test CORS origin validation functions."""

    @pytest.mark.parametrize("origin,expected", [
        ("http://localhost:3000", True),
        ("https://example.com", True),
        ("https://sub.example.com", True),
        ("http://127.0.0.1:8000", True),
        ("", False),
        ("localhost:3000", False),  # Missing protocol
        ("http://example.com/", False),  # Trailing slash
        ("ftp://example.com", False),  # Wrong protocol
        ("http://", False),  # No domain
        ("https://", False),  # No domain
    ])
    def test_validate_origin_format(self, origin, expected):
        """Test origin format validation."""
        assert validate_origin_format(origin) == expected

    def test_get_safe_cors_origins_filters_invalid(self):
        """Test that invalid origins are filtered out."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000,invalid-origin,https://example.com"
        }):
            safe_origins = get_safe_cors_origins()
            assert "http://localhost:3000" in safe_origins
            assert "https://example.com" in safe_origins
            assert "invalid-origin" not in safe_origins


class TestCORSMiddlewareIntegration:
    """Test CORS middleware integration with FastAPI."""

    def create_test_app(self, cors_config: CORSConfig) -> FastAPI:
        """Create test FastAPI app with CORS configuration."""
        app = FastAPI()
        app.add_middleware(CORSMiddleware, **cors_config.get_middleware_config())

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        return app

    def test_allowed_origin_access(self):
        """Test that allowed origins can access the API."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            cors_config = CORSConfig()
            app = self.create_test_app(cors_config)
            client = TestClient(app)

            response = client.get("/test", headers={
                "Origin": "http://localhost:3000"
            })

            assert response.status_code == 200

    def test_disallowed_origin_blocked(self):
        """Test that disallowed origins are blocked."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://allowed.com"
        }):
            cors_config = CORSConfig()
            app = self.create_test_app(cors_config)
            client = TestClient(app)

            response = client.get("/test", headers={
                "Origin": "https://malicious.com"
            })

            # The request should succeed but CORS headers should indicate blocking
            assert response.status_code == 200
            # FastAPI CORS middleware doesn't set Access-Control-Allow-Origin for disallowed origins
            assert "Access-Control-Allow-Origin" not in response.headers

    def test_preflight_request_handling(self):
        """Test CORS preflight request handling."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            cors_config = CORSConfig()
            app = self.create_test_app(cors_config)
            client = TestClient(app)

            # Send preflight OPTIONS request
            response = client.options("/test", headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type"
            })

            assert response.status_code == 200
            assert "Access-Control-Allow-Origin" in response.headers
            assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"

    def test_credentials_handling_development(self):
        """Test credentials handling in development."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            cors_config = CORSConfig()
            app = self.create_test_app(cors_config)
            client = TestClient(app)

            response = client.get("/test", headers={
                "Origin": "http://localhost:3000"
            })

            assert "Access-Control-Allow-Credentials" in response.headers
            assert response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_credentials_handling_testing(self):
        """Test credentials handling in testing (should be false)."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "testing",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            cors_config = CORSConfig()
            app = self.create_test_app(cors_config)
            client = TestClient(app)

            response = client.get("/test", headers={
                "Origin": "http://localhost:3000"
            })

            # Testing environment should not allow credentials
            assert "Access-Control-Allow-Credentials" not in response.headers or \
                   response.headers.get("Access-Control-Allow-Credentials") == "false"


class TestCORSSecurityScenarios:
    """Test specific CORS security scenarios."""

    def test_malicious_origin_attempt(self):
        """Test protection against malicious origin attempts."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://legitimate-app.com"
        }):
            cors_config = CORSConfig()
            app = FastAPI()
            app.add_middleware(CORSMiddleware, **cors_config.get_middleware_config())

            @app.get("/sensitive")
            async def sensitive_endpoint():
                return {"sensitive": "data"}

            client = TestClient(app)

            # Attempt from malicious origin
            response = client.get("/sensitive", headers={
                "Origin": "https://malicious-site.com"
            })

            # Request should complete but without CORS headers allowing access
            assert response.status_code == 200
            assert "Access-Control-Allow-Origin" not in response.headers

    def test_subdomain_security(self):
        """Test that subdomains are not automatically allowed."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            cors_config = CORSConfig()
            app = FastAPI()
            app.add_middleware(CORSMiddleware, **cors_config.get_middleware_config())

            @app.get("/test")
            async def test_endpoint():
                return {"message": "test"}

            client = TestClient(app)

            # Attempt from similar subdomain that wasn't explicitly allowed
            response = client.get("/test", headers={
                "Origin": "https://evil.example.com"
            })

            assert "Access-Control-Allow-Origin" not in response.headers

    def test_case_sensitivity(self):
        """Test that origin matching is case-sensitive."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            cors_config = CORSConfig()
            app = FastAPI()
            app.add_middleware(CORSMiddleware, **cors_config.get_middleware_config())

            @app.get("/test")
            async def test_endpoint():
                return {"message": "test"}

            client = TestClient(app)

            # Attempt with different case
            response = client.get("/test", headers={
                "Origin": "https://APP.EXAMPLE.COM"
            })

            # Should not match due to case sensitivity
            assert "Access-Control-Allow-Origin" not in response.headers


class TestCORSConfigurationLogging:
    """Test CORS configuration logging and monitoring."""

    @patch('backend.api.cors_config.logger')
    def test_security_info_logging(self, mock_logger):
        """Test that security information is logged appropriately."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            cors_config = CORSConfig()
            cors_config.log_security_info()

            # Verify logging was called
            mock_logger.info.assert_called()

            # Verify sensitive information is not logged in production
            logged_messages = [call.args[0] for call in mock_logger.info.call_args_list]
            logged_text = " ".join(logged_messages).lower()

            # Should not contain actual origin URLs in production logs
            assert "origins not logged in non-development environments" in logged_text

    @patch('backend.api.cors_config.logger')
    def test_development_origin_logging(self, mock_logger):
        """Test that origins are logged in development only."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            cors_config = CORSConfig()
            cors_config.log_security_info()

            # Verify detailed logging in development
            logged_messages = [call.args[0] for call in mock_logger.info.call_args_list]
            logged_text = " ".join(logged_messages)

            # Should contain origin details in development
            assert "Origin 1:" in logged_text

    @patch('backend.api.cors_config.logger')
    def test_production_validation_error_logging(self, mock_logger):
        """Test that production validation errors are properly logged."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "*"  # Invalid for production
        }):
            with pytest.raises(ValueError):
                CORSConfig()

            # Verify error was logged
            mock_logger.error.assert_called()
            error_message = mock_logger.error.call_args[0][0]
            assert "CORS security validation failed" in error_message
            assert "Wildcard" in error_message


class TestCORSIntegrationWithMainApp:
    """Test CORS integration with the main FastAPI application."""

    def test_cors_config_function_integration(self):
        """Test get_cors_config function works correctly."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            config = get_cors_config()
            assert isinstance(config, CORSConfig)
            assert config.environment == Environment.DEVELOPMENT

    def test_multiple_cors_config_instances_consistency(self):
        """Test that multiple instances produce consistent results."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "testing",
            "CORS_ORIGINS": "http://localhost:3000"
        }):
            config1 = get_cors_config()
            config2 = get_cors_config()

            assert config1.get_middleware_config() == config2.get_middleware_config()

    def test_environment_override(self):
        """Test that environment can be overridden correctly."""
        # Test default environment
        with patch.dict(os.environ, {}, clear=True):
            config = CORSConfig()
            assert config.environment == Environment.DEVELOPMENT

        # Test explicit environment
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "CORS_ORIGINS": "https://example.com"}):
            config = CORSConfig()
            assert config.environment == Environment.PRODUCTION
