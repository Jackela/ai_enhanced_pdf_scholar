"""
Test suite for multi-document RAG models
Tests for data models supporting cross-document queries and collections.
"""


import pytest

from src.database.multi_document_models import (
    CrossDocumentQueryModel,
    CrossReference,
    DocumentSource,
    MultiDocumentCollectionModel,
    MultiDocumentIndexModel,
)


class TestMultiDocumentCollectionModel:
    """Test suite for MultiDocumentCollectionModel."""

    def test_create_collection_with_valid_data(self):
        """测试创建有效的文档集合"""
        collection = MultiDocumentCollectionModel(
            name="研究论文集",
            description="机器学习相关论文",
            document_ids=[1, 2, 3]
        )

        assert collection.name == "研究论文集"
        assert collection.description == "机器学习相关论文"
        assert collection.document_ids == [1, 2, 3]
        assert collection.document_count == 3
        assert collection.created_at is not None
        assert collection.updated_at is not None
        assert collection.id is None  # Not set until inserted

    def test_create_collection_minimal_data(self):
        """测试创建最小数据集合"""
        collection = MultiDocumentCollectionModel(
            name="最小集合",
            document_ids=[1]
        )

        assert collection.name == "最小集合"
        assert collection.description is None
        assert collection.document_ids == [1]
        assert collection.document_count == 1

    def test_collection_validation_empty_name(self):
        """测试空名称验证"""
        with pytest.raises(ValueError, match="Collection name cannot be empty"):
            MultiDocumentCollectionModel(
                name="",
                document_ids=[1]
            )

    def test_collection_validation_empty_documents(self):
        """测试空文档列表验证"""
        with pytest.raises(ValueError, match="Collection must contain at least one document"):
            MultiDocumentCollectionModel(
                name="空集合",
                document_ids=[]
            )

    def test_collection_validation_invalid_document_ids(self):
        """测试无效文档ID验证"""
        with pytest.raises(ValueError, match="All document IDs must be positive"):
            MultiDocumentCollectionModel(
                name="无效ID集合",
                document_ids=[1, 0, -1]
            )

    def test_add_document_to_collection(self):
        """测试向集合添加文档"""
        collection = MultiDocumentCollectionModel(
            name="测试集合",
            document_ids=[1, 2]
        )

        collection.add_document(3)
        assert collection.document_ids == [1, 2, 3]
        assert collection.document_count == 3

    def test_add_duplicate_document(self):
        """测试添加重复文档"""
        collection = MultiDocumentCollectionModel(
            name="测试集合",
            document_ids=[1, 2]
        )

        collection.add_document(2)  # 重复文档
        assert collection.document_ids == [1, 2]
        assert collection.document_count == 2

    def test_remove_document_from_collection(self):
        """测试从集合移除文档"""
        collection = MultiDocumentCollectionModel(
            name="测试集合",
            document_ids=[1, 2, 3]
        )

        result = collection.remove_document(2)
        assert result is True
        assert collection.document_ids == [1, 3]
        assert collection.document_count == 2

    def test_remove_nonexistent_document(self):
        """测试移除不存在的文档"""
        collection = MultiDocumentCollectionModel(
            name="测试集合",
            document_ids=[1, 2]
        )

        result = collection.remove_document(3)
        assert result is False
        assert collection.document_ids == [1, 2]

    def test_remove_last_document_fails(self):
        """测试移除最后一个文档失败"""
        collection = MultiDocumentCollectionModel(
            name="测试集合",
            document_ids=[1]
        )

        with pytest.raises(ValueError, match="Cannot remove the last document"):
            collection.remove_document(1)

    def test_from_database_row(self):
        """测试从数据库行创建对象"""
        row = {
            "id": 1,
            "name": "测试集合",
            "description": "测试描述",
            "document_ids": "[1, 2, 3]",
            "document_count": 3,
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T11:00:00"
        }

        collection = MultiDocumentCollectionModel.from_database_row(row)
        assert collection.id == 1
        assert collection.name == "测试集合"
        assert collection.description == "测试描述"
        assert collection.document_ids == [1, 2, 3]
        assert collection.document_count == 3

    def test_to_database_dict(self):
        """测试转换为数据库字典"""
        collection = MultiDocumentCollectionModel(
            name="测试集合",
            description="测试描述",
            document_ids=[1, 2, 3]
        )
        collection.id = 1

        db_dict = collection.to_database_dict()
        expected_keys = {
            "id", "name", "description", "document_ids",
            "document_count", "created_at", "updated_at"
        }
        assert set(db_dict.keys()) == expected_keys
        assert db_dict["document_ids"] == "[1, 2, 3]"


