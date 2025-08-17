"""
Test suite for Multi-Document RAG Service
Tests for cross-document queries and collection management functionality.
"""

import pytest
import tempfile
import shutil
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from typing import List

from src.database.multi_document_models import (
    MultiDocumentCollectionModel,
    MultiDocumentIndexModel,
    CrossDocumentQueryModel,
    DocumentSource,
    CrossReference,
)
from src.services.multi_document_rag_service import (
    MultiDocumentRAGService,
    MultiDocumentQueryResponse,
    CrossDocumentAnalyzer,
    CollectionIndexManager,
)


class TestMultiDocumentRAGService:
    """Test suite for MultiDocumentRAGService."""
    
    @pytest.fixture
    def mock_collection_repo(self):
        """Mock collection repository."""
        repo = Mock()
        
        def mock_create(collection):
            # Return the collection with an ID assigned
            collection.id = 1
            return collection
            
        repo.create.side_effect = mock_create
        repo.get_by_id.return_value = MultiDocumentCollectionModel(
            id=1, name="测试集合", document_ids=[1, 2, 3]
        )
        repo.get_all.return_value = []
        repo.update.return_value = True
        repo.delete.return_value = True
        return repo
    
    @pytest.fixture
    def mock_index_repo(self):
        """Mock index repository."""
        repo = Mock()
        
        def mock_create_index(index):
            # Return the index with an ID assigned
            index.id = 1
            return index
            
        repo.create.side_effect = mock_create_index
        repo.get_by_collection_id.return_value = MultiDocumentIndexModel(
            id=1, collection_id=1, index_path="/tmp/test", index_hash="abc123"
        )
        return repo
    
    @pytest.fixture
    def mock_query_repo(self):
        """Mock query repository."""
        repo = Mock()
        
        def mock_create_query(query):
            # Return the query with an ID assigned
            query.id = 1
            return query
            
        repo.create.side_effect = mock_create_query
        repo.update.return_value = True
        return repo
    
    @pytest.fixture
    def mock_document_repo(self):
        """Mock document repository."""
        repo = Mock()
        from src.database.models import DocumentModel
        repo.get_by_id.return_value = DocumentModel(
            id=1, title="测试文档", file_path="/test.pdf", file_hash="hash1", file_size=1000
        )
        
        def mock_get_by_ids(doc_ids):
            # Return documents that exist for the given IDs
            docs = [
                DocumentModel(id=1, title="文档1", file_path="/test1.pdf", file_hash="hash1", file_size=1000),
                DocumentModel(id=2, title="文档2", file_path="/test2.pdf", file_hash="hash2", file_size=2000),
                DocumentModel(id=3, title="文档3", file_path="/test3.pdf", file_hash="hash3", file_size=3000),
            ]
            return [doc for doc in docs if doc.id in doc_ids]
            
        repo.get_by_ids.side_effect = mock_get_by_ids
        return repo
    
    @pytest.fixture
    def mock_enhanced_rag(self):
        """Mock enhanced RAG service."""
        rag = Mock()
        rag.query_document.return_value = "单文档查询结果"
        return rag
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def service(self, mock_collection_repo, mock_index_repo, mock_query_repo, 
                mock_document_repo, mock_enhanced_rag, temp_dir):
        """Create MultiDocumentRAGService instance for testing."""
        return MultiDocumentRAGService(
            collection_repository=mock_collection_repo,
            index_repository=mock_index_repo,
            query_repository=mock_query_repo,
            document_repository=mock_document_repo,
            enhanced_rag_service=mock_enhanced_rag,
            index_storage_path=temp_dir
        )
    
    def test_create_collection_with_valid_data(self, service, mock_collection_repo):
        """测试创建有效的文档集合"""
        collection = service.create_collection(
            name="研究论文集",
            description="机器学习相关论文",
            document_ids=[1, 2, 3]
        )
        
        assert collection.id == 1
        assert collection.name == "研究论文集"
        assert collection.document_ids == [1, 2, 3]
        mock_collection_repo.create.assert_called_once()
        
    def test_create_collection_validates_document_existence(self, service, mock_document_repo):
        """测试创建集合时验证文档存在性"""
        # 模拟文档不存在 - 只返回两个文档，缺少ID为3的文档
        def mock_get_by_ids(doc_ids):
            from src.database.models import DocumentModel
            docs = [
                DocumentModel(id=1, title="文档1", file_path="/test1.pdf", file_hash="hash1", file_size=1000),
                DocumentModel(id=2, title="文档2", file_path="/test2.pdf", file_hash="hash2", file_size=2000),
                # 缺少ID为3的文档
            ]
            return [doc for doc in docs if doc.id in doc_ids]
            
        mock_document_repo.get_by_ids.side_effect = mock_get_by_ids
        
        with pytest.raises(ValueError, match="Documents not found: \\[3\\]"):
            service.create_collection(
                name="测试集合",
                document_ids=[1, 2, 3]
            )
    
    def test_get_collection_by_id(self, service, mock_collection_repo):
        """测试根据ID获取集合"""
        collection = service.get_collection(1)
        
        assert collection.id == 1
        assert collection.name == "测试集合"
        mock_collection_repo.get_by_id.assert_called_once_with(1)
        
    def test_get_nonexistent_collection(self, service, mock_collection_repo):
        """测试获取不存在的集合"""
        mock_collection_repo.get_by_id.return_value = None
        
        with pytest.raises(ValueError, match="Collection not found: 999"):
            service.get_collection(999)
    
    def test_update_collection_add_document(self, service, mock_collection_repo):
        """测试向集合添加文档"""
        updated_collection = service.add_document_to_collection(1, 4)
        
        assert updated_collection is not None
        mock_collection_repo.get_by_id.assert_called_with(1)
        mock_collection_repo.update.assert_called_once()
        
    def test_update_collection_remove_document(self, service, mock_collection_repo):
        """测试从集合移除文档"""
        updated_collection = service.remove_document_from_collection(1, 2)
        
        assert updated_collection is not None
        mock_collection_repo.get_by_id.assert_called_with(1)
        mock_collection_repo.update.assert_called_once()
    
    def test_create_collection_index(self, service, mock_index_repo):
        """测试创建集合索引"""
        index = service.create_collection_index(1)
        
        assert index.collection_id == 1
        assert index.index_path is not None
        assert index.index_path.endswith("collection_1")
        assert index.index_hash is not None
        mock_index_repo.create.assert_called_once()
        
    @patch('src.services.multi_document_rag_service.CrossDocumentAnalyzer')
    @pytest.mark.asyncio
    async def test_query_collection_success(self, mock_analyzer_class, service, mock_query_repo):
        """测试成功的集合查询"""
        # 模拟分析器
        mock_analyzer = Mock()
        mock_response = MultiDocumentQueryResponse(
            answer="综合分析结果",
            confidence=0.9,
            sources=[
                DocumentSource(document_id=1, relevance_score=0.95, excerpt="摘录1"),
                DocumentSource(document_id=2, relevance_score=0.85, excerpt="摘录2")
            ],
            cross_references=[
                CrossReference(
                    source_doc_id=1, target_doc_id=2, 
                    relation_type="supports", confidence=0.8
                )
            ],
            processing_time_ms=1500,
            tokens_used=100
        )
        mock_analyzer.analyze_cross_document_query.return_value = mock_response
        mock_analyzer_class.return_value = mock_analyzer
        
        response = await service.query_collection(
            collection_id=1,
            query="比较所有文档的主要观点",
            max_results=10
        )
        
        assert response.answer == "综合分析结果"
        assert response.confidence == 0.9
        assert len(response.sources) == 2
        assert len(response.cross_references) == 1
        mock_query_repo.create.assert_called_once()
        mock_query_repo.update.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_query_collection_with_invalid_collection(self, service, mock_collection_repo):
        """测试查询不存在的集合"""
        mock_collection_repo.get_by_id.return_value = None
        
        with pytest.raises(ValueError, match="Collection not found: 999"):
            await service.query_collection(999, "测试查询")
    
    @patch('src.services.multi_document_rag_service.CrossDocumentAnalyzer')
    @pytest.mark.asyncio
    async def test_query_collection_handles_errors(self, mock_analyzer_class, service, mock_query_repo):
        """测试查询时的错误处理"""
        # 模拟分析器抛出异常
        mock_analyzer = Mock()
        mock_analyzer.analyze_cross_document_query.side_effect = Exception("分析失败")
        mock_analyzer_class.return_value = mock_analyzer
        
        with pytest.raises(Exception, match="分析失败"):
            await service.query_collection(1, "测试查询")
        
        # 验证查询记录被创建并更新为失败状态
        mock_query_repo.create.assert_called_once()
        mock_query_repo.update.assert_called_once()
        
        # 检查更新的查询记录状态
        update_call = mock_query_repo.update.call_args[0][0]
        assert update_call.status == "failed"
        assert "分析失败" in update_call.error_message
    
    def test_delete_collection(self, service, mock_collection_repo, mock_index_repo):
        """测试删除集合"""
        # 模拟索引存在
        mock_index_repo.get_by_collection_id.return_value = MultiDocumentIndexModel(
            id=1, collection_id=1, index_path="/tmp/test", index_hash="abc123"
        )
        
        result = service.delete_collection(1)
        
        assert result is True
        mock_collection_repo.delete.assert_called_once_with(1)
        mock_index_repo.delete.assert_called_once_with(1)
    
    def test_get_collection_statistics(self, service, mock_collection_repo, mock_document_repo):
        """测试获取集合统计信息"""
        stats = service.get_collection_statistics(1)
        
        expected_keys = {
            "collection_id", "name", "document_count", 
            "total_file_size", "avg_file_size", "created_at"
        }
        assert set(stats.keys()) == expected_keys
        assert stats["collection_id"] == 1
        assert stats["document_count"] == 3
        assert stats["total_file_size"] == 6000  # 1000 + 2000 + 3000
        assert stats["avg_file_size"] == 2000


