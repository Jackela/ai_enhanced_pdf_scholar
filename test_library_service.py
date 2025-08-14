#!/usr/bin/env python3
"""
文档库服务测试 - 测试Repository层和Service层

专门测试新开发的文档库管理功能，包括Repository模式和业务逻辑。
"""

import sys
import tempfile
import sqlite3
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_document_repository():
    """测试文档Repository"""
    print("🧪 测试文档Repository...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        from database.models import DocumentModel
        from repositories.document_repository import DocumentRepository

        # 初始化数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()

        # 创建Repository
        doc_repo = DocumentRepository(db)

        # 创建测试文档
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(b"test PDF content")
            pdf_path = temp_pdf.name

        # 测试创建文档
        doc = DocumentModel.from_file(pdf_path, "test_hash", "Test Document")
        created_doc = doc_repo.create(doc)

        assert created_doc.id is not None
        assert created_doc.title == "Test Document"
        print(f"  ✅ 文档创建成功，ID: {created_doc.id}")

        # 测试根据哈希查找
        found_doc = doc_repo.find_by_file_hash("test_hash")
        assert found_doc is not None
        assert found_doc.id == created_doc.id
        print("  ✅ 根据哈希查找成功")

        # 测试标题搜索
        search_results = doc_repo.search_by_title("Test")
        assert len(search_results) == 1
        assert search_results[0].title == "Test Document"
        print("  ✅ 标题搜索成功")

        # 测试更新访问时间
        success = doc_repo.update_access_time(created_doc.id)
        assert success is True
        print("  ✅ 访问时间更新成功")

        # 测试统计信息
        stats = doc_repo.get_statistics()
        assert stats["total_documents"] == 1
        assert "size_stats" in stats
        print(f"  📊 统计信息: {stats['total_documents']} 个文档")

        # 清理
        Path(pdf_path).unlink(missing_ok=True)
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 文档Repository测试通过")
        return True

    except Exception as e:
        print(f"❌ 文档Repository测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_vector_repository():
    """测试向量索引Repository"""
    print("🧪 测试向量索引Repository...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        from database.models import DocumentModel, VectorIndexModel
        from repositories.document_repository import DocumentRepository
        from repositories.vector_repository import VectorIndexRepository

        # 初始化数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()

        # 创建Repositories
        doc_repo = DocumentRepository(db)
        vector_repo = VectorIndexRepository(db)

        # 创建测试文档
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(b"test PDF content")
            pdf_path = temp_pdf.name

        doc = DocumentModel.from_file(pdf_path, "test_hash", "Test Document")
        created_doc = doc_repo.create(doc)

        # 创建向量索引
        with tempfile.TemporaryDirectory() as temp_dir:
            vector_index = VectorIndexModel(
                document_id=created_doc.id,
                index_path=temp_dir,
                index_hash="vector_hash_123",
                chunk_count=10
            )

            created_index = vector_repo.create(vector_index)
            assert created_index.id is not None
            print(f"  ✅ 向量索引创建成功，ID: {created_index.id}")

            # 测试根据文档ID查找
            found_index = vector_repo.find_by_document_id(created_doc.id)
            assert found_index is not None
            assert found_index.document_id == created_doc.id
            print("  ✅ 根据文档ID查找成功")

            # 测试根据索引哈希查找
            found_by_hash = vector_repo.find_by_index_hash("vector_hash_123")
            assert found_by_hash is not None
            assert found_by_hash.index_hash == "vector_hash_123"
            print("  ✅ 根据索引哈希查找成功")

            # 测试带文档信息的查找
            with_docs = vector_repo.find_all_with_documents()
            assert len(with_docs) == 1
            assert with_docs[0]["document_title"] == "Test Document"
            print("  ✅ 带文档信息查找成功")

            # 测试统计信息
            stats = vector_repo.get_index_statistics()
            assert stats["total_indexes"] == 1
            print(f"  📊 索引统计: {stats['total_indexes']} 个索引")

        # 清理
        Path(pdf_path).unlink(missing_ok=True)
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 向量索引Repository测试通过")
        return True

    except Exception as e:
        print(f"❌ 向量索引Repository测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_document_library_service():
    """测试文档库服务"""
    print("🧪 测试文档库服务...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        # 直接导入服务层模块
        sys.path.insert(0, str(Path(__file__).parent / "src" / "services"))
        from document_library_service import DocumentLibraryService, DuplicateDocumentError

        # 初始化数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()

        # 创建服务
        library_service = DocumentLibraryService(db)

        # 创建测试PDF文件
        try:
            import fitz
            temp_pdf_fd, pdf_path = tempfile.mkstemp(suffix='.pdf')
            import os
            os.close(temp_pdf_fd)

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), "Test library service content")
            doc.save(pdf_path)
            doc.close()
            print("  📄 测试PDF创建完成")
        except ImportError:
            # 如果没有PyMuPDF，创建假PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(b"fake PDF content")
                pdf_path = temp_pdf.name
            print("  📄 测试文件创建完成（无PyMuPDF）")

        # 测试文档导入
        imported_doc = library_service.import_document(pdf_path, "Test Library Document")
        assert imported_doc.id is not None
        assert imported_doc.title == "Test Library Document"
        print(f"  ✅ 文档导入成功，ID: {imported_doc.id}")

        # 测试重复导入检测
        try:
            library_service.import_document(pdf_path, "Duplicate Document")
            assert False, "应该抛出重复文档异常"
        except DuplicateDocumentError:
            print("  ✅ 重复文档检测成功")

        # 测试覆盖重复文档
        overwritten_doc = library_service.import_document(
            pdf_path,
            "Overwritten Document",
            overwrite_duplicates=True
        )
        assert overwritten_doc.id == imported_doc.id
        assert overwritten_doc.title == "Overwritten Document"
        print("  ✅ 文档覆盖成功")

        # 测试获取文档列表
        docs = library_service.get_documents()
        assert len(docs) == 1
        assert docs[0].title == "Overwritten Document"
        print("  ✅ 获取文档列表成功")

        # 测试按ID获取文档
        doc_by_id = library_service.get_document_by_id(imported_doc.id)
        assert doc_by_id is not None
        assert doc_by_id.id == imported_doc.id
        print("  ✅ 按ID获取文档成功")

        # 测试搜索
        search_results = library_service.get_documents(search_query="Overwritten")
        assert len(search_results) == 1
        print("  ✅ 文档搜索成功")

        # 测试统计信息
        stats = library_service.get_library_statistics()
        assert "documents" in stats
        assert stats["documents"]["total_documents"] == 1
        print(f"  📊 库统计: {stats['documents']['total_documents']} 个文档")

        # 测试完整性验证
        integrity = library_service.verify_document_integrity(imported_doc.id)
        assert integrity["exists"] is True
        print(f"  🔍 完整性检查: {'健康' if integrity['is_healthy'] else '有问题'}")

        # 测试删除文档
        deleted = library_service.delete_document(imported_doc.id)
        assert deleted is True
        print("  ✅ 文档删除成功")

        # 验证删除
        deleted_doc = library_service.get_document_by_id(imported_doc.id)
        assert deleted_doc is None
        print("  ✅ 删除验证成功")

        # 清理
        Path(pdf_path).unlink(missing_ok=True)
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 文档库服务测试通过")
        return True

    except Exception as e:
        print(f"❌ 文档库服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_duplicate_detection():
    """测试重复文档检测功能"""
    print("🧪 测试重复文档检测...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        # 直接导入服务层模块
        sys.path.insert(0, str(Path(__file__).parent / "src" / "services"))
        from document_library_service import DocumentLibraryService

        # 初始化数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()

        library_service = DocumentLibraryService(db)

        # 创建多个测试文件
        test_files = []

        try:
            import fitz

            # 创建相同大小的文件
            for i in range(3):
                temp_pdf_fd, pdf_path = tempfile.mkstemp(suffix='.pdf')
                import os
                os.close(temp_pdf_fd)

                doc = fitz.open()
                page = doc.new_page()
                page.insert_text((100, 100), f"Document {i} with same size")
                doc.save(pdf_path)
                doc.close()

                test_files.append(pdf_path)

                # 导入文档
                library_service.import_document(pdf_path, f"Document {i}")

            print(f"  📄 创建了 {len(test_files)} 个测试文档")

        except ImportError:
            print("  ⚠️ PyMuPDF不可用，跳过详细重复检测测试")
            return True

        # 测试重复检测
        duplicates = library_service.find_duplicate_documents()
        print(f"  🔍 发现 {len(duplicates)} 组潜在重复文档")

        # 显示重复组
        for criteria, docs in duplicates:
            print(f"    📊 {criteria}: {len(docs)} 个文档")
            for doc in docs:
                print(f"      - {doc.title} (ID: {doc.id})")

        # 清理
        for pdf_path in test_files:
            Path(pdf_path).unlink(missing_ok=True)

        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 重复文档检测测试通过")
        return True

    except Exception as e:
        print(f"❌ 重复文档检测测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_library_cleanup():
    """测试库清理功能"""
    print("🧪 测试库清理功能...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        # 直接导入服务层模块
        sys.path.insert(0, str(Path(__file__).parent / "src" / "services"))
        from document_library_service import DocumentLibraryService
        from repositories.vector_repository import VectorIndexRepository
        from database.models import VectorIndexModel

        # 初始化数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()

        library_service = DocumentLibraryService(db)
        vector_repo = VectorIndexRepository(db)

        # 临时禁用外键约束来创建孤立索引
        db.execute("PRAGMA foreign_keys = OFF")

        # 创建孤立的向量索引（没有对应文档）
        orphaned_index = VectorIndexModel(
            document_id=999,  # 不存在的文档ID
            index_path="/fake/path",
            index_hash="orphaned_hash"
        )
        vector_repo.create(orphaned_index)

        # 重新启用外键约束
        db.execute("PRAGMA foreign_keys = ON")
        print("  🗑️ 创建了孤立向量索引")

        # 测试清理前统计
        stats_before = library_service.get_library_statistics()
        orphaned_before = stats_before["vector_indexes"]["orphaned_count"]
        print(f"  📊 清理前：{orphaned_before} 个孤立索引")

        # 执行清理
        cleanup_results = library_service.cleanup_library()
        print(f"  🧹 清理结果: {cleanup_results}")

        # 测试清理后统计
        stats_after = library_service.get_library_statistics()
        orphaned_after = stats_after["vector_indexes"]["orphaned_count"]
        print(f"  📊 清理后：{orphaned_after} 个孤立索引")

        assert orphaned_after < orphaned_before
        print("  ✅ 孤立索引清理成功")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 库清理功能测试通过")
        return True

    except Exception as e:
        print(f"❌ 库清理功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有文档库服务测试"""
    print("🚀 开始测试文档库服务功能...\n")

    tests = [
        test_document_repository,
        test_vector_repository,
        test_document_library_service,
        test_duplicate_detection,
        test_library_cleanup
    ]

    passed = 0
    total = len(tests)

    for test_func in tests:
        if test_func():
            passed += 1
        print()  # 空行分隔

    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有文档库服务测试通过！")
        print("\n📋 第二阶段完成：")
        print("✅ Repository层（数据访问）")
        print("✅ Service层（业务逻辑）")
        print("✅ 重复检测功能")
        print("✅ 库管理功能")
        print("\n🚀 下一步：创建UI组件和控制器")
        return True
    else:
        print("⚠️ 部分测试失败，需要修复。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)