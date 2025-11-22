from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.database.models import DocumentModel, VectorIndexModel
from src.services.enhanced_rag_service import EnhancedRAGService

pytestmark = pytest.mark.services


class DummyDB:
    def fetch_one(self, *args, **kwargs):
        return None

    def fetch_all(self, *args, **kwargs):
        return []

    def execute(self, *args, **kwargs):
        class Result:
            rowcount = 0

            def fetchone(self_inner):
                return None

        return Result()

    def get_last_insert_id(self) -> int:
        return 1


class DummyDocumentRepo:
    def __init__(self):
        self.docs = {
            1: DocumentModel(
                id=1,
                title="Doc1",
                file_path="/docs/doc1.pdf",
                file_hash="hash1",
                file_size=100,
                metadata={},
                _from_database=True,
            )
        }
        self.updated_access: list[int] = []

    def find_by_id(self, doc_id: int):
        return self.docs.get(doc_id)

    def update_access_time(self, doc_id: int):
        self.updated_access.append(doc_id)
        return True


class DummyVectorRepo:
    def __init__(self):
        self.records: dict[int, VectorIndexModel] = {}
        self.cleaned = 0
        self.deleted_ids: list[int] = []
        self.stats_calls = 0

    def find_by_document_id(self, doc_id: int):
        return self.records.get(doc_id)

    def create(self, model: VectorIndexModel):
        model.id = len(self.records) + 1
        self.records[model.document_id] = model
        return model

    def update(self, model: VectorIndexModel):
        self.records[model.document_id] = model
        return model

    def delete(self, index_id: int):
        self.deleted_ids.append(index_id)
        for key, val in list(self.records.items()):
            if val.id == index_id:
                del self.records[key]

    def cleanup_orphaned_indexes(self):
        self.cleaned = len(self.records)
        self.records.clear()
        return self.cleaned

    def get_index_statistics(self):
        self.stats_calls += 1
        return {"total_indexes": len(self.records)}


class DummyPromptManager:
    def get_prompt(self, *_args, **_kwargs):
        return "Prompt"


def build_test_service(
    monkeypatch,
    tmp_path: Path,
    doc_repo: DummyDocumentRepo | None = None,
    vector_repo: DummyVectorRepo | None = None,
) -> tuple[EnhancedRAGService, DummyDocumentRepo, DummyVectorRepo]:
    """
    Helper to create an EnhancedRAGService wired to dummy repositories so tests
    can mutate repository state directly.
    """
    doc_repo = doc_repo or DummyDocumentRepo()
    vector_repo = vector_repo or DummyVectorRepo()
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="test-key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
        vector_storage_dir=str(tmp_path / "vector_store"),
    )
    return service, doc_repo, vector_repo


@pytest.fixture
def enhanced_rag(monkeypatch):
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository",
        lambda db: DummyDocumentRepo(),
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: DummyVectorRepo(),
    )
    # Skip heavy llama index init
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="test-key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    return service


def test_enhanced_rag_initialization(enhanced_rag: EnhancedRAGService):
    assert enhanced_rag.api_key == "test-key"
    assert enhanced_rag.vector_storage_dir.exists()


def test_load_index_for_document(monkeypatch, tmp_path: Path):
    doc_repo = DummyDocumentRepo()
    vector_repo = DummyVectorRepo()
    idx_path = tmp_path / "idx"
    idx_path.mkdir()
    vector_repo.records[1] = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(idx_path),
        index_hash="hash",
        chunk_count=1,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    monkeypatch.setattr(service, "_verify_index_files", lambda path: True)
    service.load_index_for_document(1)
    assert service.current_document_id == 1
    assert doc_repo.updated_access == [1]


def test_get_document_index_status(monkeypatch, tmp_path: Path):
    doc_repo = DummyDocumentRepo()
    vector_repo = DummyVectorRepo()
    idx_path = tmp_path / "idx"
    idx_path.mkdir()
    vector_repo.records[1] = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(idx_path),
        index_hash="hash",
        chunk_count=2,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    monkeypatch.setattr(service, "_verify_index_files", lambda path: True)
    status = service.get_document_index_status(1)
    assert status["has_index"] is True
    assert status["index_valid"] is True


