"""Minimal pytest configuration for the streamlined backend test suite."""

from __future__ import annotations

import sys
import types


def _install_pdf_stub() -> None:
    """Install a lightweight stub for PyMuPDF so tests can run without the dependency."""

    class _StubPage:
        def get_text(self) -> str:
            return ""

    class _StubDocument:
        def __enter__(self) -> "_StubDocument":
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            return None

        def __len__(self) -> int:
            return 0

        def __getitem__(self, index: int) -> _StubPage:
            return _StubPage()

    def _open(*_args, **_kwargs) -> _StubDocument:
        return _StubDocument()

    stub_module = types.SimpleNamespace(open=_open, Document=_StubDocument)
    sys.modules.setdefault("fitz", stub_module)
    sys.modules.setdefault("pymupdf", stub_module)


def _install_llama_stub() -> None:
    """Install a small stub for llama_index so imports succeed without the dependency."""

    llama_module = types.ModuleType("llama_index")
    llama_core = types.ModuleType("llama_index.core")
    llama_core_schema = types.ModuleType("llama_index.core.schema")

    class _StubStorageContext:
        @classmethod
        def from_defaults(cls, **_kwargs):
            return cls()

    class _StubVectorStoreIndex:
        @classmethod
        def from_documents(cls, *_args, **_kwargs):
            return cls()

        def as_retriever(self, **_kwargs):
            return self

        def retrieve(self, *_args, **_kwargs):
            return []

    def _load_index_from_storage(*_args, **_kwargs):
        return _StubVectorStoreIndex()

    class _StubDocument:
        def __init__(self, text: str | None = None):
            self.text = text or ""

    llama_core.StorageContext = _StubStorageContext
    llama_core.VectorStoreIndex = _StubVectorStoreIndex
    llama_core.load_index_from_storage = _load_index_from_storage
    llama_core_schema.Document = _StubDocument

    sys.modules.setdefault("llama_index", llama_module)
    sys.modules.setdefault("llama_index.core", llama_core)
    sys.modules.setdefault("llama_index.core.schema", llama_core_schema)


_install_pdf_stub()
_install_llama_stub()
