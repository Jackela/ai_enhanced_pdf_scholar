import pytest
from unittest.mock import MagicMock, patch
import requests
import json
from src.llm_service import GeminiLLMService, LLMAPIError, LLMResponseError, LLMConfigurationError

# A sample successful response from the Gemini API
MOCK_SUCCESS_RESPONSE = {
    "candidates": [
        {"content": {"parts": [{"text": "This is a test response."}]}}
    ]
}

class MockSettings:
    """A mock QSettings class for testing purposes."""
    def __init__(self, settings_dict):
        self._settings = settings_dict

    def value(self, key, defaultValue=None):
        return self._settings.get(key, defaultValue)
    
    def organizationName(self):
        return "Test Organization"
    
    def applicationName(self):
        return "Test Application"
    
    def allKeys(self):
        return list(self._settings.keys())

class TestGeminiLLMService:

    @pytest.fixture
    def configured_service(self):
        """Provides a service instance configured with a valid API key."""
        mock_settings = MockSettings({
            "llm/api_key": "test_api_key",
            "llm/model_name": "gemini-pro"
        })
        return GeminiLLMService(settings=mock_settings)

    @patch('src.llm_service.requests.post')
    def test_query_llm_success(self, mock_requests_post, configured_service):
        """Tests a successful LLM query."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = MOCK_SUCCESS_RESPONSE
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        result = configured_service.query_llm("Test prompt")

        assert result == "This is a test response."
        mock_requests_post.assert_called_once()
        
    def test_query_llm_raises_configuration_error_if_no_api_key(self):
        """Tests that LLMConfigurationError is raised if the API key is missing."""
        mock_settings = MockSettings({"llm/api_key": ""}) # No API key
        service = GeminiLLMService(settings=mock_settings)
        
        with pytest.raises(LLMConfigurationError, match="Gemini API key is not configured"):
            service.query_llm("Test prompt")

    @patch('src.llm_service.requests.post')
    def test_query_llm_raises_llm_api_error_on_http_error(self, mock_requests_post, configured_service):
        """Tests that LLMAPIError is raised for HTTP errors."""
        mock_requests_post.side_effect = requests.exceptions.HTTPError("404 Not Found")

        with pytest.raises(LLMAPIError, match="API request failed: 404 Not Found"):
            configured_service.query_llm("Test prompt")

    @patch('src.llm_service.requests.post')
    def test_query_llm_raises_llm_api_error_on_request_exception(self, mock_requests_post, configured_service):
        """Tests that LLMAPIError is raised for general request exceptions."""
        mock_requests_post.side_effect = requests.exceptions.RequestException("Connection timed out")

        with pytest.raises(LLMAPIError, match="API request failed: Connection timed out"):
            configured_service.query_llm("Test prompt")

    @patch('src.llm_service.requests.post')
    def test_query_llm_raises_llm_response_error_on_json_decode_error(self, mock_requests_post, configured_service):
        """Tests that LLMResponseError is raised for JSON decoding errors."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = "Invalid JSON"
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "Invalid JSON", 0)
        mock_requests_post.return_value = mock_response

        with pytest.raises(LLMResponseError, match="Failed to decode JSON response: Invalid JSON"):
            configured_service.query_llm("Test prompt")

    @pytest.mark.parametrize("invalid_response", [
        {"candidates": []},
        {"candidates": [{}]},
        {"candidates": [{"content": {}}]},
        {"candidates": [{"content": {"parts": []}}]},
        {"candidates": [{"content": {"parts": [{"image": "base64"}]}}]},
        {"no_candidates_field": True}
    ])
    @patch('src.llm_service.requests.post')
    def test_query_llm_raises_llm_response_error_on_malformed_data(self, mock_requests_post, invalid_response, configured_service):
        """Tests that LLMResponseError is raised for various malformed responses."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = invalid_response
        mock_response.text = str(invalid_response)
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        with pytest.raises(LLMResponseError, match="Invalid or empty response structure|No text found in LLM response"):
            configured_service.query_llm("Test prompt")

    @patch('src.llm_service.requests.post')
    def test_query_llm_with_empty_prompt_raises_value_error(self, mock_requests_post, configured_service):
        """Tests that ValueError is raised for empty prompts."""
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            configured_service.query_llm("")

    @patch('src.llm_service.requests.post')  
    def test_query_llm_with_none_prompt_raises_value_error(self, mock_requests_post, configured_service):
        """Tests that ValueError is raised for None prompts."""
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            configured_service.query_llm(None)

    @patch('src.llm_service.requests.post')
    def test_query_llm_with_very_long_prompt(self, mock_requests_post, configured_service):
        """Tests handling of very long prompts."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = MOCK_SUCCESS_RESPONSE
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response

        long_prompt = "x" * 10000  # Very long prompt
        result = configured_service.query_llm(long_prompt)

        assert result == "This is a test response."
        mock_requests_post.assert_called_once()

    def test_is_configured_with_valid_api_key(self, configured_service):
        """Tests that is_configured returns True when API key is present."""
        assert configured_service.is_configured() is True

    def test_is_configured_with_empty_api_key(self):
        """Tests that is_configured returns False when API key is empty."""
        mock_settings = MockSettings({"llm/api_key": ""})
        service = GeminiLLMService(settings=mock_settings)
        assert service.is_configured() is False

    def test_is_configured_with_none_api_key(self):
        """Tests that is_configured returns False when API key is None."""
        mock_settings = MockSettings({"llm/api_key": None})
        service = GeminiLLMService(settings=mock_settings)
        assert service.is_configured() is False
