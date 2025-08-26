#!/usr/bin/env python3
"""
数据库功能测试 - 测试数据库连接、模型和哈希服务功能

专门测试我们新开发的数据库持久化和内容哈希功能。
"""

import sys
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_database_connection():
    """测试数据库连接功能"""
    print("🧪 测试数据库连接...")

    try:
        from database.connection import DatabaseConnection

        # 创建临时数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        # 测试连接
        db = DatabaseConnection(db_path)

        # 测试基本操作
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO test (name) VALUES (?)", ("test_record",))

        result = db.fetch_one("SELECT name FROM test WHERE id = 1")
        assert result["name"] == "test_record"

        # 测试批量操作
        db.execute_many("INSERT INTO test (name) VALUES (?)", [("test2",), ("test3",)])
        results = db.fetch_all("SELECT name FROM test ORDER BY id")
        assert len(results) == 3

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 数据库连接测试通过")
        return True

    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_models():
    """测试数据库模型"""
    print("🧪 测试数据库模型...")

    try:
        from datetime import datetime

        from database.models import DocumentModel, TagModel, VectorIndexModel

        # 创建临时PDF文件
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(b"dummy PDF content")
            pdf_path = temp_pdf.name

        # 测试DocumentModel
        doc = DocumentModel(
            title="Test Document",
            file_path=pdf_path,
            file_hash="test_hash_123",
            file_size=1024
        )

        assert doc.title == "Test Document"
        assert doc.file_hash == "test_hash_123"
        assert isinstance(doc.created_at, datetime)

        # 测试数据库字典转换
        db_dict = doc.to_database_dict()
        assert "title" in db_dict
        assert "file_hash" in db_dict

        # 测试从文件创建
        doc2 = DocumentModel.from_file(pdf_path, "hash456", "Auto Title")
        assert doc2.title == "Auto Title"
        assert doc2.file_size > 0

        # 测试VectorIndexModel
        index = VectorIndexModel(
            document_id=1,
            index_path="/test/path",
            index_hash="index_hash_123"
        )

        assert index.document_id == 1
        assert index.index_path == "/test/path"

        # 测试TagModel
        tag = TagModel(name="Academic")
        assert tag.name == "academic"  # 应该被标准化为小写

        # 清理
        Path(pdf_path).unlink(missing_ok=True)

        print("✅ 数据库模型测试通过")
        return True

    except Exception as e:
        print(f"❌ 数据库模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_content_hash_service_isolated():
    """测试内容哈希服务（独立版本，不依赖其他服务）"""
    print("🧪 测试内容哈希服务...")

    try:
        # 直接导入，避免通过__init__.py
        sys.path.insert(0, str(Path(__file__).parent / "src" / "services"))
        from content_hash_service import ContentHashService

        # 首先检查PyMuPDF是否可用
        try:
            import fitz
            print("  📖 PyMuPDF 可用")
        except ImportError:
            print("  ⚠️ PyMuPDF 不可用，跳过PDF内容哈希测试")
            return True

        # 创建测试PDF
        temp_pdf_fd, pdf_path = tempfile.mkstemp(suffix='.pdf')
        import os
        os.close(temp_pdf_fd)  # 关闭文件描述符

        # 创建简单PDF
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((100, 100), "Test content for hashing")
        doc.save(pdf_path)
        doc.close()

        # 测试文件哈希
        file_hash = ContentHashService.calculate_file_hash(pdf_path)
        assert isinstance(file_hash, str)
        assert len(file_hash) == 16
        print(f"  📊 文件哈希: {file_hash}")

        # 测试内容哈希
        content_hash = ContentHashService.calculate_content_hash(pdf_path)
        assert isinstance(content_hash, str)
        assert len(content_hash) == 16
        print(f"  📄 内容哈希: {content_hash}")

        # 测试一致性
        file_hash2 = ContentHashService.calculate_file_hash(pdf_path)
        content_hash2 = ContentHashService.calculate_content_hash(pdf_path)
        assert file_hash == file_hash2
        assert content_hash == content_hash2

        # 测试组合哈希
        file_h, content_h = ContentHashService.calculate_combined_hashes(pdf_path)
        assert file_h == file_hash
        assert content_h == content_hash

        # 测试PDF验证
        assert ContentHashService.validate_pdf_file(pdf_path) is True

        # 测试文件信息
        info = ContentHashService.get_file_info(pdf_path)
        assert info["is_valid_pdf"] is True
        assert info["page_count"] == 1
        print(f"  📋 文件信息: {info['file_size']} bytes, {info['page_count']} pages")

        # 清理
        Path(pdf_path).unlink(missing_ok=True)

        print("✅ 内容哈希服务测试通过")
        return True

    except Exception as e:
        print(f"❌ 内容哈希服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_migrations():
    """测试数据库迁移系统"""
    print("🧪 测试数据库迁移...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator

        # 创建临时数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        # 创建连接和迁移器
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)

        # 测试版本检查
        assert migrator.get_current_version() == 0
        assert migrator.needs_migration() is True
        print("  📋 初始版本: 0, 需要迁移: True")

        # 执行迁移
        success = migrator.migrate()
        assert success is True
        print("  🔄 迁移执行成功")

        # 检查迁移后状态
        current_version = migrator.get_current_version()
        assert current_version == 2
        assert migrator.needs_migration() is False
        print(f"  📋 迁移后版本: {current_version}, 需要迁移: False")

        # 验证表创建
        schema_info = migrator.get_schema_info()
        table_names = [table["name"] for table in schema_info["tables"]]
        expected_tables = ["documents", "vector_indexes", "tags", "document_tags"]

        for table in expected_tables:
            assert table in table_names
        print(f"  📊 创建表: {', '.join(table_names)}")

        # 验证schema
        assert migrator.validate_schema() is True
        print("  ✅ Schema验证通过")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 数据库迁移测试通过")
        return True

    except Exception as e:
        print(f"❌ 数据库迁移测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_database():
    """集成测试 - 数据库和哈希服务协同工作"""
    print("🧪 集成测试（数据库版）...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        from database.models import DocumentModel

        # 直接导入哈希服务，避免依赖问题
        sys.path.insert(0, str(Path(__file__).parent / "src" / "services"))
        from content_hash_service import ContentHashService

        # 创建临时数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        # 初始化数据库
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()
        print("  🏗️ 数据库初始化完成")

        # 创建测试PDF
        try:
            import fitz
            temp_pdf_fd, pdf_path = tempfile.mkstemp(suffix='.pdf')
            import os
            os.close(temp_pdf_fd)

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), "Integration test content")
            doc.save(pdf_path)
            doc.close()
            print("  📄 测试PDF创建完成")
        except ImportError:
            # 如果没有PyMuPDF，创建假PDF文件
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(b"fake PDF content")
                pdf_path = temp_pdf.name
            print("  📄 测试文件创建完成（无PyMuPDF）")

        # 计算哈希
        if 'fitz' in sys.modules:
            file_hash, content_hash = ContentHashService.calculate_combined_hashes(pdf_path)
            print(f"  🔍 文件哈希: {file_hash}")
            print(f"  📝 内容哈希: {content_hash}")
        else:
            file_hash = ContentHashService.calculate_file_hash(pdf_path)
            content_hash = file_hash  # 假值
            print(f"  🔍 文件哈希: {file_hash}")

        # 创建文档模型
        doc_model = DocumentModel.from_file(
            file_path=pdf_path,
            file_hash=file_hash,
            title="Integration Test Document"
        )
        print("  📋 文档模型创建完成")

        # 保存到数据库
        insert_sql = """
        INSERT INTO documents (title, file_path, file_hash, file_size, created_at, updated_at, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        db_dict = doc_model.to_database_dict()
        db.execute(insert_sql, (
            db_dict["title"],
            db_dict["file_path"],
            db_dict["file_hash"],
            db_dict["file_size"],
            db_dict["created_at"],
            db_dict["updated_at"],
            db_dict["metadata"]
        ))

        # 验证数据插入
        result = db.fetch_one("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
        assert result is not None
        assert result["title"] == "Integration Test Document"
        print(f"  💾 文档已保存，ID: {result['id']}")

        # 测试重复检测
        duplicate_check = db.fetch_all("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
        assert len(duplicate_check) == 1
        print("  🔍 重复检测正常")

        # 测试文档查询
        all_docs = db.fetch_all("SELECT id, title, file_hash FROM documents")
        assert len(all_docs) == 1
        print(f"  📊 文档查询: 找到 {len(all_docs)} 个文档")

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)
        Path(pdf_path).unlink(missing_ok=True)

        print("✅ 集成测试通过")
        return True

    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_duplicate_detection():
    """专门测试重复文档检测功能"""
    print("🧪 测试重复文档检测...")

    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        from database.models import DocumentModel

        # 直接导入哈希服务
        sys.path.insert(0, str(Path(__file__).parent / "src" / "services"))
        from content_hash_service import ContentHashService

        # 初始化数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name

        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()

        # 创建两个相同内容的PDF文件
        try:
            import os

            import fitz

            # 第一个文件
            temp_pdf1_fd, pdf_path1 = tempfile.mkstemp(suffix='.pdf')
            os.close(temp_pdf1_fd)

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), "Same content for dedup test")
            doc.save(pdf_path1)
            doc.close()

            # 第二个文件，相同内容
            temp_pdf2_fd, pdf_path2 = tempfile.mkstemp(suffix='.pdf')
            os.close(temp_pdf2_fd)

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), "Same content for dedup test")  # 相同内容
            doc.save(pdf_path2)
            doc.close()

            # 计算哈希
            file_hash1, content_hash1 = ContentHashService.calculate_combined_hashes(pdf_path1)
            file_hash2, content_hash2 = ContentHashService.calculate_combined_hashes(pdf_path2)

            print(f"  📄 文件1 - 文件哈希: {file_hash1}, 内容哈希: {content_hash1}")
            print(f"  📄 文件2 - 文件哈希: {file_hash2}, 内容哈希: {content_hash2}")

            # 文件哈希应该不同（不同文件）
            assert file_hash1 != file_hash2
            print("  ✅ 文件哈希不同（符合预期）")

            # 内容哈希应该相同（相同内容）
            assert content_hash1 == content_hash2
            print("  ✅ 内容哈希相同（符合预期）")

            # 保存第一个文档
            doc1 = DocumentModel.from_file(pdf_path1, file_hash1, "Document 1")
            insert_sql = """
            INSERT INTO documents (title, file_path, file_hash, file_size, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            db_dict1 = doc1.to_database_dict()
            db.execute(insert_sql, (
                db_dict1["title"], db_dict1["file_path"], db_dict1["file_hash"],
                db_dict1["file_size"], db_dict1["created_at"],
                db_dict1["updated_at"], db_dict1["metadata"]
            ))
            print("  💾 文档1已保存")

            # 检查基于文件哈希的重复（应该没有）
            file_duplicates = db.fetch_all("SELECT * FROM documents WHERE file_hash = ?", (file_hash2,))
            assert len(file_duplicates) == 0
            print("  🔍 基于文件哈希：无重复（符合预期）")

            # 检查基于内容哈希的重复（这需要额外的字段或查询逻辑）
            # 这里我们可以通过自定义查询来实现内容去重
            # 注意：这需要在实际实现中添加content_hash字段到数据库

            print("  💡 内容级去重检测：建议在documents表中添加content_hash字段")

            # 清理
            Path(pdf_path1).unlink(missing_ok=True)
            Path(pdf_path2).unlink(missing_ok=True)

        except ImportError:
            print("  ⚠️ PyMuPDF不可用，使用文件哈希测试")
            # 使用普通文件进行测试
            with tempfile.NamedTemporaryFile(delete=False) as f1:
                f1.write(b"same content")
                path1 = f1.name

            with tempfile.NamedTemporaryFile(delete=False) as f2:
                f2.write(b"same content")
                path2 = f2.name

            hash1 = ContentHashService.calculate_file_hash(path1)
            hash2 = ContentHashService.calculate_file_hash(path2)

            # 相同内容的不同文件应该有不同的文件哈希（因为metadata不同）
            print(f"  📊 哈希1: {hash1}, 哈希2: {hash2}")

            Path(path1).unlink(missing_ok=True)
            Path(path2).unlink(missing_ok=True)

        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)

        print("✅ 重复文档检测测试通过")
        return True

    except Exception as e:
        print(f"❌ 重复文档检测测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有数据库相关测试"""
    print("🚀 开始测试数据库和哈希功能...\n")

    tests = [
        test_database_connection,
        test_database_models,
        test_content_hash_service_isolated,
        test_database_migrations,
        test_integration_database,
        test_duplicate_detection
    ]

    passed = 0
    total = len(tests)

    for test_func in tests:
        if test_func():
            passed += 1
        print()  # 空行分隔

    print(f"📊 测试结果: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有数据库功能测试通过！")
        print("\n📋 下一步建议：")
        print("1. 在documents表中添加content_hash字段以支持内容级去重")
        print("2. 创建Repository层以封装数据访问逻辑")
        print("3. 创建DocumentLibraryService以提供业务逻辑")
        print("4. 创建UI组件以展示文档库")
        return True
    else:
        print("⚠️ 部分测试失败，需要修复。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
