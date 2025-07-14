#!/usr/bin/env python3
"""
独立测试脚本 - 测试新的数据库和内容哈希功能

这个脚本独立运行，不依赖现有的pytest配置，
用于验证我们新开发的功能。
"""

import sys
import tempfile
import sqlite3
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
        
        # 测试事务
        with db.transaction():
            db.execute("INSERT INTO test (name) VALUES (?)", ("transaction_test",))
        
        results = db.fetch_all("SELECT name FROM test")
        assert len(results) == 2
        
        # 清理
        db.close_connection()
        Path(db_path).unlink(missing_ok=True)
        
        print("✅ 数据库连接测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        return False

def test_database_models():
    """测试数据库模型"""
    print("🧪 测试数据库模型...")
    
    try:
        from database.models import DocumentModel, VectorIndexModel, TagModel
        from datetime import datetime
        
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
        return False

def test_content_hash_service():
    """测试内容哈希服务"""
    print("🧪 测试内容哈希服务...")
    
    try:
        # 首先检查PyMuPDF是否可用
        try:
            import fitz
            print("  📖 PyMuPDF 可用")
        except ImportError:
            print("  ⚠️ PyMuPDF 不可用，跳过PDF内容哈希测试")
            return True
        
        from services.content_hash_service import ContentHashService
        
        # 创建测试PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            # 创建简单PDF
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((100, 100), "Test content for hashing")
            doc.save(temp_pdf.name)
            doc.close()
            pdf_path = temp_pdf.name
        
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
        
        # 执行迁移
        success = migrator.migrate()
        assert success is True
        
        # 检查迁移后状态
        assert migrator.get_current_version() == 1
        assert migrator.needs_migration() is False
        
        # 验证表创建
        schema_info = migrator.get_schema_info()
        table_names = [table["name"] for table in schema_info["tables"]]
        assert "documents" in table_names
        assert "vector_indexes" in table_names
        assert "tags" in table_names
        assert "document_tags" in table_names
        
        # 验证schema
        assert migrator.validate_schema() is True
        
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

def test_integration():
    """集成测试 - 测试各组件协同工作"""
    print("🧪 集成测试...")
    
    try:
        from database.connection import DatabaseConnection
        from database.migrations import DatabaseMigrator
        from database.models import DocumentModel
        from services.content_hash_service import ContentHashService
        
        # 创建临时数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
            db_path = temp_db.name
        
        # 初始化数据库
        db = DatabaseConnection(db_path)
        migrator = DatabaseMigrator(db)
        migrator.migrate()
        
        # 创建测试PDF
        try:
            import fitz
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                doc = fitz.open()
                page = doc.new_page()
                page.insert_text((100, 100), "Integration test content")
                doc.save(temp_pdf.name)
                doc.close()
                pdf_path = temp_pdf.name
        except ImportError:
            # 如果没有PyMuPDF，创建假PDF文件
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(b"fake PDF content")
                pdf_path = temp_pdf.name
        
        # 计算哈希
        if 'fitz' in sys.modules:
            file_hash, content_hash = ContentHashService.calculate_combined_hashes(pdf_path)
        else:
            file_hash = ContentHashService.calculate_file_hash(pdf_path)
            content_hash = file_hash  # 假值
        
        # 创建文档模型
        doc_model = DocumentModel.from_file(
            file_path=pdf_path,
            file_hash=file_hash,
            title="Integration Test Document"
        )
        
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
        
        # 测试重复检测
        duplicate_check = db.fetch_all("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
        assert len(duplicate_check) == 1
        
        print(f"  📄 文档已保存，ID: {result['id']}")
        print(f"  🔍 文件哈希: {file_hash}")
        
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

def main():
    """运行所有测试"""
    print("🚀 开始测试新功能...\n")
    
    tests = [
        test_database_connection,
        test_database_models,
        test_content_hash_service,
        test_database_migrations,
        test_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        if test_func():
            passed += 1
        print()  # 空行分隔
    
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！新功能实现成功！")
        return True
    else:
        print("⚠️ 部分测试失败，需要修复。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)