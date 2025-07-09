from abc import ABC, abstractmethod
import requests
import json
import logging

# Configure logging for debugging
logger = logging.getLogger(__name__)

# Custom Exceptions for robust error handling
class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass

class LLMAPIError(LLMServiceError):
    """Raised for API-specific errors (e.g., bad request, authentication failure)."""
    pass

class LLMResponseError(LLMServiceError):
    """Raised for issues with the LLM's response (e.g., malformed JSON, missing content)."""
    pass

class LLMConfigurationError(LLMServiceError):
    """Raised for configuration-related errors, such as a missing API key."""
    pass

class LLMService(ABC):
    @abstractmethod
    def query_llm(self, prompt: str) -> str:
        """
        {
            "name": "LLMService.query_llm",
            "version": "1.0.0",
            "description": "Abstract method to query a Large Language Model with a given prompt.",
            "interface": {
                "inputs": [{"name": "prompt", "type": "string"}],
                "outputs": "string"
            }
        }
        Queries the configured Large Language Model.
        @param {string} prompt - The text prompt to send to the LLM.
        @returns {string} The text response from the LLM.
        @raises {LLMAPIError} - If the API request fails (e.g., network error, HTTP error status).
        @raises {LLMResponseError} - If the response from the API is invalid or malformed.
        @raises {LLMConfigurationError} - If the service is not configured correctly (e.g., missing API key).
        """
        pass

class GeminiLLMService(LLMService):
    """
    {
        "name": "GeminiLLMService",
        "version": "1.0.0",
        "description": "Concrete implementation of LLMService for Google's Gemini API.",
        "dependencies": ["requests"],
        "interface": {
            "inputs": [
                {"name": "api_key", "type": "string"},
                {"name": "model_name", "type": "string"}
            ]
        }
    }
    Provides access to the Gemini LLM.
    @param {string} api_key - The API key for the Gemini API.
    @param {string} model_name - The name of the Gemini model to use.
    """
    def __init__(self, settings):
        self.settings = settings
        
        # Log QSettings information for debugging
        logger.info(f"Initializing GeminiLLMService with QSettings organization: '{settings.organizationName()}', application: '{settings.applicationName()}'")
        
        self.api_key = self.settings.value("llm/api_key", "")
        self.model_name = self.settings.value("llm/model_name", "gemini-pro")
        
        # Log configuration details (safely, without exposing the full API key)
        api_key_preview = f"{self.api_key[:8]}..." if self.api_key and len(self.api_key) > 8 else "***EMPTY***" if not self.api_key else f"{self.api_key[:4]}***"
        logger.info(f"API Key loaded: {api_key_preview} (length: {len(self.api_key) if self.api_key else 0})")
        logger.info(f"Model name loaded: {self.model_name}")
        
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        logger.info(f"Base URL configured: {self.base_url}")

    def refresh_config(self):
        """Reloads configuration from the QSettings object."""
        logger.info("Refreshing LLM configuration from QSettings")
        
        self.api_key = self.settings.value("llm/api_key", "")
        self.model_name = self.settings.value("llm/model_name", "gemini-pro")
        
        # Log refreshed configuration details
        api_key_preview = f"{self.api_key[:8]}..." if self.api_key and len(self.api_key) > 8 else "***EMPTY***" if not self.api_key else f"{self.api_key[:4]}***"
        logger.info(f"Refreshed API Key: {api_key_preview} (length: {len(self.api_key) if self.api_key else 0})")
        logger.info(f"Refreshed Model name: {self.model_name}")
        
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

    def is_configured(self):
        """Check if the service is properly configured with an API key."""
        return bool(self.api_key and self.api_key.strip())

    def query_llm(self, prompt: str) -> str:
        logger.info("Starting LLM query")
        
        # Validate prompt input
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        self.refresh_config()  # Always get the latest config before a query
        
        if not self.api_key:
            logger.error("API key is missing or empty!")
            logger.error(f"Current QSettings organization: '{self.settings.organizationName()}', application: '{self.settings.applicationName()}'")
            
            # List all available keys for debugging
            all_keys = self.settings.allKeys()
            logger.error(f"Available keys in QSettings: {all_keys}")
            
            raise LLMConfigurationError(
                "Gemini API key is not configured. Please set it in the Settings menu."
            )
        
        logger.info(f"Proceeding with API call using {len(self.api_key)}-character API key")

        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        data = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            response = requests.post(
                self.base_url, headers=headers, params=params, data=json.dumps(data), timeout=30
            )
            response.raise_for_status()
            response_json = response.json()
            
            # Safely navigate the response JSON
            candidates = response_json.get("candidates")
            if not candidates or not isinstance(candidates, list) or not candidates[0].get("content", {}).get("parts"):
                raise LLMResponseError(f"Invalid or empty response structure received: {response.text}")

            text_parts = [
                part.get("text") 
                for part in candidates[0]["content"]["parts"] 
                if part.get("text")
            ]
            if not text_parts:
                raise LLMResponseError(f"No text found in LLM response parts: {response.text}")

            return "".join(text_parts)

        except requests.exceptions.RequestException as e:
            raise LLMAPIError(f"API request failed: {e}") from e
        except json.JSONDecodeError as e:
            raise LLMResponseError(f"Failed to decode JSON response: {response.text}") from e
        except (KeyError, IndexError) as e:
            raise LLMResponseError(f"Unexpected response structure: {response.text}") from e

# Example usage (for testing purposes, not part of the main application flow)
if __name__ == "__main__":
    import os
    # It's better practice to load secrets from environment variables
    api_key_env = os.environ.get("GEMINI_API_KEY")
    model_name_main = "gemini-pro"
    
    if not api_key_env:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        print("Please set the environment variable and try again.")
    else:
        # This example usage needs to be adapted as it cannot use QSettings directly.
        # For direct testing, one might temporarily bypass the settings-based init.
        print("Bypassing QSettings for direct script execution example.")
        try:
            # Mocking settings for standalone run
            class MockSettings:
                def value(self, key, default):
                    if key == "llm/api_key":
                        return api_key_env
                    if key == "llm/model_name":
                        return model_name_main
                    return default

            llm_service = GeminiLLMService(settings=MockSettings())
            response_text = llm_service.query_llm("What is the main idea behind the SOLID principles?")
            print(f"LLM Response:\n{response_text}")
        except LLMServiceError as e:
            print(f"An error occurred: {e}")