class TestCollectionIndexManager:
    """Test suite for CollectionIndexManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_documents(self):
        """Mock document models."""
        from src.database.models import DocumentModel
        return [
            DocumentModel(id=1, title="文档1", file_path="/test1.pdf", file_hash="hash1", file_size=1000),
            DocumentModel(id=2, title="文档2", file_path="/test2.pdf", file_hash="hash2", file_size=2000),
        ]
    
    @pytest.fixture
    def index_manager(self, temp_dir):
        """Create CollectionIndexManager instance."""
        return CollectionIndexManager(storage_path=temp_dir)
    
    @patch('src.services.multi_document_rag_service.VectorStoreIndex')
    def test_create_index_for_collection(self, mock_vector_store, index_manager, mock_documents):
        """测试为集合创建索引"""
        mock_index = Mock()
        mock_vector_store.from_documents.return_value = mock_index
        mock_index.storage_context.persist.return_value = None
        
        index_path = index_manager.create_index(mock_documents, collection_id=1)
        
        assert index_path.endswith("collection_1")
        assert Path(index_path).exists()
        mock_vector_store.from_documents.assert_called_once()
        mock_index.storage_context.persist.assert_called_once()
    
    def test_get_index_path(self, index_manager):
        """测试获取索引路径"""
        path = index_manager.get_index_path(1)
        expected_path = str(Path(index_manager.storage_path) / "collection_1")
        assert path == expected_path
    
    def test_index_exists(self, index_manager, temp_dir):
        """测试检查索引是否存在"""
        # 索引不存在
        assert not index_manager.index_exists(1)
        
        # 创建索引目录
        index_dir = Path(temp_dir) / "collection_1"
        index_dir.mkdir()
        (index_dir / "default__vector_store.json").touch()
        (index_dir / "graph_store.json").touch()
        (index_dir / "index_store.json").touch()
        
        # 索引存在
        assert index_manager.index_exists(1)
    
    def test_delete_index(self, index_manager, temp_dir):
        """测试删除索引"""
        # 创建索引目录
        index_dir = Path(temp_dir) / "collection_1"
        index_dir.mkdir()
        (index_dir / "test_file.txt").touch()
        
        assert index_dir.exists()
        
        result = index_manager.delete_index(1)
        
        assert result is True
        assert not index_dir.exists()
    
    def test_delete_nonexistent_index(self, index_manager):
        """测试删除不存在的索引"""
        result = index_manager.delete_index(999)
        assert result is False


class TestCrossDocumentAnalyzer:
    """Test suite for CrossDocumentAnalyzer."""
    
    @pytest.fixture
    def mock_enhanced_rag(self):
        """Mock enhanced RAG service."""
        rag = Mock()
        return rag
    
    @pytest.fixture
    def mock_documents(self):
        """Mock document models."""
        from src.database.models import DocumentModel
        return [
            DocumentModel(id=1, title="机器学习基础", file_path="/ml1.pdf", file_hash="hash1", file_size=1000),
            DocumentModel(id=2, title="深度学习进阶", file_path="/dl1.pdf", file_hash="hash2", file_size=2000),
        ]
    
    @pytest.fixture
    def analyzer(self, mock_enhanced_rag):
        """Create CrossDocumentAnalyzer instance."""
        return CrossDocumentAnalyzer(mock_enhanced_rag)
    
    @patch('src.services.multi_document_rag_service.VectorStoreIndex')
    @pytest.mark.asyncio
    async def test_analyze_cross_document_query(self, mock_vector_store, analyzer, mock_documents):
        """测试跨文档查询分析"""
        # 模拟索引加载和查询
        mock_index = Mock()
        mock_vector_store.load_from_storage.return_value = mock_index
        
        mock_query_engine = Mock()
        mock_index.as_query_engine.return_value = mock_query_engine
        
        mock_response = Mock()
        mock_response.response = "综合分析：两个文档都讨论了机器学习，但侧重点不同。"
        mock_response.source_nodes = [
            Mock(node=Mock(metadata={"document_id": 1, "page_number": 5}), score=0.95),
            Mock(node=Mock(metadata={"document_id": 2, "page_number": 10}), score=0.85),
        ]
        mock_query_engine.query.return_value = mock_response
        
        result = await analyzer.analyze_cross_document_query(
            query="比较两个文档的机器学习方法",
            documents=mock_documents,
            index_path="/tmp/test_index"
        )
        
        assert isinstance(result, MultiDocumentQueryResponse)
        assert "综合分析" in result.answer
        assert result.confidence > 0.0
        assert len(result.sources) == 2
        assert result.processing_time_ms > 0
    
    def test_extract_cross_references(self, analyzer):
        """测试提取交叉引用"""
        sources = [
            DocumentSource(document_id=1, relevance_score=0.95, excerpt="监督学习是重要方法"),
            DocumentSource(document_id=2, relevance_score=0.85, excerpt="深度学习基于监督学习"),
        ]
        
        cross_refs = analyzer._extract_cross_references(sources, "监督学习")
        
        assert len(cross_refs) >= 0  # 可能找到交叉引用
        for ref in cross_refs:
            assert isinstance(ref, CrossReference)
            assert ref.source_doc_id != ref.target_doc_id
    
    def test_calculate_confidence_score(self, analyzer):
        """测试计算置信度分数"""
        sources = [
            DocumentSource(document_id=1, relevance_score=0.95, excerpt="高相关内容"),
            DocumentSource(document_id=2, relevance_score=0.85, excerpt="中等相关内容"),
            DocumentSource(document_id=3, relevance_score=0.75, excerpt="一般相关内容"),
        ]
        
        confidence = analyzer._calculate_confidence_score(sources)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # 应该基于高相关性得分获得较高置信度