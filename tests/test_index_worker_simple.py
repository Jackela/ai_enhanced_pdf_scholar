"""
简化的IndexWorker测试
遵循TDD原则，避免使用QSignalSpy的复杂测试
"""

import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
from PyQt6.QtCore import QTimer

# Import the classes we need to test
from src.index_worker import IndexWorker


class TestIndexWorkerBasic:
    """测试IndexWorker的基本功能"""
    
    def test_index_worker_requires_pdf_path(self):
        """IndexWorker应该要求有效的PDF路径"""
        with pytest.raises(ValueError, match="PDF path is required"):
            IndexWorker("", Mock())
            
        with pytest.raises(ValueError, match="PDF path is required"):
            IndexWorker(None, Mock())
    
    def test_index_worker_requires_rag_service(self):
        """IndexWorker应该要求RAG服务"""
        with pytest.raises(ValueError, match="RAG service is required"):
            IndexWorker("test.pdf", None)
    
    def test_index_worker_initialization_success(self):
        """IndexWorker应该能够成功初始化"""
        mock_rag_service = Mock()
        worker = IndexWorker("test.pdf", mock_rag_service)
        
        assert worker is not None
        assert worker.get_pdf_path() == "test.pdf"
        assert worker.rag_service == mock_rag_service
    
    def test_signals_exist(self):
        """IndexWorker应该有必要的信号"""
        mock_rag_service = Mock()
        worker = IndexWorker("test.pdf", mock_rag_service)
        
        # 检查信号是否存在
        assert hasattr(worker, 'indexing_completed')
        assert hasattr(worker, 'indexing_failed')
        assert hasattr(worker, 'progress_update')
    
    def test_is_qthread_subclass(self):
        """IndexWorker应该是QThread的子类"""
        from PyQt6.QtCore import QThread
        mock_rag_service = Mock()
        worker = IndexWorker("test.pdf", mock_rag_service)
        
        assert isinstance(worker, QThread)


class TestIndexWorkerExecution:
    """测试IndexWorker的执行功能"""
    
    def setup_method(self):
        """每个测试方法的设置"""
        self.mock_rag_service = Mock()
        self.worker = IndexWorker("test.pdf", self.mock_rag_service)
        
        # 设置信号接收器
        self.completed_signals = []
        self.failed_signals = []
        self.progress_signals = []
        
        self.worker.indexing_completed.connect(self.completed_signals.append)
        self.worker.indexing_failed.connect(self.failed_signals.append)
        self.worker.progress_update.connect(self.progress_signals.append)
    
    def test_run_successful_indexing(self):
        """成功索引应该发出完成信号"""
        # Mock成功的索引创建
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # 运行worker
        self.worker.run()
        
        # 验证信号
        assert len(self.completed_signals) == 1
        assert len(self.failed_signals) == 0
        assert self.completed_signals[0] == "test.pdf"  # 应该发出PDF路径
        
        # 验证RAG服务被调用
        self.mock_rag_service.build_index_from_pdf.assert_called_once_with("test.pdf")
    
    def test_run_failed_indexing(self):
        """索引失败应该发出失败信号"""
        # Mock失败的索引创建
        error_msg = "Indexing failed"
        self.mock_rag_service.build_index_from_pdf.side_effect = Exception(error_msg)
        
        # 运行worker
        self.worker.run()
        
        # 验证信号
        assert len(self.completed_signals) == 0
        assert len(self.failed_signals) == 1
        assert error_msg in self.failed_signals[0]
        
        # 验证RAG服务被调用
        self.mock_rag_service.build_index_from_pdf.assert_called_once_with("test.pdf")
    
    def test_progress_updates_during_indexing(self):
        """索引过程中应该发出进度更新"""
        # Mock成功的索引创建
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # 运行worker
        self.worker.run()
        
        # 应该有进度更新
        assert len(self.progress_signals) >= 1
        
        # 检查是否有典型的进度消息
        progress_messages = " ".join(self.progress_signals)
        assert "索引" in progress_messages or "正在" in progress_messages


class TestIndexWorkerErrorHandling:
    """测试IndexWorker的错误处理"""
    
    def setup_method(self):
        """每个测试方法的设置"""
        self.mock_rag_service = Mock()
        self.worker = IndexWorker("test.pdf", self.mock_rag_service)
        
        self.failed_signals = []
        self.worker.indexing_failed.connect(self.failed_signals.append)
    
    def test_handles_rag_service_errors(self):
        """应该优雅地处理RAG服务错误"""
        from src.rag_service import RAGIndexError
        
        self.mock_rag_service.build_index_from_pdf.side_effect = RAGIndexError("PDF file not found")
        
        # 运行worker
        self.worker.run()
        
        # 应该发出失败信号
        assert len(self.failed_signals) == 1
        assert "PDF file not found" in self.failed_signals[0]
    
    def test_handles_generic_exceptions(self):
        """应该处理任何意外异常"""
        self.mock_rag_service.build_index_from_pdf.side_effect = RuntimeError("Unexpected error")
        
        # 运行worker
        self.worker.run()
        
        # 应该发出失败信号
        assert len(self.failed_signals) == 1
        assert "Unexpected error" in self.failed_signals[0]
    
    def test_continues_execution_after_error(self):
        """错误后worker应该继续执行而不会崩溃"""
        self.mock_rag_service.build_index_from_pdf.side_effect = Exception("Test error")
        
        # 这不应该引发异常或崩溃
        self.worker.run()
        
        # Worker应该仍然处于有效状态
        assert self.worker is not None


class TestIndexWorkerIntegration:
    """IndexWorker的集成测试"""
    
    def setup_method(self):
        """每个测试方法的设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_pdf_path = os.path.join(self.temp_dir, "test.pdf")
        
        # 创建一个mock PDF文件
        with open(self.test_pdf_path, 'wb') as f:
            f.write(b"Mock PDF content")
        
        self.mock_rag_service = Mock()
        self.worker = IndexWorker(self.test_pdf_path, self.mock_rag_service)
        
        # 设置信号接收器
        self.completed_signals = []
        self.failed_signals = []
        
        self.worker.indexing_completed.connect(self.completed_signals.append)
        self.worker.indexing_failed.connect(self.failed_signals.append)
    
    def teardown_method(self):
        """每个测试方法后的清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow_success(self):
        """测试完整的成功工作流程"""
        # Mock成功的索引创建
        self.mock_rag_service.build_index_from_pdf.return_value = True
        
        # 运行worker
        self.worker.run()
        
        # 验证成功信号
        assert len(self.completed_signals) == 1
        assert len(self.failed_signals) == 0
        assert self.completed_signals[0] == self.test_pdf_path
        
        # 验证RAG服务被正确调用
        self.mock_rag_service.build_index_from_pdf.assert_called_once_with(self.test_pdf_path)
    
    def test_full_workflow_failure(self):
        """测试完整的失败工作流程"""
        # Mock失败的索引创建
        self.mock_rag_service.build_index_from_pdf.side_effect = Exception("Test failure")
        
        # 运行worker
        self.worker.run()
        
        # 验证失败信号
        assert len(self.completed_signals) == 0
        assert len(self.failed_signals) == 1
        assert "Test failure" in self.failed_signals[0]


if __name__ == "__main__":
    pytest.main([__file__]) 