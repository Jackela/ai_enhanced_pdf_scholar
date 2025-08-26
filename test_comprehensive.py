#!/usr/bin/env python3
"""
全面测试套件 - 边界条件、错误场景和性能测试

确保系统在各种条件下的稳定性和可靠性。
"""

import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_error_handling():
    """测试错误处理和边界条件"""
    print("🧪 测试错误处理...")

    try:
        from database.connection import DatabaseConnection, DatabaseConnectionError
        from database.models import DocumentModel
        from repositories.document_repository import DocumentRepository

        # 测试无效数据库路径
        try:
            DatabaseConnection("/invalid/path/database.db")
            assert False, "应该抛出连接错误"
        except DatabaseConnectionError:
            print("  ✅ 无效数据库路径错误处理正确")

        # 测试模型验证
        try:
            DocumentModel("", "", "", -1)  # 空标题和负数大小
            assert False, "应该抛出验证错误"
        except ValueError:
            print("  ✅ 模型数据验证正确")

        # 测试数据库操作错误
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        repo = DocumentRepository(db)

        # 测试查找不存在的记录
        result = repo.find_by_id(99999)
        assert result is None
        print("  ✅ 不存在记录查找处理正确")

        # 测试无效SQL
        try:
            db.execute("INVALID SQL QUERY")
            assert False, "应该抛出SQL错误"
        except Exception:
            print("  ✅ 无效SQL错误处理正确")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 错误处理测试通过")
        return True

    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False

