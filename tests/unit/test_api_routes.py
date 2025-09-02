"""
Unit tests for API Routes - FastAPI endpoints.
"""

import json
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# Mock the dependencies before importing routes
with patch('backend.api.routes.documents.get_library_controller'):
    with patch('backend.api.routes.library.get_library_controller'):
        with patch('backend.api.routes.rag.require_rag_service'):
            from backend.api.routes import documents, library, rag


class TestDocumentRoutes:
    """Test suite for document API endpoints."""

    @pytest.fixture
    def mock_document_service(self):
        """Create a mock document service."""
        service = Mock()
        service.get_all_documents.return_value = [
            {"id": 1, "title": "Doc 1", "file_path": "/path1.pdf"},
            {"id": 2, "title": "Doc 2", "file_path": "/path2.pdf"}
        ]
        service.get_document_by_id.return_value = {
            "id": 1,
            "title": "Test Document",
            "file_path": "/test.pdf",
            "content": "Test content"
        }
        service.create_document.return_value = {
            "id": 3,
            "title": "New Document",
            "file_path": "/new.pdf"
        }
        service.update_document.return_value = {
            "id": 1,
            "title": "Updated Document",
            "file_path": "/updated.pdf"
        }
        service.delete_document.return_value = True
        return service

    @pytest.fixture
    def app(self, mock_document_service):
        """Create FastAPI app with mocked dependencies."""
        app = FastAPI()

        # Mock dependency injection
        def get_mock_service():
            return mock_document_service

        with patch('backend.api.routes.documents.get_library_controller', get_mock_service):
            app.include_router(documents.router, prefix="/api/documents")

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_get_all_documents(self, client, mock_document_service):
        """Test GET /api/documents endpoint."""
        # Act
        response = client.get("/api/documents")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Doc 1"
        mock_document_service.get_all_documents.assert_called_once()

    def test_get_document_by_id(self, client, mock_document_service):
        """Test GET /api/documents/{id} endpoint."""
        # Act
        response = client.get("/api/documents/1")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Test Document"
        mock_document_service.get_document_by_id.assert_called_once_with(1)

    def test_get_document_not_found(self, client, mock_document_service):
        """Test GET /api/documents/{id} with non-existent document."""
        # Arrange
        mock_document_service.get_document_by_id.return_value = None

        # Act
        response = client.get("/api/documents/999")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_document(self, client, mock_document_service):
        """Test POST /api/documents endpoint."""
        # Arrange
        document_data = {
            "title": "New Document",
            "file_path": "/new.pdf",
            "content": "New content"
        }

        # Act
        response = client.post("/api/documents", json=document_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 3
        assert data["title"] == "New Document"
        mock_document_service.create_document.assert_called_once()

    def test_update_document(self, client, mock_document_service):
        """Test PUT /api/documents/{id} endpoint."""
        # Arrange
        update_data = {
            "title": "Updated Document",
            "content": "Updated content"
        }

        # Act
        response = client.put("/api/documents/1", json=update_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Document"
        mock_document_service.update_document.assert_called_once_with(1, update_data)

    def test_delete_document(self, client, mock_document_service):
        """Test DELETE /api/documents/{id} endpoint."""
        # Act
        response = client.delete("/api/documents/1")

        # Assert
        assert response.status_code == 204
        mock_document_service.delete_document.assert_called_once_with(1)

    def test_search_documents(self, client, mock_document_service):
        """Test GET /api/documents/search endpoint."""
        # Arrange
        mock_document_service.search_documents.return_value = [
            {"id": 1, "title": "Machine Learning Paper", "score": 0.95}
        ]

        # Act
        response = client.get("/api/documents/search?q=machine learning")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "Machine Learning" in data[0]["title"]
        mock_document_service.search_documents.assert_called_once()


class TestLibraryRoutes:
    """Test suite for library API endpoints."""

    @pytest.fixture
    def mock_library_service(self):
        """Create a mock library service."""
        service = Mock()
        service.upload_document.return_value = {
            "id": 1,
            "title": "Uploaded Document",
            "file_path": "/uploads/doc.pdf",
            "size": 1024000
        }
        service.get_library_stats.return_value = {
            "total_documents": 10,
            "total_size": 50000000,
            "document_types": {"pdf": 8, "txt": 2}
        }
        service.process_document.return_value = {
            "status": "processed",
            "citations_extracted": 15,
            "index_created": True
        }
        return service

    @pytest.fixture
    def app(self, mock_library_service):
        """Create FastAPI app with mocked dependencies."""
        app = FastAPI()

        def get_mock_service():
            return mock_library_service

        with patch('backend.api.routes.library.get_library_service', get_mock_service):
            app.include_router(library.router, prefix="/api/library")

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_upload_document(self, client, mock_library_service):
        """Test POST /api/library/upload endpoint."""
        # Arrange
        files = {"file": ("test.pdf", b"PDF content", "application/pdf")}

        # Act
        response = client.post("/api/library/upload", files=files)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Uploaded Document"
        mock_library_service.upload_document.assert_called_once()

    def test_get_library_stats(self, client, mock_library_service):
        """Test GET /api/library/stats endpoint."""
        # Act
        response = client.get("/api/library/stats")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_documents"] == 10
        assert data["document_types"]["pdf"] == 8
        mock_library_service.get_library_stats.assert_called_once()

    def test_process_document(self, client, mock_library_service):
        """Test POST /api/library/process/{id} endpoint."""
        # Act
        response = client.post("/api/library/process/1")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["citations_extracted"] == 15
        mock_library_service.process_document.assert_called_once_with(1)

    def test_bulk_upload(self, client, mock_library_service):
        """Test POST /api/library/bulk-upload endpoint."""
        # Arrange
        mock_library_service.bulk_upload.return_value = {
            "uploaded": 3,
            "failed": 0,
            "documents": [
                {"id": 1, "title": "Doc1.pdf"},
                {"id": 2, "title": "Doc2.pdf"},
                {"id": 3, "title": "Doc3.pdf"}
            ]
        }

        files = [
            ("files", ("doc1.pdf", b"Content 1", "application/pdf")),
            ("files", ("doc2.pdf", b"Content 2", "application/pdf")),
            ("files", ("doc3.pdf", b"Content 3", "application/pdf"))
        ]

        # Act
        response = client.post("/api/library/bulk-upload", files=files)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["uploaded"] == 3
        assert len(data["documents"]) == 3


class TestRAGRoutes:
    """Test suite for RAG API endpoints."""

    @pytest.fixture
    def mock_rag_service(self):
        """Create a mock RAG service."""
        service = Mock()
        service.query.return_value = {
            "answer": "The answer to your question is...",
            "sources": [
                {"document_id": 1, "page": 5, "score": 0.92},
                {"document_id": 2, "page": 10, "score": 0.85}
            ],
            "confidence": 0.88
        }
        service.create_index.return_value = {
            "status": "created",
            "document_id": 1,
            "chunks": 50
        }
        service.update_index.return_value = {
            "status": "updated",
            "document_id": 1
        }
        return service

    @pytest.fixture
    def app(self, mock_rag_service):
        """Create FastAPI app with mocked dependencies."""
        app = FastAPI()

        def get_mock_service():
            return mock_rag_service

        with patch('backend.api.routes.rag.require_rag_service', get_mock_service):
            app.include_router(rag.router, prefix="/api/rag")

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_query_rag(self, client, mock_rag_service):
        """Test POST /api/rag/query endpoint."""
        # Arrange
        query_data = {
            "question": "What is machine learning?",
            "document_ids": [1, 2],
            "top_k": 5
        }

        # Act
        response = client.post("/api/rag/query", json=query_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert len(data["sources"]) == 2
        assert data["confidence"] == 0.88
        mock_rag_service.query.assert_called_once()

    def test_create_index(self, client, mock_rag_service):
        """Test POST /api/rag/index endpoint."""
        # Arrange
        index_data = {
            "document_id": 1,
            "chunk_size": 512,
            "overlap": 50
        }

        # Act
        response = client.post("/api/rag/index", json=index_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["chunks"] == 50
        mock_rag_service.create_index.assert_called_once()

    def test_update_index(self, client, mock_rag_service):
        """Test PUT /api/rag/index/{document_id} endpoint."""
        # Act
        response = client.put("/api/rag/index/1")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        mock_rag_service.update_index.assert_called_once_with(1)

    def test_delete_index(self, client, mock_rag_service):
        """Test DELETE /api/rag/index/{document_id} endpoint."""
        # Arrange
        mock_rag_service.delete_index.return_value = True

        # Act
        response = client.delete("/api/rag/index/1")

        # Assert
        assert response.status_code == 204
        mock_rag_service.delete_index.assert_called_once_with(1)

    def test_get_index_status(self, client, mock_rag_service):
        """Test GET /api/rag/index/{document_id}/status endpoint."""
        # Arrange
        mock_rag_service.get_index_status.return_value = {
            "document_id": 1,
            "status": "ready",
            "chunks": 50,
            "last_updated": "2024-01-01T00:00:00"
        }

        # Act
        response = client.get("/api/rag/index/1/status")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["chunks"] == 50

    def test_query_with_filters(self, client, mock_rag_service):
        """Test RAG query with advanced filters."""
        # Arrange
        query_data = {
            "question": "What are neural networks?",
            "filters": {
                "date_range": {"start": "2023-01-01", "end": "2024-12-31"},
                "authors": ["Smith", "Jones"],
                "min_score": 0.7
            }
        }

        # Act
        response = client.post("/api/rag/query", json=query_data)

        # Assert
        assert response.status_code == 200
        mock_rag_service.query.assert_called_once()
        call_args = mock_rag_service.query.call_args[0][0]
        assert "filters" in call_args

    def test_batch_index_creation(self, client, mock_rag_service):
        """Test batch index creation for multiple documents."""
        # Arrange
        mock_rag_service.batch_create_index.return_value = {
            "processed": 5,
            "failed": 0,
            "results": [
                {"document_id": i, "status": "created"} for i in range(1, 6)
            ]
        }

        batch_data = {
            "document_ids": [1, 2, 3, 4, 5],
            "chunk_size": 512
        }

        # Act
        response = client.post("/api/rag/batch-index", json=batch_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["processed"] == 5
        assert len(data["results"]) == 5
