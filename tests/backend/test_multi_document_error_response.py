from backend.api.models.multi_document_models import ErrorResponse


def test_error_response_has_detail_and_defaults():
    resp = ErrorResponse(error="boom", detail="bad", error_code="ERR123")

    assert resp.success is False
    assert resp.error == "boom"
    assert resp.detail == "bad"
    assert resp.error_code == "ERR123"

    schema = resp.model_json_schema()
    assert "detail" in schema["properties"], "detail field missing from schema"