def test_cleanup_orphaned_indexes(monkeypatch):
    doc_repo = DummyDocumentRepo()
    vector_repo = DummyVectorRepo()
    vector_repo.records[1] = VectorIndexModel(
        id=1,
        document_id=1,
        index_path="/tmp/index",
        index_hash="hash",
        chunk_count=1,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    cleaned = service.cleanup_orphaned_indexes()
    assert cleaned == 1


def test_query_document_in_test_mode(monkeypatch):
    doc_repo = DummyDocumentRepo()
    vector_repo = DummyVectorRepo()
    idx_path = Path("/tmp/test_idx")
    idx_path.mkdir(parents=True, exist_ok=True)
    vector_repo.records[1] = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(idx_path),
        index_hash="hash",
        chunk_count=1,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    monkeypatch.setattr(service, "_verify_index_files", lambda path: True)
    response = service.query_document("What is AI?", 1)
    assert "Test mode response" in response


def test_rebuild_index(monkeypatch):
    doc_repo = DummyDocumentRepo()
    vector_repo = DummyVectorRepo()
    vector_repo.records[1] = VectorIndexModel(
        id=1,
        document_id=1,
        index_path="/tmp/index",
        index_hash="hash",
        chunk_count=1,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    rebuilt = {"result": "new"}
    monkeypatch.setattr(
        service, "build_index_from_document", lambda doc, overwrite: rebuilt
    )
    result = service.rebuild_index(1)
    assert result == rebuilt
    assert vector_repo.deleted_ids == [1]


def test_get_enhanced_cache_info(monkeypatch):
    doc_repo = DummyDocumentRepo()
    vector_repo = DummyVectorRepo()
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    info = service.get_enhanced_cache_info()
    assert "vector_storage_dir" in info
    assert "database_stats" in info


def test_recover_corrupted_index(monkeypatch, tmp_path: Path):
    doc_repo = DummyDocumentRepo()
    vector_repo = DummyVectorRepo()
    idx_path = tmp_path / "idx"
    idx_path.mkdir()
    vector_repo.records[1] = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(idx_path),
        index_hash="hash",
        chunk_count=1,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.DocumentRepository", lambda db: doc_repo
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.VectorIndexRepository",
        lambda db: vector_repo,
    )
    monkeypatch.setattr(
        "src.services.enhanced_rag_service.EnhancedRAGService._initialize_llama_index",
        lambda self: None,
    )
    service = EnhancedRAGService(
        api_key="key",
        db_connection=DummyDB(),
        test_mode=True,
        prompt_manager=DummyPromptManager(),
    )
    monkeypatch.setattr(service, "_verify_index_files", lambda path: False)
    monkeypatch.setattr(
        service,
        "build_index_from_document",
        lambda doc, overwrite: vector_repo.records[1],
    )
    result = service.recover_corrupted_index(1, force_rebuild=True)
    assert result["recovery_successful"] is True
    assert "full_rebuild" in result["repair_actions"]


def test_analyze_index_corruption_missing_directory(
    enhanced_rag: EnhancedRAGService, tmp_path: Path
):
    missing_path = tmp_path / "nope"
    index = VectorIndexModel(
        document_id=1,
        index_path=str(missing_path),
        index_hash="hash",
        chunk_count=0,
    )
    result = enhanced_rag._analyze_index_corruption(index)
    assert result["corruption_detected"] is True
    assert "missing_directory" in result["corruption_type"]
    assert result["corruption_severity"] == "critical"


def test_analyze_index_corruption_flags_empty_files(monkeypatch, tmp_path: Path):
    service, _, _ = build_test_service(monkeypatch, tmp_path)
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    (index_dir / "default__vector_store.json").write_text("{}")
    (index_dir / "graph_store.json").write_text("")
    (index_dir / "index_store.json").write_text("{}")
    index = VectorIndexModel(
        document_id=1,
        index_path=str(index_dir),
        index_hash="hash",
        chunk_count=0,
    )
    result = service._analyze_index_corruption(index)
    assert result["corruption_detected"] is True
    assert "graph_store.json" in result["file_size_issues"]
    assert result["corruption_severity"] == "moderate"


def test_attempt_partial_index_repair_triggers_verification(
    monkeypatch, tmp_path: Path
):
    service, _, _ = build_test_service(monkeypatch, tmp_path)
    index_dir = tmp_path / "partial_idx"
    index_dir.mkdir()
    (index_dir / "default__vector_store.json").write_text("{}")
    index = VectorIndexModel(
        document_id=1,
        index_path=str(index_dir),
        index_hash="hash",
        chunk_count=0,
    )
    called = {}

    def fake_verify(path: str) -> bool:
        called["path"] = path
        return True

    monkeypatch.setattr(service, "_verify_index_files", fake_verify)
    assert service._attempt_partial_index_repair(index) is True
    assert called["path"] == str(index_dir)


def test_attempt_partial_index_repair_without_vector_store(monkeypatch, tmp_path: Path):
    service, _, _ = build_test_service(monkeypatch, tmp_path)
    index_dir = tmp_path / "partial_idx_missing"
    index_dir.mkdir()
    index = VectorIndexModel(
        document_id=1,
        index_path=str(index_dir),
        index_hash="hash",
        chunk_count=0,
    )
    assert service._attempt_partial_index_repair(index) is False


def test_perform_index_verification_repair_updates_chunk_count(
    monkeypatch, tmp_path: Path
):
    service, _, vector_repo = build_test_service(monkeypatch, tmp_path)
    index_dir = tmp_path / "verification_idx"
    index_dir.mkdir()
    for name in ("default__vector_store.json", "graph_store.json", "index_store.json"):
        (index_dir / name).write_text("{}")
    index = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(index_dir),
        index_hash="hash",
        chunk_count=1,
    )
    vector_repo.records[1] = index
    monkeypatch.setattr(service, "_verify_index_files", lambda path: True)
    monkeypatch.setattr(service, "_get_chunk_count", lambda path: 5)
    assert service._perform_index_verification_repair(index) is True
    assert vector_repo.records[1].chunk_count == 5


