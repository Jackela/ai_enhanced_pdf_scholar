import types

from src.services.rag.file_manager import RAGFileManager
from src.services.rag.index_builder import RAGIndexBuilder


class _StubFileManager(RAGFileManager):
    def __init__(self):
        # bypass base init
        pass

    def verify_index_files(self, storage_dir: str) -> bool:
        return True


def test_index_builder_test_mode_skips_llama_init(monkeypatch, tmp_path):
    fm = _StubFileManager()
    builder = RAGIndexBuilder(api_key="key", file_manager=fm, test_mode=True)
    assert builder.test_mode is True
    # In test mode, build_index_from_pdf should short-circuit
    assert (
        builder.build_index_from_pdf(str(tmp_path / "file.pdf"), str(tmp_path)) is True
    )