class TestMultiDocumentIndexModel:
    """Test suite for MultiDocumentIndexModel."""

    def test_create_index_with_valid_data(self):
        """测试创建有效的多文档索引"""
        index = MultiDocumentIndexModel(
            collection_id=1,
            index_path="/path/to/index",
            index_hash="abc123",
            embedding_model="text-embedding-ada-002"
        )

        assert index.collection_id == 1
        assert index.index_path == "/path/to/index"
        assert index.index_hash == "abc123"
        assert index.embedding_model == "text-embedding-ada-002"
        assert index.chunk_count is None
        assert index.created_at is not None

    def test_index_validation_invalid_collection_id(self):
        """测试无效集合ID验证"""
        with pytest.raises(ValueError, match="Collection ID must be positive"):
            MultiDocumentIndexModel(
                collection_id=0,
                index_path="/path/to/index",
                index_hash="abc123"
            )

    def test_index_validation_empty_path(self):
        """测试空路径验证"""
        with pytest.raises(ValueError, match="Index path cannot be empty"):
            MultiDocumentIndexModel(
                collection_id=1,
                index_path="",
                index_hash="abc123"
            )

    def test_index_validation_empty_hash(self):
        """测试空哈希验证"""
        with pytest.raises(ValueError, match="Index hash cannot be empty"):
            MultiDocumentIndexModel(
                collection_id=1,
                index_path="/path/to/index",
                index_hash=""
            )


class TestCrossDocumentQueryModel:
    """Test suite for CrossDocumentQueryModel."""

    def test_create_query_with_valid_data(self):
        """测试创建有效的跨文档查询"""
        query = CrossDocumentQueryModel(
            collection_id=1,
            query_text="比较不同论文的研究方法",
            user_id="user123"
        )

        assert query.collection_id == 1
        assert query.query_text == "比较不同论文的研究方法"
        assert query.user_id == "user123"
        assert query.created_at is not None
        assert query.status == "pending"

    def test_query_validation_invalid_collection_id(self):
        """测试无效集合ID验证"""
        with pytest.raises(ValueError, match="Collection ID must be positive"):
            CrossDocumentQueryModel(
                collection_id=0,
                query_text="测试查询"
            )

    def test_query_validation_empty_text(self):
        """测试空查询文本验证"""
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            CrossDocumentQueryModel(
                collection_id=1,
                query_text=""
            )

    def test_query_set_response(self):
        """测试设置查询响应"""
        query = CrossDocumentQueryModel(
            collection_id=1,
            query_text="测试查询"
        )

        sources = [
            DocumentSource(document_id=1, relevance_score=0.95, excerpt="摘录1"),
            DocumentSource(document_id=2, relevance_score=0.85, excerpt="摘录2")
        ]

        cross_refs = [
            CrossReference(
                source_doc_id=1, target_doc_id=2,
                relation_type="supports", confidence=0.8
            )
        ]

        query.set_response(
            answer="综合分析结果",
            confidence=0.9,
            sources=sources,
            cross_references=cross_refs
        )

        assert query.status == "completed"
        assert query.response_text == "综合分析结果"
        assert query.confidence_score == 0.9
        assert len(query.sources) == 2
        assert len(query.cross_references) == 1

    def test_query_set_error(self):
        """测试设置查询错误"""
        query = CrossDocumentQueryModel(
            collection_id=1,
            query_text="测试查询"
        )

        query.set_error("处理失败")

        assert query.status == "failed"
        assert query.error_message == "处理失败"


class TestDocumentSource:
    """Test suite for DocumentSource dataclass."""

    def test_create_document_source(self):
        """测试创建文档来源"""
        source = DocumentSource(
            document_id=1,
            relevance_score=0.95,
            excerpt="这是相关摘录",
            page_number=10
        )

        assert source.document_id == 1
        assert source.relevance_score == 0.95
        assert source.excerpt == "这是相关摘录"
        assert source.page_number == 10

    def test_document_source_validation_invalid_id(self):
        """测试无效文档ID验证"""
        with pytest.raises(ValueError, match="Document ID must be positive"):
            DocumentSource(
                document_id=0,
                relevance_score=0.95,
                excerpt="摘录"
            )

    def test_document_source_validation_invalid_score(self):
        """测试无效相关性分数验证"""
        with pytest.raises(ValueError, match="Relevance score must be between 0.0 and 1.0"):
            DocumentSource(
                document_id=1,
                relevance_score=1.5,
                excerpt="摘录"
            )


class TestCrossReference:
    """Test suite for CrossReference dataclass."""

    def test_create_cross_reference(self):
        """测试创建交叉引用"""
        cross_ref = CrossReference(
            source_doc_id=1,
            target_doc_id=2,
            relation_type="supports",
            confidence=0.8,
            description="支持该观点"
        )

        assert cross_ref.source_doc_id == 1
        assert cross_ref.target_doc_id == 2
        assert cross_ref.relation_type == "supports"
        assert cross_ref.confidence == 0.8
        assert cross_ref.description == "支持该观点"

    def test_cross_reference_validation_invalid_ids(self):
        """测试无效文档ID验证"""
        with pytest.raises(ValueError, match="Document IDs must be positive"):
            CrossReference(
                source_doc_id=0,
                target_doc_id=2,
                relation_type="supports"
            )

    def test_cross_reference_validation_same_document(self):
        """测试相同文档验证"""
        with pytest.raises(ValueError, match="Source and target documents cannot be the same"):
            CrossReference(
                source_doc_id=1,
                target_doc_id=1,
                relation_type="supports"
            )

    def test_cross_reference_validation_invalid_confidence(self):
        """测试无效置信度验证"""
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            CrossReference(
                source_doc_id=1,
                target_doc_id=2,
                relation_type="supports",
                confidence=1.5
            )
