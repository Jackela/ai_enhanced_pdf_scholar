import os

import pytest

from backend.api.cors_config import (
    CORSConfig,
    Environment,
    get_safe_cors_origins,
    validate_origin_format,
)


def test_cors_config_development_defaults(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:8000")

    config = CORSConfig()

    assert config.environment is Environment.DEVELOPMENT
    assert "http://localhost:3000" in config.config["allow_origins"]
    assert config.config["allow_credentials"] is True
    assert "GET" in config.config["allow_methods"]


def test_cors_config_production_requires_https(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://app.example.com,https://api.example.com"
    )

    config = CORSConfig()

    assert config.environment is Environment.PRODUCTION
    origins = config.get_middleware_config()["allow_origins"]
    assert origins == ["https://app.example.com", "https://api.example.com"]


def test_cors_config_production_invalid_origin_raises(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    with pytest.raises(ValueError):
        CORSConfig()


def test_validate_origin_helpers(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://valid.example.com,invalid-origin,https://ok.example.org/",
    )

    safe = get_safe_cors_origins()

    assert "https://valid.example.com" in safe
    assert not any(origin.endswith("/") for origin in safe)
    assert validate_origin_format("https://site.test")
    assert not validate_origin_format("ftp://site.test")
    assert not validate_origin_format("http://site.test/")