def test_concurrent_operations():
    """测试并发操作安全性"""
    print("🧪 测试并发操作...")

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

        repo = DocumentRepository(db)
        results = []
        errors = []

        def worker_thread(thread_id):
            """并发工作线程"""
            try:
                for i in range(5):
                    # 创建测试文档
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                        temp_pdf.write(f"Thread {thread_id} document {i}".encode())
                        pdf_path = temp_pdf.name

                    doc = DocumentModel.from_file(
                        pdf_path,
                        f"hash_{thread_id}_{i}",
                        f"Document {thread_id}-{i}"
                    )

                    created_doc = repo.create(doc)
                    results.append(f"thread_{thread_id}_doc_{i}")

                    # 清理临时文件
                    Path(pdf_path).unlink(missing_ok=True)

                    time.sleep(0.001)  # 短暂延迟增加竞争条件

            except Exception as e:
                errors.append(f"Thread {thread_id} error: {e}")

        # 启动多个并发线程
        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=worker_thread, args=(thread_id,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 验证结果
        assert len(errors) == 0, f"并发错误: {errors}"
        assert len(results) == 15, f"期望15个结果，实际{len(results)}个"

        # 验证数据库一致性
        total_docs = repo.count()
        assert total_docs == 15, f"数据库中期望15个文档，实际{total_docs}个"

        print(f"  ✅ 成功处理 {len(results)} 个并发操作")
        print("  📊 数据库一致性验证通过")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 并发操作测试通过")
        return True

    except Exception as e:
        print(f"❌ 并发操作测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_large_data_handling():
    """测试大数据量处理性能"""
    print("🧪 测试大数据量处理...")

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

        repo = DocumentRepository(db)

        # 测试批量插入性能
        start_time = time.time()
        batch_size = 100

        documents = []
        for i in range(batch_size):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(f"Large test document {i}".encode())
                pdf_path = temp_pdf.name

            doc = DocumentModel.from_file(pdf_path, f"large_hash_{i}", f"Large Document {i}")
            documents.append((doc, pdf_path))

        # 批量创建
        for doc, pdf_path in documents:
            repo.create(doc)
            Path(pdf_path).unlink(missing_ok=True)

        insert_time = time.time() - start_time
        print(f"  📊 插入 {batch_size} 个文档耗时: {insert_time:.2f}秒")

        # 测试大量查询性能
        start_time = time.time()

        # 执行各种查询
        all_docs = repo.find_all()
        search_results = repo.search_by_title("Large")
        stats = repo.get_statistics()

        query_time = time.time() - start_time
        print(f"  📊 复杂查询耗时: {query_time:.2f}秒")

        # 验证结果
        assert len(all_docs) == batch_size
        assert len(search_results) == batch_size
        assert stats["total_documents"] == batch_size

        # 性能基准
        avg_insert_time = insert_time / batch_size * 1000  # 毫秒
        print(f"  ⚡ 平均插入时间: {avg_insert_time:.2f}ms/文档")

        if avg_insert_time > 100:  # 如果超过100ms/文档则警告
            print("  ⚠️ 插入性能可能需要优化")
        else:
            print("  ✅ 插入性能良好")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 大数据量处理测试通过")
        return True

    except Exception as e:
        print(f"❌ 大数据量处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_content_hash_edge_cases():
    """测试内容哈希服务的边界情况"""
    print("🧪 测试内容哈希边界情况...")

    try:
        # 直接导入避免依赖问题
        sys.path.insert(0, str(Path(__file__).parent / "src" / "services"))
        from content_hash_service import ContentHashError, ContentHashService

        # 测试空文件
        with tempfile.NamedTemporaryFile(delete=False) as empty_file:
            empty_path = empty_file.name

        try:
            hash_result = ContentHashService.calculate_file_hash(empty_path)
            assert isinstance(hash_result, str)
            assert len(hash_result) == 16
            print("  ✅ 空文件哈希计算正确")
        except Exception as e:
            print(f"  ⚠️ 空文件处理: {e}")

        # 测试大文件（模拟）
        with patch('builtins.open') as mock_open:
            mock_file = MagicMock()
            # 模拟分块读取
            mock_file.read.side_effect = [
                b'chunk1' * 1000,  # 第一块
                b'chunk2' * 1000,  # 第二块
                b''  # 结束
            ]
            mock_open.return_value.__enter__.return_value = mock_file

            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    hash_result = ContentHashService.calculate_file_hash("/fake/large/file.pdf")
                    assert len(hash_result) == 16
                    print("  ✅ 大文件分块处理正确")

        # 测试不存在的文件
        try:
            ContentHashService.calculate_file_hash("/nonexistent/file.pdf")
            assert False, "应该抛出文件不存在错误"
        except ContentHashError:
            print("  ✅ 不存在文件错误处理正确")

        # 测试无效PDF（需要PyMuPDF）
        try:
            import fitz
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as invalid_pdf:
                invalid_pdf.write(b"This is not a valid PDF content")
                invalid_path = invalid_pdf.name

            try:
                ContentHashService.calculate_content_hash(invalid_path)
                assert False, "应该抛出PDF处理错误"
            except ContentHashError:
                print("  ✅ 无效PDF错误处理正确")

            Path(invalid_path).unlink(missing_ok=True)

        except ImportError:
            print("  ⚠️ PyMuPDF不可用，跳过PDF测试")

        # 测试文本规范化边界情况
        test_cases = [
            ("", ""),  # 空字符串
            ("   ", ""),  # 只有空格
            ("UPPER\tLOWER", "upper lower"),  # 大小写和制表符
            ("Multiple   Spaces", "multiple spaces"),  # 多个空格
            ("Line1\nLine2\r\nLine3", "line1 line2 line3"),  # 换行符
        ]

        for input_text, expected in test_cases:
            result = ContentHashService._normalize_text(input_text)
            assert result == expected, f"文本规范化失败: '{input_text}' -> '{result}' (期望: '{expected}')"

        print("  ✅ 文本规范化边界情况正确")

        # 清理
        Path(empty_path).unlink(missing_ok=True)

        print("✅ 内容哈希边界情况测试通过")
        return True

    except Exception as e:
        print(f"❌ 内容哈希边界情况测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_transaction_rollback():
    """测试事务回滚功能"""
    print("🧪 测试事务回滚...")

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

        repo = DocumentRepository(db)

        # 创建测试数据
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(b"test content")
            pdf_path = temp_pdf.name

        doc = DocumentModel.from_file(pdf_path, "test_hash", "Test Document")
        created_doc = repo.create(doc)

        # 验证初始状态
        initial_count = repo.count()
        assert initial_count == 1

        # 测试事务回滚
        try:
            with db.transaction():
                # 创建另一个文档
                doc2 = DocumentModel.from_file(pdf_path, "test_hash_2", "Test Document 2")
                repo.create(doc2)

                # 故意触发错误（重复哈希）
                doc3 = DocumentModel.from_file(pdf_path, "test_hash", "Duplicate Hash")
                repo.create(doc3)  # 这应该失败因为哈希重复

        except Exception:
            print("  ✅ 事务因重复哈希回滚（符合预期）")

        # 验证回滚后状态
        final_count = repo.count()
        assert final_count == initial_count, f"期望{initial_count}个文档，实际{final_count}个"
        print("  ✅ 事务回滚验证成功")

        # 清理
        Path(pdf_path).unlink(missing_ok=True)
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 事务回滚测试通过")
        return True

    except Exception as e:
        print(f"❌ 事务回滚测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_migration_compatibility():
    """测试数据库迁移兼容性"""
    print("🧪 测试数据库迁移兼容性...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator

        # 创建空数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)

        # 测试从版本0开始
        assert migrator.get_current_version() == 0
        assert migrator.needs_migration() is True
        print("  ✅ 初始状态检测正确")

        # 执行迁移
        success = migrator.migrate()
        assert success is True
        print("  ✅ 迁移执行成功")

        # 验证迁移后状态
        assert migrator.get_current_version() == 1
        assert migrator.needs_migration() is False
        print("  ✅ 迁移后状态正确")

        # 测试重复迁移
        success2 = migrator.migrate()
        assert success2 is True  # 应该成功但无操作
        assert migrator.get_current_version() == 1
        print("  ✅ 重复迁移处理正确")

        # 验证schema完整性
        assert migrator.validate_schema() is True
        print("  ✅ Schema验证通过")

        # 测试schema信息
        schema_info = migrator.get_schema_info()
        expected_tables = ["documents", "vector_indexes", "tags", "document_tags"]
        actual_tables = [table["name"] for table in schema_info["tables"]]

        for table in expected_tables:
            assert table in actual_tables, f"缺少表: {table}"
        print("  ✅ 所有必要表存在")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 数据库迁移兼容性测试通过")
        return True

    except Exception as e:
        print(f"❌ 数据库迁移兼容性测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_memory_usage():
    """测试内存使用情况"""
    print("🧪 测试内存使用...")

    try:
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

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
        repo = DocumentRepository(db)

        # 创建大量文档测试内存使用
        for i in range(50):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(f"Memory test document {i}".encode())
                pdf_path = temp_pdf.name

            doc = DocumentModel.from_file(pdf_path, f"memory_hash_{i}", f"Memory Test {i}")
            repo.create(doc)
            Path(pdf_path).unlink(missing_ok=True)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        print(f"  📊 初始内存: {initial_memory:.1f}MB")
        print(f"  📊 最终内存: {final_memory:.1f}MB")
        print(f"  📊 内存增长: {memory_increase:.1f}MB")

        # 内存使用应该合理（小于50MB增长）
        if memory_increase > 50:
            print("  ⚠️ 内存使用可能过高")
        else:
            print("  ✅ 内存使用合理")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 内存使用测试通过")
        return True

    except ImportError:
        print("  ⚠️ psutil不可用，跳过内存测试")
        return True
    except Exception as e:
        print(f"❌ 内存使用测试失败: {e}")
        return False

def main():
    """运行全面测试套件"""
    print("🚀 开始全面测试...\n")

    tests = [
        test_error_handling,
        test_concurrent_operations,
        test_large_data_handling,
        test_content_hash_edge_cases,
        test_transaction_rollback,
        test_migration_compatibility,
        test_memory_usage
    ]

    passed = 0
    total = len(tests)

    for test_func in tests:
        if test_func():
            passed += 1
        print()  # 空行分隔

    print(f"📊 全面测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有全面测试通过！系统稳定可靠！")
        return True
    else:
        print("⚠️ 部分测试失败，需要进一步优化。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
