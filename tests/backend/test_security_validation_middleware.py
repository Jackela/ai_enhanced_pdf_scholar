import pytest
from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import Response

from backend.api.middleware.security_validation import (
    SecurityValidationMiddleware,
    create_security_exception_handlers,
    log_security_metrics,
)
from backend.api.models import SecurityValidationError


def _request_scope(path: str = "/") -> dict[str, object]:
    return {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "client": ("127.0.0.1", 1234),
    }


@pytest.mark.asyncio
async def test_security_validation_middleware_handles_security_error():
    middleware = SecurityValidationMiddleware(app=lambda scope: None)

    async def call_next(request: Request):
        raise SecurityValidationError("field", "bad pattern", pattern="xss")

    request = Request(_request_scope("/danger"))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 400
    import json

    body = json.loads(response.body)
    assert body.get("error_code") == "SECURITY_VALIDATION_ERROR"
    assert body.get("field") == "field"


@pytest.mark.asyncio
async def test_security_validation_middleware_handles_validation_error():
    middleware = SecurityValidationMiddleware(app=lambda scope: None)

    class Payload(BaseModel):
        value: int

    try:
        Payload(value="not-an-int")
    except ValidationError as exc:
        validation_error = exc

    async def call_next(request: Request):
        raise validation_error

    request = Request(_request_scope("/validate"))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 422
    import json

    body = json.loads(response.body)
    assert body.get("error_code") in (
        "VALIDATION_ERROR",
        "VALIDATION_ERROR".lower(),
        None,
    )


@pytest.mark.asyncio
async def test_security_validation_middleware_passthrough():
    middleware = SecurityValidationMiddleware(app=lambda scope: None)

    async def call_next(request: Request):
        return Response("ok", status_code=200)

    request = Request(_request_scope("/ok"))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_security_exception_handlers_build_responses():
    handlers = create_security_exception_handlers()
    request = Request(_request_scope("/path"))

    security_exc = SecurityValidationError("field", "blocked", pattern="sql")
    response = await handlers[SecurityValidationError](request, security_exc)
    assert response.status_code == 400

    class Payload(BaseModel):
        value: int

    try:
        Payload(value="bad")
    except ValidationError as exc:
        validation_exc = exc

    response_validation = await handlers[ValidationError](request, validation_exc)
    assert response_validation.status_code == 422


def test_log_security_metrics(caplog):
    caplog.set_level("INFO")
    log_security_metrics("test_event", "field", client_ip="1.2.3.4")
    assert any("SECURITY_METRIC" in message for message in caplog.messages)
