"""
Settings API Routes
Handles system settings management including API keys, configuration,
and system status.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from backend.api.dependencies import get_db
from backend.api.error_handling import SystemException
from backend.api.models import (
    DANGEROUS_SQL_PATTERNS,
    XSS_PATTERNS,
    SecurityValidationError,
    validate_against_patterns,
)
from src.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class ApiKeyRequest(BaseModel):
    """API key test request with security validation."""
    api_key: str = Field(..., min_length=10, max_length=200,
                        description="API key to test")

    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key format and security."""
        # Basic validation against injection attacks
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, 'api_key', 'sql_injection')
        validate_against_patterns(v, XSS_PATTERNS, 'api_key', 'xss_attempt')

        # API key format validation
        if not v.strip():
            raise SecurityValidationError('api_key', 'API key cannot be empty')

        # Check for suspicious patterns
        suspicious_patterns = [
            r'\s',  # No whitespace allowed in API keys
            r'[<>"\']',  # No HTML/quote characters
            r'javascript:',  # No JS protocol
            r'data:',  # No data protocol
        ]

        validate_against_patterns(v, suspicious_patterns, 'api_key', 'suspicious_pattern')

        return v.strip()


class SettingsRequest(BaseModel):
    """Settings update request with security validation."""
    gemini_api_key: str | None = Field(None, min_length=10, max_length=200,
                                         description="Google Gemini API key")
    rag_enabled: bool = Field(False, description="Enable RAG functionality")

    @field_validator('gemini_api_key')
    @classmethod
    def validate_gemini_api_key(cls, v: str | None) -> str | None:
        """Validate Gemini API key."""
        if v is None:
            return v

        # Skip validation if it's a masked value (contains bullets)
        if '●' in v:
            return v

        # Basic validation against injection attacks
        validate_against_patterns(v, DANGEROUS_SQL_PATTERNS, 'gemini_api_key', 'sql_injection')
        validate_against_patterns(v, XSS_PATTERNS, 'gemini_api_key', 'xss_attempt')

        # API key format validation
        if not v.strip():
            raise SecurityValidationError('gemini_api_key', 'API key cannot be empty')

        # Check for suspicious patterns
        suspicious_patterns = [
            r'\s',  # No whitespace allowed in API keys
            r'[<>"\']',  # No HTML/quote characters
            r'javascript:',  # No JS protocol
            r'data:',  # No data protocol
        ]

        validate_against_patterns(v, suspicious_patterns, 'gemini_api_key', 'suspicious_pattern')

        return v.strip()


class SettingsResponse(BaseModel):
    """Settings response model."""
    gemini_api_key: str = Field("", description="Masked API key")
    rag_enabled: bool = Field(False, description="RAG enabled status")
    has_api_key: bool = Field(False, description="Whether API key is configured")


class ApiKeyTestResponse(BaseModel):
    """API key test response model."""
    valid: bool = Field(..., description="Whether API key is valid")
    error: str | None = Field(None, description="Error message if invalid")


class SettingsManager:
    """Manages system settings persistence."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self._initialize_settings_table()

    def _initialize_settings_table(self):
        """Initialize settings table if not exists."""
        try:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            # Create index
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_key ON system_settings(key)"
            )
            logger.debug("Settings table initialized")
        except Exception as e:
            logger.error(f"Failed to initialize settings table: {e}")
            raise

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        try:
            result = self.db.fetch_one(
                "SELECT value FROM system_settings WHERE key = ?", (key,)
            )
            if result and result["value"] is not None:
                # Try to parse JSON, fallback to string
                try:
                    return json.loads(result["value"])
                except (json.JSONDecodeError, TypeError):
                    return result["value"]
            return default
        except Exception as e:
            logger.error(f"Failed to get setting {key}: {e}")
            return default

    def set_setting(self, key: str, value: Any) -> bool:
        """Set a setting value."""
        try:
            # Serialize value to JSON if needed
            if isinstance(value, (dict, list, bool)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value) if value is not None else None
            # Use INSERT OR REPLACE to handle both insert and update
            self.db.execute(
                """
                INSERT OR REPLACE INTO system_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
                (key, serialized_value),
            )
            logger.debug(f"Setting {key} updated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to set setting {key}: {e}")
            return False

    def get_all_settings(self) -> dict[str, Any]:
        """Get all settings as a dictionary."""
        try:
            results = self.db.fetch_all("SELECT key, value FROM system_settings")
            settings = {}
            for result in results:
                key = result["key"]
                value = result["value"]
                # Try to parse JSON
                if value is not None:
                    try:
                        settings[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        settings[key] = value
                else:
                    settings[key] = None
            return settings
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            return {}


def get_settings_manager(db: DatabaseConnection = Depends(get_db)) -> SettingsManager:
    """Get settings manager dependency."""
    return SettingsManager(db)


def mask_api_key(api_key: str) -> str:
    """Mask API key for safe display."""
    if not api_key or len(api_key) < 8:
        return ""
    return api_key[:4] + "●●●●●●●●" + api_key[-4:]


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    settings_manager: SettingsManager = Depends(get_settings_manager),
):
    """Get current system settings."""
    try:
        gemini_api_key = settings_manager.get_setting("gemini_api_key", "")
        rag_enabled = settings_manager.get_setting("rag_enabled", False)
        return SettingsResponse(
            gemini_api_key=mask_api_key(gemini_api_key) if gemini_api_key else "",
            rag_enabled=bool(rag_enabled),
            has_api_key=bool(gemini_api_key and gemini_api_key.strip()),
        )
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise SystemException(
            message="Failed to retrieve system settings",
            error_type="database") from e


