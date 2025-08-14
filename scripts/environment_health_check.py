#!/usr/bin/env python3
"""
AI Enhanced PDF Scholar - Environment Health Check
验证开发环境的完整性和依赖关系状态
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def check_python_environment() -> Dict[str, any]:
    """检查Python环境配置"""
    return {
        "version": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "virtual_env": os.getenv('VIRTUAL_ENV', 'Not activated'),
        "python_path": sys.path[:3]
    }


def check_core_dependencies() -> Dict[str, str]:
    """检查核心依赖包"""
    results = {}

    try:
        import fitz
        results["PyMuPDF"] = f"{fitz.__version__} ✅"
    except ImportError as e:
        results["PyMuPDF"] = f"❌ {e}"

    try:
        import google.generativeai as genai
        results["Google GenerativeAI"] = "Available ✅"
    except ImportError as e:
        results["Google GenerativeAI"] = f"❌ {e}"

    try:
        import fastapi
        results["FastAPI"] = f"{fastapi.__version__} ✅"
    except ImportError as e:
        results["FastAPI"] = f"❌ {e}"

    try:
        from llama_index.core import __version__ as llama_version
        results["LlamaIndex"] = f"{llama_version} ✅"
    except ImportError as e:
        results["LlamaIndex"] = f"❌ {e}"

    try:
        import sqlite3
        results["SQLite"] = f"{sqlite3.sqlite_version} ✅"
    except ImportError as e:
        results["SQLite"] = f"❌ {e}"

    try:
        from PIL import Image
        results["Pillow"] = "Available ✅"
    except ImportError as e:
        results["Pillow"] = f"❌ {e}"

    return results


def test_pdf_processing() -> Tuple[bool, str]:
    """测试PDF处理功能"""
    try:
        import fitz
        import io

        # Create test PDF
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), 'Test PDF for Health Check')
        pdf_bytes = doc.tobytes()
        doc.close()

        # Test reading
        doc2 = fitz.open(stream=pdf_bytes)
        text = doc2[0].get_text()
        doc2.close()

        if 'Test PDF for Health Check' in text:
            return True, "PDF processing working correctly"
        else:
            return False, "PDF text extraction failed"

    except Exception as e:
        return False, f"PDF processing error: {e}"


def test_gemini_api() -> Tuple[bool, str]:
    """测试Google Gemini API连接"""
    try:
        import google.generativeai as genai
        import os

        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return False, "GEMINI_API_KEY not found in environment"

        if 'test_api_key' in api_key:
            return False, "Using test API key, real API key needed"

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content('Test connection')

        if response and response.text:
            return True, f"API connection successful: {response.text[:50]}..."
        else:
            return False, "API returned empty response"

    except Exception as e:
        return False, f"API connection failed: {e}"


def check_database_status() -> Tuple[bool, str]:
    """检查数据库状态"""
    try:
        import sys
        from pathlib import Path

        # Add project root to Python path
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.database.connection import DatabaseConnection
        from src.database.modular_migrator import ModularDatabaseMigrator as DatabaseMigrator

        db_path = os.getenv('DATABASE_PATH', './data/library.db')
        db_connection = DatabaseConnection(db_path=db_path)
        migrator = DatabaseMigrator(db_connection)

        schema_info = migrator.get_schema_info()
        current_version = schema_info.get('current_version', 0)
        target_version = schema_info.get('target_version', 0)
        tables = schema_info.get('tables', [])

        if current_version == target_version:
            return True, f"Database up-to-date (v{current_version}), {len(tables)} tables"
        else:
            return False, f"Database needs migration: {current_version} → {target_version}"

    except Exception as e:
        return False, f"Database error: {e}"


def check_directory_structure() -> Dict[str, bool]:
    """检查必要的目录结构"""
    required_dirs = [
        'data',
        'data/documents',
        'data/vector_indexes',
        'logs',
        'cache',
        'cache/downloads',
        'backups'
    ]

    results = {}
    for directory in required_dirs:
        path = Path(directory)
        results[directory] = path.exists() and path.is_dir()

    return results


def check_environment_config() -> Dict[str, any]:
    """检查环境配置文件"""
    config_files = ['.env', '.env.example', '.env.test']
    results = {}

    for config_file in config_files:
        path = Path(config_file)
        if path.exists():
            results[config_file] = {
                'exists': True,
                'size': path.stat().st_size,
                'readable': os.access(path, os.R_OK)
            }
        else:
            results[config_file] = {'exists': False}

    return results


def run_health_check() -> Dict[str, any]:
    """运行完整的环境健康检查"""
    print("🔍 Running AI Enhanced PDF Scholar Environment Health Check...")
    print("=" * 60)

    health_report = {
        'timestamp': None,
        'python_environment': {},
        'core_dependencies': {},
        'pdf_processing': {},
        'gemini_api': {},
        'database_status': {},
        'directory_structure': {},
        'environment_config': {},
        'overall_status': 'UNKNOWN'
    }

    # Python环境检查
    print("\n📋 Python Environment:")
    health_report['python_environment'] = check_python_environment()
    for key, value in health_report['python_environment'].items():
        print(f"  {key}: {value}")

    # 核心依赖检查
    print("\n📦 Core Dependencies:")
    health_report['core_dependencies'] = check_core_dependencies()
    for key, value in health_report['core_dependencies'].items():
        print(f"  {key}: {value}")

    # PDF处理测试
    print("\n📄 PDF Processing Test:")
    pdf_ok, pdf_msg = test_pdf_processing()
    health_report['pdf_processing'] = {'status': pdf_ok, 'message': pdf_msg}
    print(f"  Status: {'✅' if pdf_ok else '❌'} {pdf_msg}")

    # Gemini API测试
    print("\n🤖 Gemini API Test:")
    api_ok, api_msg = test_gemini_api()
    health_report['gemini_api'] = {'status': api_ok, 'message': api_msg}
    print(f"  Status: {'✅' if api_ok else '❌'} {api_msg}")

    # 数据库状态检查
    print("\n🗄️ Database Status:")
    db_ok, db_msg = check_database_status()
    health_report['database_status'] = {'status': db_ok, 'message': db_msg}
    print(f"  Status: {'✅' if db_ok else '❌'} {db_msg}")

    # 目录结构检查
    print("\n📁 Directory Structure:")
    health_report['directory_structure'] = check_directory_structure()
    for directory, exists in health_report['directory_structure'].items():
        print(f"  {directory}: {'✅' if exists else '❌'}")

    # 环境配置检查
    print("\n⚙️ Environment Configuration:")
    health_report['environment_config'] = check_environment_config()
    for config_file, info in health_report['environment_config'].items():
        if info['exists']:
            print(f"  {config_file}: ✅ ({info['size']} bytes)")
        else:
            print(f"  {config_file}: ❌ Missing")

    # 总体状态评估
    critical_checks = [
        all('✅' in v for v in health_report['core_dependencies'].values()),
        health_report['pdf_processing']['status'],
        health_report['database_status']['status'],
        all(health_report['directory_structure'].values())
    ]

    if all(critical_checks):
        health_report['overall_status'] = 'HEALTHY'
        status_icon = '✅'
    elif sum(critical_checks) >= 3:
        health_report['overall_status'] = 'WARNING'
        status_icon = '⚠️'
    else:
        health_report['overall_status'] = 'ERROR'
        status_icon = '❌'

    print(f"\n{status_icon} Overall Status: {health_report['overall_status']}")

    # 导入时间戳
    from datetime import datetime
    health_report['timestamp'] = datetime.now().isoformat()

    return health_report


if __name__ == "__main__":
    # Change to project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)

    # Run health check
    report = run_health_check()

    # Save report to file
    import json
    report_file = Path('logs/environment_health_report.json')
    report_file.parent.mkdir(exist_ok=True)

    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Health report saved to: {report_file}")

    # Exit with appropriate code
    if report['overall_status'] == 'HEALTHY':
        sys.exit(0)
    elif report['overall_status'] == 'WARNING':
        sys.exit(1)
    else:
        sys.exit(2)