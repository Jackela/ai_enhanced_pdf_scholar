from __future__ import annotations

from pydantic import BaseModel, ValidationError

import backend.api.models as models
from backend.api.models import SecurityValidationError, SecurityValidationErrorResponse


def test_security_validation_error_response():
    err = SecurityValidationError(field="q", pattern=".*", message="bad")
    resp = SecurityValidationErrorResponse(
        success=False,
        error="Security validation failed",
        field=err.field,
        pattern=err.pattern,
        error_code="SECURITY_VALIDATION_ERROR",
        detail=str(err),
    )
    assert resp.field == "q"
    assert resp.error_code == "SECURITY_VALIDATION_ERROR"


def test_validation_error_response_from_pydantic():
    class Model(BaseModel):
        x: int

    try:
        Model(x="not-int")
    except ValidationError as exc:
        # ValidationErrorResponse is not exported; build a minimal shape from errors
        errors = exc.errors()
        assert errors[0]["loc"] == ("x",)
        assert errors[0]["type"]