def test_recover_corrupted_index_partial_repair(monkeypatch, tmp_path: Path):
    service, _, vector_repo = build_test_service(monkeypatch, tmp_path)
    index_dir = tmp_path / "idx-partial"
    index_dir.mkdir()
    index = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(index_dir),
        index_hash="hash",
        chunk_count=1,
    )
    vector_repo.records[1] = index

    analysis = {
        "corruption_detected": True,
        "corruption_type": ["metadata"],
        "corruption_severity": "moderate",
        "missing_files": [],
        "corrupted_files": [],
        "file_size_issues": [],
        "metadata_issues": ["stale"],
    }

    monkeypatch.setattr(service, "_analyze_index_corruption", lambda idx: analysis)
    monkeypatch.setattr(service, "_attempt_partial_index_repair", lambda idx: True)
    result = service.recover_corrupted_index(1)
    assert result["recovery_successful"] is True
    assert result["repair_actions"] == ["partial_repair"]


def test_recover_corrupted_index_no_corruption(monkeypatch, tmp_path: Path):
    service, _, vector_repo = build_test_service(monkeypatch, tmp_path)
    index_dir = tmp_path / "idx-clean"
    index_dir.mkdir()
    index = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(index_dir),
        index_hash="hash",
        chunk_count=1,
    )
    vector_repo.records[1] = index

    analysis = {
        "corruption_detected": False,
        "corruption_type": [],
        "corruption_severity": "none",
        "missing_files": [],
        "corrupted_files": [],
        "file_size_issues": [],
        "metadata_issues": [],
    }

    monkeypatch.setattr(service, "_analyze_index_corruption", lambda idx: analysis)
    result = service.recover_corrupted_index(1)
    assert result["recovery_successful"] is True
    assert result["repair_actions"] == ["no_action_needed"]


def test_recover_corrupted_index_missing_document(monkeypatch, tmp_path: Path):
    service, doc_repo, _ = build_test_service(monkeypatch, tmp_path)
    doc_repo.docs = {}
    result = service.recover_corrupted_index(99)
    assert result["error"] == "Document 99 not found"


def test_recover_corrupted_index_missing_vector(monkeypatch, tmp_path: Path):
    service, _, vector_repo = build_test_service(monkeypatch, tmp_path)
    vector_repo.records = {}
    result = service.recover_corrupted_index(1)
    assert result["error"] == "No index found for document 1"


def test_get_enhanced_cache_info_returns_error(monkeypatch, tmp_path: Path):
    service, _, _ = build_test_service(monkeypatch, tmp_path)

    def explode():
        raise RuntimeError("cache boom")

    monkeypatch.setattr(service, "get_cache_info", explode)
    info = service.get_enhanced_cache_info()
    assert info == {"error": "cache boom"}


def test_get_recovery_metrics_includes_health_and_db(monkeypatch, tmp_path: Path):
    service, _, vector_repo = build_test_service(monkeypatch, tmp_path)

    class DummyOrchestrator:
        def get_comprehensive_metrics(self):
            return {"base_metric": 1}

    class DummyHealth:
        def run_all_checks(self):
            return {"cpu": True, "memory": False}

    service.recovery_orchestrator = DummyOrchestrator()
    service.health_checker = DummyHealth()
    vector_repo.records[1] = VectorIndexModel(
        id=1,
        document_id=1,
        index_path=str(tmp_path / "idx"),
        index_hash="hash",
        chunk_count=2,
    )

    metrics = service.get_recovery_metrics()
    assert metrics["base_metric"] == 1
    assert metrics["service_metrics"]["vector_storage_path"]
    assert metrics["health_status"]["checks"] == {"cpu": True, "memory": False}
    assert metrics["database_metrics"]["total_indexes"] == 1


def test_perform_system_recovery_check_handles_degraded_and_corrupted(
    monkeypatch, tmp_path: Path
):
    service, _, _ = build_test_service(monkeypatch, tmp_path)

    class DummyHealth:
        def run_all_checks(self):
            return {"disk": False, "cpu": True}

    service.health_checker = DummyHealth()
    monkeypatch.setattr(service, "_identify_and_cleanup_orphaned_resources", lambda: 2)
    monkeypatch.setattr(
        service,
        "_identify_corrupted_indexes",
        lambda: [{"document_id": 1, "issues": ["missing_files"]}],
    )

    report = service.perform_system_recovery_check()
    assert report["overall_status"] == "critical"
    assert "Cleaned up 2 orphaned resources" in report["cleanup_actions"][0]
    assert report["recommendations"][0].startswith("Address failed health check")
    assert report["recommendations"][-1].startswith("Repair or rebuild")


def test_perform_system_recovery_check_handles_exception(monkeypatch, tmp_path: Path):
    service, _, _ = build_test_service(monkeypatch, tmp_path)

    class DummyHealth:
        def run_all_checks(self):
            raise RuntimeError("health boom")

    service.health_checker = DummyHealth()
    report = service.perform_system_recovery_check()
    assert report["overall_status"] == "critical"
    assert report["error"] == "health boom"
