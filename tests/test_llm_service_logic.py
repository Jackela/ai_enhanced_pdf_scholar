"""
Unit tests for GeminiLLMService in src/llm_service.py.
Covers configuration checks, refresh_config, is_configured, and query_llm various scenarios.
"""

import json
import pytest
import requests
from unittest.mock import MagicMock, patch

from src.llm_service import (
    GeminiLLMService,
    LLMConfigurationError,
    LLMAPIError,
    LLMResponseError
)


class DummySettings:
    """Stub for QSettings-like interface."""
    def __init__(self, api_key, model_name, keys=None):
        self._api_key = api_key
        self._model_name = model_name
        self._keys = keys or ["llm/api_key", "llm/model_name"]
    def value(self, key, default=None):
        if key == "llm/api_key":
            return self._api_key
        if key == "llm/model_name":
            return self._model_name
        return default
    def organizationName(self):
        return "org"
    def applicationName(self):
        return "app"
    def allKeys(self):
        return self._keys


@pytest.fixture
def settings_with_key():
    return DummySettings(api_key="secret1234", model_name="test-model")

@pytest.fixture
def settings_without_key():
    return DummySettings(api_key="", model_name="test-model")


def test_is_configured_true(settings_with_key):
    service = GeminiLLMService(settings=settings_with_key)
    assert service.is_configured() is True


def test_is_configured_false(settings_without_key):
    service = GeminiLLMService(settings=settings_without_key)
    assert service.is_configured() is False


def test_refresh_config_updates_attributes(settings_with_key):
    service = GeminiLLMService(settings=settings_with_key)
    # change settings
    settings_with_key._api_key = "newkey123"
    settings_with_key._model_name = "new-model"
    service.refresh_config()
    assert service.api_key == "newkey123"
    assert service.model_name == "new-model"
    assert "new-model" in service.base_url


def test_query_llm_empty_prompt(settings_with_key):
    service = GeminiLLMService(settings=settings_with_key)
    with pytest.raises(ValueError):
        service.query_llm("")
    with pytest.raises(ValueError):
        service.query_llm("   ")


def test_query_llm_missing_api_key(settings_without_key):
    service = GeminiLLMService(settings=settings_without_key)
    with pytest.raises(LLMConfigurationError) as excinfo:
        service.query_llm("Hello")
    assert "API key is not configured" in str(excinfo.value)

@patch("src.llm_service.requests.post")
def test_query_llm_success(mock_post, settings_with_key):
    # prepare successful response
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "response1"}, {"text": "response2"}]}}
        ]
    }
    mock_post.return_value = mock_response

    service = GeminiLLMService(settings=settings_with_key)
    result = service.query_llm("Prompt text")
    assert result == "response1response2"
    mock_post.assert_called_once()

@patch("src.llm_service.requests.post")
def test_query_llm_http_error(mock_post, settings_with_key):
    mock_post.side_effect = requests.exceptions.RequestException("timeout")
    service = GeminiLLMService(settings=settings_with_key)
    with pytest.raises(LLMAPIError) as excinfo:
        service.query_llm("Test")
    assert "API request failed" in str(excinfo.value)

@patch("src.llm_service.requests.post")
def test_query_llm_json_decode_error(mock_post, settings_with_key):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = json.JSONDecodeError("doc", "doc", 0)
    mock_response.text = "bad json"
    mock_post.return_value = mock_response

    service = GeminiLLMService(settings=settings_with_key)
    with pytest.raises(LLMResponseError) as excinfo:
        service.query_llm("Test2")
    assert "Failed to decode JSON response" in str(excinfo.value)

@patch("src.llm_service.requests.post")
def test_query_llm_malformed_structure(mock_post, settings_with_key):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    # missing candidates key
    mock_response.json.return_value = {}
    mock_response.text = "no candidates"
    mock_post.return_value = mock_response

    service = GeminiLLMService(settings=settings_with_key)
    with pytest.raises(LLMResponseError) as excinfo:
        service.query_llm("Test3")
    assert "Invalid or empty response structure" in str(excinfo.value)

@patch("src.llm_service.requests.post")
def test_query_llm_no_text_parts(mock_post, settings_with_key):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    # candidates present but empty parts
    mock_response.json.return_value = {"candidates": [{"content": {"parts": [{}]}}]}
    mock_response.text = "empty parts"
    mock_post.return_value = mock_response

    service = GeminiLLMService(settings=settings_with_key)
    with pytest.raises(LLMResponseError) as excinfo:
        service.query_llm("Test4")
    assert "No text found in LLM response parts" in str(excinfo.value) 