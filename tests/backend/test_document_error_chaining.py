import pytest
from fastapi import HTTPException, status

from backend.api.routes.documents import get_document, list_documents


class _FailingListRepo:
    def __init__(self, error: Exception):
        self._error = error

    def get_all(self, *args, **kwargs):
        raise self._error

    def count(self):
        return 0


class _FailingGetRepo:
    def __init__(self, error: Exception):
        self._error = error

    def get_by_id(self, document_id: int):
        raise self._error


@pytest.mark.asyncio
async def test_list_documents_chains_value_error():
    repo = _FailingListRepo(ValueError("bad pagination"))

    with pytest.raises(HTTPException) as exc:
        await list_documents(
            query=None,
            page=1,
            per_page=5,
            sort_by="created_at",
            sort_order="desc",
            doc_repo=repo,
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert isinstance(exc.value.__cause__, ValueError)


@pytest.mark.asyncio
async def test_get_document_chains_internal_errors():
    repo = _FailingGetRepo(RuntimeError("db down"))

    with pytest.raises(HTTPException) as exc:
        await get_document(document_id=123, doc_repo=repo)

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert isinstance(exc.value.__cause__, RuntimeError)
