#!/usr/bin/env python3
"""
简单的上传调试脚本，用于测试文档导入流程
"""

import sys
import traceback
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.api.dependencies import get_db, get_library_controller


def test_document_import():
    """测试文档导入过程"""
    try:
        print("=== 测试文档上传调试 ===")

        # 1. 测试数据库连接
        print("1. 测试数据库连接...")
        db = get_db()
        print(f"   数据库连接成功: {db}")

        # 2. 测试library_controller初始化
        print("2. 测试LibraryController初始化...")
        controller = get_library_controller(db, None)
        print(f"   LibraryController初始化成功: {controller}")

        # 3. 测试PDF文件
        test_pdf = project_root / "test_valid.pdf"
        if not test_pdf.exists():
            print(f"   错误：测试PDF文件不存在: {test_pdf}")
            return False
        print(f"   测试PDF文件存在: {test_pdf}")

        # 4. 尝试文档导入
        print("3. 尝试文档导入...")
        success = controller.import_document(
            file_path=str(test_pdf),
            title="测试PDF文档",
            check_duplicates=True,
            auto_build_index=False
        )
        print(f"   文档导入结果: {success}")

        if success:
            print("=== 文档导入测试成功 ===")
            # 验证文档是否已导入
            documents = controller.get_documents()
            print(f"   当前文档数量: {len(documents)}")
            if documents:
                print(f"   最新文档: {documents[0].title}")
        else:
            print("=== 文档导入测试失败 ===")

        return success

    except Exception as e:
        print("=== 测试过程中发生异常 ===")
        print(f"异常类型: {type(e).__name__}")
        print(f"异常信息: {str(e)}")
        print("详细堆栈:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_document_import()