@router.post("/settings")
async def update_settings(
    request: SettingsRequest,
    settings_manager: SettingsManager = Depends(get_settings_manager),
):
    """Update system settings."""
    try:
        # Update API key if provided
        if request.gemini_api_key is not None:
            # Don't update if it's a masked value
            if not request.gemini_api_key.startswith("●"):
                settings_manager.set_setting(
                    "gemini_api_key", request.gemini_api_key.strip()
                )
        # Update RAG enabled status
        settings_manager.set_setting("rag_enabled", request.rag_enabled)
        logger.info("System settings updated successfully")
        return {"message": "Settings updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise SystemException(
            message="Failed to update system settings",
            error_type="database") from e


@router.post("/test-api-key", response_model=ApiKeyTestResponse)
async def test_api_key(request: ApiKeyRequest):
    """Test if provided API key is valid."""
    try:
        api_key = request.api_key.strip()
        if not api_key:
            return ApiKeyTestResponse(valid=False, error="API key is empty")
        # Basic format validation
        if not api_key.startswith("AIza") or len(api_key) < 20:
            return ApiKeyTestResponse(
                valid=False,
                error="Invalid API key format. Gemini API keys should start with 'AIza'",
            )
        # Test the API key by making a simple request
        try:
            import google.generativeai as genai

            # Configure the API
            genai.configure(api_key=api_key)
            # Try to list models to test the key
            models = genai.list_models()
            model_list = list(models)
            if model_list:
                logger.info("API key test successful")
                return ApiKeyTestResponse(valid=True)
            else:
                return ApiKeyTestResponse(
                    valid=False, error="No models available with this API key"
                )
        except ImportError:
            # If google.generativeai is not installed, just do basic validation
            logger.warning("google.generativeai not installed, using basic validation")
            return ApiKeyTestResponse(valid=True)
        except Exception as api_error:
            logger.warning(f"API key test failed: {api_error}")
            return ApiKeyTestResponse(
                valid=False, error=f"API key validation failed: {str(api_error)}"
            )
    except Exception as e:
        logger.error(f"Failed to test API key: {e}")
        return ApiKeyTestResponse(valid=False, error="Failed to test API key")


@router.get("/status")
async def get_system_status(
    db: DatabaseConnection = Depends(get_db),
    settings_manager: SettingsManager = Depends(get_settings_manager),
):
    """Get comprehensive system status."""
    try:
        # Check database
        db_status = "healthy"
        try:
            db.fetch_one("SELECT 1")
        except Exception:
            db_status = "error"
        # Check settings
        gemini_api_key = settings_manager.get_setting("gemini_api_key", "")
        rag_enabled = settings_manager.get_setting("rag_enabled", False)
        # Check document count
        doc_count = 0
        try:
            result = db.fetch_one("SELECT COUNT(*) as count FROM documents")
            doc_count = result["count"] if result else 0
        except Exception:
            pass
        # Check vector index count
        index_count = 0
        try:
            result = db.fetch_one("SELECT COUNT(*) as count FROM vector_indexes")
            index_count = result["count"] if result else 0
        except Exception:
            pass
        return {
            "database": {
                "status": db_status,
                "document_count": doc_count,
                "vector_index_count": index_count,
            },
            "api": {
                "has_gemini_key": bool(gemini_api_key and gemini_api_key.strip()),
                "rag_enabled": bool(rag_enabled),
            },
            "version": "2.0.0",
            "system_health": "healthy" if db_status == "healthy" else "degraded",
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise SystemException(
            message="Failed to retrieve system status",
            error_type="general") from e
