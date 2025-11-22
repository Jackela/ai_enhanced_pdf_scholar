"""Request models for the v2 API surface."""

from __future__ import annotations

from pydantic import BaseModel, Field, conlist, constr


class QueryRequest(BaseModel):
    """RAG query parameters for single-document queries."""

    query: constr(min_length=1, max_length=2000)
    temperature: float = Field(0.2, ge=0.0, le=1.0)
    max_results: int = Field(5, ge=1, le=50)
    use_cache: bool = True
    streaming: bool = False


class MultiDocumentQueryRequest(QueryRequest):
    """RAG query parameters for multi-document queries."""

    document_ids: conlist(int, min_length=1)
    synthesis_mode: str = Field(
        "merge",
        description="Strategy for combining answers",
        pattern="^(merge|compare|summarize)$",
    )


class IndexBuildRequest(BaseModel):
    """Index build parameters."""

    force_rebuild: bool = False
    chunking_strategy: str = Field(
        "default",
        description="Chunking strategy identifier",
    )
    priority: str | None = Field(
        None,
        description="Optional priority hint for schedulers",
    )
