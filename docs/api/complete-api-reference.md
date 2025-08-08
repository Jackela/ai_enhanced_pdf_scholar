# Complete API Reference - AI Enhanced PDF Scholar

## Table of Contents

1. [Introduction](#introduction)
2. [Authentication & Security](#authentication--security)
3. [API Conventions](#api-conventions)
4. [System Management API](#system-management-api)
5. [Document Management API](#document-management-api)
6. [Library Management API](#library-management-api)
7. [RAG & AI Query API](#rag--ai-query-api)
8. [Citation Management API](#citation-management-api)
9. [Settings & Configuration API](#settings--configuration-api)
10. [WebSocket API](#websocket-api)
11. [Error Handling](#error-handling)
12. [Rate Limiting](#rate-limiting)
13. [SDK Examples](#sdk-examples)
14. [Changelog](#changelog)

## Introduction

The AI Enhanced PDF Scholar API is a RESTful service built with FastAPI that provides comprehensive document management, AI-powered analysis, and citation extraction capabilities. This reference documents all available endpoints with detailed examples, response formats, and integration patterns.

### Base URL
```
http://localhost:8000
```

### API Version
```
Current Version: v2.1.0
API Path Prefix: /api
Interactive Docs: /api/docs
ReDoc: /api/redoc
```

### Content Types
- **Request**: `application/json`, `multipart/form-data`
- **Response**: `application/json`
- **File Downloads**: `application/pdf`, `application/octet-stream`

## Authentication & Security

### Current Authentication Model
The current version operates as a single-user local application without authentication requirements. However, the API includes security features:

```python
# Security headers included in all responses
{
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
}
```

### Future Authentication (v3.0+)
```python
# Planned authentication flow
{
    "Authorization": "Bearer <jwt_token>",
    "X-API-Key": "<api_key>"
}
```

### Rate Limiting
- **Default**: 100 requests per minute per IP
- **Upload**: 10 files per minute
- **RAG Queries**: 20 queries per minute

## API Conventions

### Standard Response Format

#### Success Response
```json
{
    "success": true,
    "message": "Operation completed successfully",
    "data": {
        // Response data here
    },
    "timestamp": "2025-08-09T10:30:00Z",
    "request_id": "req_1234567890"
}
```

#### Error Response
```json
{
    "detail": "Descriptive error message",
    "error_code": "ERROR_CODE_CONSTANT",
    "status_code": 400,
    "timestamp": "2025-08-09T10:30:00Z",
    "request_id": "req_1234567890",
    "validation_errors": [
        {
            "field": "field_name",
            "message": "Field-specific error message"
        }
    ]
}
```

### HTTP Status Codes
- **200 OK**: Successful operation
- **201 Created**: Resource created successfully
- **400 Bad Request**: Invalid request parameters
- **404 Not Found**: Resource not found
- **409 Conflict**: Resource conflict (e.g., duplicate)
- **413 Payload Too Large**: File size exceeds limit
- **422 Unprocessable Entity**: Validation error
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error
- **503 Service Unavailable**: Service temporarily unavailable

### Pagination
```json
{
    "data": [],
    "pagination": {
        "page": 1,
        "per_page": 50,
        "total": 150,
        "pages": 3,
        "has_next": true,
        "has_prev": false
    }
}
```

## System Management API

### Health Check
**GET** `/api/system/health`

Monitor system health and component availability.

**Response Example:**
```json
{
    "success": true,
    "status": "healthy",
    "components": {
        "database": {
            "status": "healthy",
            "response_time_ms": 12
        },
        "rag_service": {
            "status": "healthy",
            "api_key_configured": true,
            "model_available": true
        },
        "vector_service": {
            "status": "healthy",
            "indexes_count": 45
        },
        "storage": {
            "status": "healthy",
            "available_space_mb": 15360,
            "total_space_mb": 51200
        }
    },
    "uptime_seconds": 86400,
    "version": "2.1.0"
}
```

**Health Status Values:**
- `healthy`: All systems operational
- `degraded`: Some non-critical issues
- `unhealthy`: Critical system failures

### System Configuration
**GET** `/api/system/config`

Retrieve system configuration and feature availability.

**Response Example:**
```json
{
    "success": true,
    "features": {
        "document_upload": true,
        "rag_queries": true,
        "vector_indexing": true,
        "citation_extraction": true,
        "citation_networks": true,
        "batch_processing": true,
        "websocket_support": true,
        "export_formats": ["bibtex", "endnote", "csv", "json"]
    },
    "limits": {
        "max_file_size_mb": 100,
        "max_documents": 10000,
        "max_query_length": 5000,
        "max_concurrent_queries": 10,
        "supported_formats": [".pdf"]
    },
    "api_version": "2.1.0",
    "build_info": {
        "version": "2.1.0",
        "build_date": "2025-08-09",
        "commit": "a1b2c3d"
    }
}
```

### System Information
**GET** `/api/system/info`

Get detailed system environment information.

**Response Example:**
```json
{
    "success": true,
    "system": {
        "platform": "Windows-10-10.0.22621-SP0",
        "python_version": "3.11.5",
        "architecture": "AMD64",
        "cpu_count": 8,
        "memory_total_gb": 16.0
    },
    "application": {
        "version": "2.1.0",
        "environment": "development",
        "debug_mode": false,
        "database_url": "sqlite:///./data/library.db",
        "storage_path": "~/.ai_pdf_scholar"
    },
    "dependencies": {
        "fastapi": "0.104.1",
        "llama-index": "0.9.15",
        "sqlalchemy": "2.0.23"
    }
}
```

### Initialize System
**POST** `/api/system/initialize`

Initialize or reinitialize the system (run migrations, create directories).

**Request Body:**
```json
{
    "force_reinit": false,
    "migrate_database": true,
    "create_directories": true,
    "verify_dependencies": true
}
```

**Response Example:**
```json
{
    "success": true,
    "message": "System initialized successfully",
    "operations_performed": [
        "database_migrations_applied",
        "storage_directories_created", 
        "vector_indexes_validated",
        "cache_initialized"
    ],
    "warnings": []
}
```

## Document Management API

### List Documents
**GET** `/api/documents/`

Retrieve a paginated list of documents with filtering and sorting options.

**Query Parameters:**
- `search_query` (string): Search in titles and content
- `sort_by` (enum): `created_at|updated_at|last_accessed|title|file_size|page_count`
- `sort_order` (enum): `asc|desc`
- `page` (int): Page number (default: 1)
- `per_page` (int): Items per page (default: 50, max: 200)
- `show_missing` (boolean): Include documents with missing files
- `has_vector_index` (boolean): Filter by vector index presence
- `file_size_min` (int): Minimum file size in bytes
- `file_size_max` (int): Maximum file size in bytes
- `created_after` (datetime): Filter by creation date
- `created_before` (datetime): Filter by creation date

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/documents/?search_query=machine+learning&sort_by=created_at&sort_order=desc&page=1&per_page=20"
```

**Response Example:**
```json
{
    "success": true,
    "documents": [
        {
            "id": 1,
            "title": "Machine Learning Fundamentals.pdf",
            "file_path": "~/.ai_pdf_scholar/documents/abc123.pdf",
            "file_size": 2048000,
            "page_count": 25,
            "created_at": "2025-08-09T10:00:00Z",
            "updated_at": "2025-08-09T10:00:00Z",
            "last_accessed": "2025-08-09T15:30:00Z",
            "file_hash": "abc123def456",
            "content_hash": "def456ghi789",
            "is_file_available": true,
            "has_vector_index": true,
            "citation_count": 15,
            "metadata": {
                "author": "Dr. Smith",
                "keywords": ["machine learning", "artificial intelligence"],
                "language": "en",
                "quality_score": 0.92
            }
        }
    ],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 45,
        "pages": 3,
        "has_next": true,
        "has_prev": false
    },
    "filters_applied": {
        "search_query": "machine learning",
        "sort_by": "created_at",
        "sort_order": "desc"
    }
}
```

### Get Document Details
**GET** `/api/documents/{document_id}`

Retrieve detailed information about a specific document.

**Path Parameters:**
- `document_id` (int): Document ID

**Query Parameters:**
- `include_content` (boolean): Include extracted text content
- `include_metadata` (boolean): Include detailed metadata
- `include_citations` (boolean): Include citation summary

**Response Example:**
```json
{
    "success": true,
    "document": {
        "id": 1,
        "title": "Machine Learning Fundamentals.pdf",
        "file_path": "~/.ai_pdf_scholar/documents/abc123.pdf",
        "file_size": 2048000,
        "page_count": 25,
        "created_at": "2025-08-09T10:00:00Z",
        "updated_at": "2025-08-09T10:00:00Z",
        "last_accessed": "2025-08-09T15:30:00Z",
        "file_hash": "abc123def456",
        "content_hash": "def456ghi789",
        "is_file_available": true,
        "has_vector_index": true,
        "vector_index_stats": {
            "chunks_count": 45,
            "embedding_model": "text-embedding-ada-002",
            "index_size_mb": 12.5,
            "build_date": "2025-08-09T10:05:00Z"
        },
        "citations": {
            "total_count": 15,
            "high_confidence_count": 12,
            "average_confidence": 0.87
        },
        "access_stats": {
            "view_count": 25,
            "query_count": 8,
            "last_query": "2025-08-09T15:25:00Z"
        },
        "content_preview": "This paper presents a comprehensive overview of machine learning fundamentals...",
        "metadata": {
            "extracted_title": "Machine Learning Fundamentals: Theory and Practice",
            "extracted_authors": ["Dr. John Smith", "Dr. Jane Doe"],
            "publication_year": 2024,
            "language": "en",
            "quality_metrics": {
                "text_quality_score": 0.95,
                "structure_score": 0.88,
                "completeness_score": 0.92
            },
            "processing_info": {
                "processed_at": "2025-08-09T10:02:00Z",
                "processing_time_seconds": 45.2,
                "ocr_applied": false
            }
        }
    }
}
```

### Upload Document
**POST** `/api/documents/upload`

Upload a new PDF document to the system.

**Request Format:** `multipart/form-data`

**Form Parameters:**
- `file` (file, required): PDF file to upload
- `title` (string, optional): Document title (auto-extracted if not provided)
- `tags` (string, optional): Comma-separated tags
- `check_duplicates` (boolean, optional): Check for duplicates (default: true)
- `auto_build_index` (boolean, optional): Build vector index after upload (default: false)
- `extract_citations` (boolean, optional): Extract citations after upload (default: false)
- `metadata` (string, optional): JSON string with additional metadata

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
     -F "file=@research_paper.pdf" \
     -F "title=My Research Paper" \
     -F "tags=machine learning,research,AI" \
     -F "check_duplicates=true" \
     -F "auto_build_index=true" \
     -F "metadata={\"author\": \"Dr. Smith\", \"year\": 2024}"
```

**Response Example:**
```json
{
    "success": true,
    "message": "Document uploaded successfully",
    "document": {
        "id": 5,
        "title": "My Research Paper",
        "file_path": "~/.ai_pdf_scholar/documents/xyz789.pdf",
        "file_size": 1536000,
        "page_count": 18,
        "file_hash": "xyz789abc123",
        "content_hash": "abc123xyz789",
        "created_at": "2025-08-09T16:00:00Z",
        "is_file_available": true,
        "has_vector_index": false,
        "processing_status": "completed",
        "metadata": {
            "original_filename": "research_paper.pdf",
            "upload_timestamp": "2025-08-09T16:00:00Z",
            "tags": ["machine learning", "research", "AI"],
            "author": "Dr. Smith",
            "year": 2024
        }
    },
    "processing_info": {
        "duplicate_check_result": "no_duplicates_found",
        "text_extraction_time": 3.2,
        "quality_assessment": {
            "text_quality": 0.94,
            "structure_quality": 0.89,
            "overall_score": 0.91
        }
    }
}
```

**Error Responses:**
```json
// File too large
{
    "detail": "File size exceeds maximum limit of 100MB",
    "error_code": "FILE_TOO_LARGE",
    "status_code": 413
}

// Unsupported format
{
    "detail": "Only PDF files are supported",
    "error_code": "UNSUPPORTED_FORMAT",
    "status_code": 400
}

// Duplicate detected
{
    "detail": "Duplicate document detected",
    "error_code": "DUPLICATE_DOCUMENT",
    "status_code": 409,
    "duplicate_info": {
        "existing_document_id": 3,
        "similarity_score": 0.98,
        "match_type": "content_hash"
    }
}
```

### Update Document
**PUT** `/api/documents/{document_id}`

Update document metadata and properties.

**Path Parameters:**
- `document_id` (int): Document ID

**Request Body:**
```json
{
    "title": "Updated Document Title",
    "metadata": {
        "author": "Dr. Updated Author",
        "tags": ["updated", "tags"],
        "custom_field": "custom_value"
    },
    "notes": "Additional notes about this document"
}
```

**Response Example:**
```json
{
    "success": true,
    "message": "Document updated successfully",
    "document": {
        "id": 1,
        "title": "Updated Document Title",
        "updated_at": "2025-08-09T16:30:00Z",
        "metadata": {
            "author": "Dr. Updated Author",
            "tags": ["updated", "tags"],
            "custom_field": "custom_value",
            "last_modified_by": "system",
            "modification_history": [
                {
                    "timestamp": "2025-08-09T16:30:00Z",
                    "changes": ["title", "metadata.author", "metadata.tags"]
                }
            ]
        }
    }
}
```

### Delete Document
**DELETE** `/api/documents/{document_id}`

Delete a document and all associated data.

**Path Parameters:**
- `document_id` (int): Document ID

**Query Parameters:**
- `delete_file` (boolean): Also delete the physical file (default: true)
- `force` (boolean): Force deletion even if references exist (default: false)

**Response Example:**
```json
{
    "success": true,
    "message": "Document deleted successfully",
    "deleted_components": [
        "document_record",
        "vector_index",
        "citations",
        "physical_file",
        "cache_entries"
    ],
    "cleanup_info": {
        "freed_space_mb": 15.2,
        "deleted_citations": 12,
        "deleted_cache_entries": 5
    }
}
```

### Download Document
**GET** `/api/documents/{document_id}/download`

Download the original PDF file.

**Path Parameters:**
- `document_id` (int): Document ID

**Query Parameters:**
- `inline` (boolean): Display inline in browser (default: false)

**Response:** Binary PDF file with appropriate headers

**Response Headers:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="document_title.pdf"
Content-Length: 2048000
```

### Document Integrity Check
**GET** `/api/documents/{document_id}/integrity`

Check document and index integrity.

**Path Parameters:**
- `document_id` (int): Document ID

**Query Parameters:**
- `deep_check` (boolean): Perform deep integrity validation (default: false)
- `repair_if_needed` (boolean): Attempt automatic repair (default: false)

**Response Example:**
```json
{
    "success": true,
    "document_id": 1,
    "integrity_status": "healthy",
    "checks_performed": {
        "file_exists": {
            "status": "pass",
            "file_path": "~/.ai_pdf_scholar/documents/abc123.pdf"
        },
        "file_accessible": {
            "status": "pass",
            "read_test": true
        },
        "hash_validation": {
            "status": "pass",
            "file_hash_match": true,
            "content_hash_match": true
        },
        "database_consistency": {
            "status": "pass",
            "record_complete": true,
            "metadata_valid": true
        },
        "vector_index": {
            "status": "healthy",
            "index_exists": true,
            "index_valid": true,
            "chunks_count": 45,
            "embeddings_valid": true
        }
    },
    "warnings": [],
    "errors": [],
    "repair_actions": [],
    "recommendations": [
        "Document integrity is excellent",
        "Consider periodic backup of important documents"
    ]
}
```

## Library Management API

### Library Statistics
**GET** `/api/library/stats`

Get comprehensive library statistics and analytics.

**Query Parameters:**
- `include_trends` (boolean): Include trend data (default: false)
- `date_range` (string): Date range for analytics ('7d', '30d', '90d', 'all')

**Response Example:**
```json
{
    "success": true,
    "statistics": {
        "documents": {
            "total_count": 150,
            "total_size_mb": 2048.5,
            "average_size_mb": 13.65,
            "size_distribution": {
                "small_files_under_5mb": 45,
                "medium_files_5_50mb": 90,
                "large_files_over_50mb": 15
            },
            "page_statistics": {
                "total_pages": 3750,
                "average_pages": 25,
                "median_pages": 18
            }
        },
        "vector_indexes": {
            "indexed_documents": 120,
            "total_chunks": 5400,
            "average_chunks_per_document": 45,
            "index_coverage_percentage": 80.0,
            "total_index_size_mb": 156.2
        },
        "citations": {
            "total_citations": 2450,
            "documents_with_citations": 98,
            "average_citations_per_document": 16.3,
            "citation_networks": 12,
            "unique_authors": 1250,
            "publication_year_range": {
                "earliest": 1995,
                "latest": 2024,
                "most_common": 2023
            }
        },
        "usage_metrics": {
            "total_queries": 850,
            "unique_active_documents": 75,
            "average_queries_per_document": 5.7,
            "most_queried_document_id": 42
        },
        "health_indicators": {
            "documents_with_missing_files": 2,
            "corrupted_indexes": 0,
            "orphaned_citations": 5,
            "overall_health_score": 0.95
        }
    },
    "trends": {
        "upload_trend_7d": [2, 5, 3, 7, 4, 6, 8],
        "query_trend_7d": [15, 23, 18, 31, 25, 28, 22],
        "popular_topics": [
            {"topic": "machine learning", "count": 45},
            {"topic": "artificial intelligence", "count": 38},
            {"topic": "neural networks", "count": 28}
        ]
    },
    "generated_at": "2025-08-09T16:45:00Z"
}
```

### Search Library
**GET** `/api/library/search`

Perform comprehensive library search across documents.

**Query Parameters:**
- `q` (string, required): Search query
- `search_mode` (enum): `full_text|semantic|hybrid` (default: hybrid)
- `include_content` (boolean): Search in document content (default: true)
- `include_metadata` (boolean): Search in metadata (default: true)
- `include_citations` (boolean): Search in citations (default: false)
- `limit` (int): Maximum results (default: 50, max: 200)
- `min_score` (float): Minimum relevance score (0.0-1.0)
- `document_ids` (list): Restrict search to specific documents
- `date_filter` (string): Date range filter ('7d', '30d', '90d', 'all')

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/library/search?q=machine+learning+optimization&search_mode=hybrid&limit=20&min_score=0.7"
```

**Response Example:**
```json
{
    "success": true,
    "query": "machine learning optimization",
    "search_mode": "hybrid",
    "results": [
        {
            "document_id": 1,
            "title": "Machine Learning Optimization Techniques",
            "relevance_score": 0.95,
            "match_type": "title_and_content",
            "matched_snippets": [
                {
                    "text": "Machine learning optimization is crucial for...",
                    "score": 0.92,
                    "page": 5,
                    "context": "introduction"
                }
            ],
            "document_info": {
                "file_size": 2048000,
                "page_count": 25,
                "created_at": "2025-08-09T10:00:00Z",
                "has_vector_index": true,
                "citation_count": 15
            }
        }
    ],
    "search_stats": {
        "total_found": 25,
        "returned": 20,
        "search_time_ms": 150,
        "semantic_matches": 18,
        "keyword_matches": 7,
        "hybrid_score_boost": true
    },
    "suggestions": [
        "optimization algorithms",
        "gradient descent",
        "neural network optimization"
    ]
}
```

### Find Duplicates
**GET** `/api/library/duplicates`

Identify potential duplicate documents in the library.

**Query Parameters:**
- `similarity_threshold` (float): Similarity threshold (0.0-1.0, default: 0.85)
- `check_method` (enum): `content_hash|file_hash|semantic|all` (default: all)
- `include_near_duplicates` (boolean): Include near-duplicates (default: true)

**Response Example:**
```json
{
    "success": true,
    "duplicate_groups": [
        {
            "similarity_score": 0.98,
            "match_type": "content_hash",
            "documents": [
                {
                    "id": 5,
                    "title": "AI Research Paper.pdf",
                    "file_size": 1024000,
                    "created_at": "2025-08-05T10:00:00Z"
                },
                {
                    "id": 12,
                    "title": "AI_Research_Paper_Copy.pdf", 
                    "file_size": 1024000,
                    "created_at": "2025-08-07T15:30:00Z"
                }
            ]
        }
    ],
    "near_duplicates": [
        {
            "similarity_score": 0.87,
            "match_type": "semantic",
            "documents": [
                {
                    "id": 8,
                    "title": "Machine Learning Fundamentals",
                    "similarity_reasons": ["similar_title", "overlapping_content"]
                },
                {
                    "id": 15,
                    "title": "Introduction to ML Concepts"
                }
            ]
        }
    ],
    "summary": {
        "total_duplicate_groups": 1,
        "total_near_duplicate_groups": 1,
        "affected_documents": 4,
        "potential_space_savings_mb": 15.2
    }
}
```

### Library Cleanup
**POST** `/api/library/cleanup`

Perform library maintenance and cleanup operations.

**Request Body:**
```json
{
    "operations": {
        "remove_orphaned_indexes": true,
        "remove_corrupted_data": true,
        "update_missing_metadata": true,
        "optimize_database": true,
        "clean_cache": true,
        "verify_file_integrity": false
    },
    "dry_run": false
}
```

**Response Example:**
```json
{
    "success": true,
    "message": "Library cleanup completed successfully",
    "operations_performed": {
        "orphaned_indexes_removed": 3,
        "corrupted_records_fixed": 1,
        "metadata_updates": 15,
        "database_optimization": "completed",
        "cache_entries_cleaned": 127,
        "space_freed_mb": 45.7
    },
    "warnings": [
        "2 documents have missing physical files but were not removed",
        "Index rebuild recommended for 5 documents"
    ],
    "recommendations": [
        "Run integrity check on documents with IDs: [23, 45, 67]",
        "Consider rebuilding vector indexes for better performance"
    ],
    "cleanup_duration_seconds": 12.5
}
```

## RAG & AI Query API

### Execute RAG Query
**POST** `/api/rag/query`

Perform an AI-powered query against a document using RAG technology.

**Request Body:**
```json
{
    "query": "What are the main findings of this research?",
    "document_id": 1,
    "options": {
        "max_sources": 5,
        "min_relevance_score": 0.7,
        "include_page_numbers": true,
        "response_length": "detailed",
        "temperature": 0.3,
        "use_conversation_context": false
    }
}
```

**Response Example:**
```json
{
    "success": true,
    "answer": "Based on the research presented in this document, the main findings include: 1) Machine learning models showed a 23% improvement in accuracy when optimized using the proposed gradient descent variant. 2) The new algorithm demonstrates better convergence properties compared to traditional methods. 3) Computational efficiency was improved by approximately 15% across all tested scenarios.",
    "sources": [
        {
            "chunk_id": "chunk_15",
            "content": "Our experimental results demonstrate that the proposed optimization technique achieves a 23% improvement in model accuracy...",
            "relevance_score": 0.92,
            "page_number": 8,
            "section": "Results",
            "start_char": 1250,
            "end_char": 1580
        },
        {
            "chunk_id": "chunk_22",
            "content": "The convergence analysis shows that our algorithm reaches optimal solutions 40% faster than baseline methods...",
            "relevance_score": 0.87,
            "page_number": 12,
            "section": "Analysis",
            "start_char": 2100,
            "end_char": 2435
        }
    ],
    "query_metadata": {
        "document_title": "Advanced ML Optimization Techniques",
        "processing_time_ms": 2150,
        "tokens_used": {
            "input_tokens": 1250,
            "output_tokens": 185,
            "total_cost_estimate_usd": 0.0025
        },
        "confidence_score": 0.89,
        "model_used": "gpt-4",
        "retrieval_strategy": "semantic_search"
    }
}
```

### Build Vector Index
**POST** `/api/rag/build-index`

Build or rebuild the vector index for a document to enable RAG queries.

**Request Body:**
```json
{
    "document_id": 1,
    "options": {
        "force_rebuild": false,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "embedding_model": "text-embedding-ada-002",
        "chunk_strategy": "semantic",
        "include_metadata": true,
        "batch_size": 100
    }
}
```

**Response Example:**
```json
{
    "success": true,
    "message": "Vector index built successfully",
    "index_info": {
        "document_id": 1,
        "chunks_created": 45,
        "embedding_model": "text-embedding-ada-002",
        "index_size_mb": 12.5,
        "build_time_seconds": 32.7,
        "chunk_statistics": {
            "average_chunk_size": 950,
            "min_chunk_size": 420,
            "max_chunk_size": 1500,
            "total_characters": 42750
        }
    },
    "processing_details": {
        "text_extraction_time": 3.2,
        "chunking_time": 1.5,
        "embedding_generation_time": 27.8,
        "index_storage_time": 0.2
    },
    "quality_metrics": {
        "text_quality_score": 0.94,
        "chunk_coherence_score": 0.88,
        "coverage_score": 0.96
    }
}
```

### Check Index Status
**GET** `/api/rag/status/{document_id}`

Check the RAG index status for a specific document.

**Path Parameters:**
- `document_id` (int): Document ID

**Response Example:**
```json
{
    "success": true,
    "document_id": 1,
    "index_status": "ready",
    "index_info": {
        "exists": true,
        "chunks_count": 45,
        "embedding_model": "text-embedding-ada-002",
        "index_size_mb": 12.5,
        "created_at": "2025-08-09T14:30:00Z",
        "last_updated": "2025-08-09T14:30:00Z"
    },
    "capabilities": {
        "query_ready": true,
        "semantic_search": true,
        "similarity_threshold": 0.7,
        "max_retrievable_chunks": 45
    },
    "performance_stats": {
        "average_query_time_ms": 150,
        "cache_hit_rate": 0.65,
        "total_queries": 23
    },
    "recommendations": []
}
```

### Multi-Document Query
**POST** `/api/rag/query-multi`

Execute a query across multiple documents simultaneously.

**Request Body:**
```json
{
    "query": "Compare the methodologies used across these papers",
    "document_ids": [1, 5, 8, 12],
    "options": {
        "max_sources_per_document": 3,
        "aggregation_strategy": "synthesis",
        "include_document_comparison": true,
        "min_relevance_score": 0.7
    }
}
```

**Response Example:**
```json
{
    "success": true,
    "synthesized_answer": "Across the analyzed papers, three main methodological approaches emerge: 1) Traditional gradient descent optimization (Papers 1, 5), 2) Advanced neural architecture search (Papers 8, 12), and 3) Hybrid ensemble methods (Papers 1, 8). Each approach shows distinct advantages in different scenarios...",
    "document_responses": [
        {
            "document_id": 1,
            "document_title": "ML Optimization Techniques",
            "answer": "This paper primarily uses gradient descent optimization with adaptive learning rates...",
            "sources": [...],
            "relevance_to_query": 0.91
        }
    ],
    "comparative_analysis": {
        "common_themes": [
            "optimization efficiency",
            "convergence properties",
            "computational complexity"
        ],
        "contrasting_approaches": [
            {
                "aspect": "learning_rate_adaptation",
                "document_1": "fixed schedule",
                "document_5": "adaptive adjustment"
            }
        ]
    },
    "aggregate_metadata": {
        "total_processing_time_ms": 5200,
        "documents_analyzed": 4,
        "total_sources_considered": 32,
        "synthesis_confidence": 0.86
    }
}
```

## Citation Management API

### Extract Citations
**POST** `/api/citations/extract/{document_id}`

Extract academic citations from a document.

**Path Parameters:**
- `document_id` (int): Document ID

**Request Body:**
```json
{
    "options": {
        "confidence_threshold": 0.8,
        "extract_metadata": true,
        "resolve_doi": true,
        "format_standardization": true,
        "duplicate_detection": true
    },
    "text_content": "optional_text_override"
}
```

**Response Example:**
```json
{
    "success": true,
    "message": "Successfully extracted 12 citations",
    "extraction_summary": {
        "total_citations": 12,
        "high_confidence_citations": 9,
        "medium_confidence_citations": 2,
        "low_confidence_citations": 1,
        "average_confidence_score": 0.87
    },
    "citations": [
        {
            "id": 45,
            "raw_text": "Smith, J., & Johnson, M. (2023). Advanced Machine Learning Techniques. Journal of AI Research, 15(3), 123-145. https://doi.org/10.1000/jar.2023.001",
            "parsed_fields": {
                "authors": "Smith, J.; Johnson, M.",
                "title": "Advanced Machine Learning Techniques",
                "journal": "Journal of AI Research",
                "volume": "15",
                "issue": "3",
                "pages": "123-145",
                "year": 2023,
                "doi": "10.1000/jar.2023.001"
            },
            "citation_type": "journal_article",
            "confidence_score": 0.95,
            "metadata": {
                "extraction_method": "regex_pattern",
                "validation_status": "verified",
                "doi_resolved": true,
                "author_count": 2
            },
            "position_info": {
                "page_number": 15,
                "line_number": 342,
                "context": "As demonstrated by Smith and Johnson (2023), advanced ML techniques..."
            }
        }
    ],
    "processing_info": {
        "extraction_time_seconds": 8.5,
        "text_processing_method": "combined_extraction",
        "patterns_matched": 15,
        "manual_review_suggested": 1
    }
}
```

### List Citations
**GET** `/api/citations/document/{document_id}`

Retrieve citations for a specific document with filtering options.

**Path Parameters:**
- `document_id` (int): Document ID

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `limit` (int): Citations per page (default: 50)
- `min_confidence` (float): Minimum confidence score filter
- `citation_type` (string): Filter by citation type
- `year_from` (int): Filter citations from this year
- `year_to` (int): Filter citations up to this year
- `sort_by` (enum): `confidence|year|author|title`
- `sort_order` (enum): `asc|desc`

**Response Example:**
```json
{
    "success": true,
    "citations": [
        {
            "id": 45,
            "raw_text": "Smith, J., & Johnson, M. (2023). Advanced Machine Learning Techniques...",
            "authors": "Smith, J.; Johnson, M.",
            "title": "Advanced Machine Learning Techniques",
            "journal": "Journal of AI Research",
            "year": 2023,
            "citation_type": "journal_article",
            "confidence_score": 0.95,
            "doi": "10.1000/jar.2023.001",
            "created_at": "2025-08-09T10:15:00Z"
        }
    ],
    "pagination": {
        "page": 1,
        "limit": 50,
        "total": 12,
        "pages": 1
    },
    "statistics": {
        "total_citations": 12,
        "by_type": {
            "journal_article": 8,
            "conference_paper": 3,
            "book": 1
        },
        "by_confidence": {
            "high": 9,
            "medium": 2,
            "low": 1
        },
        "year_distribution": {
            "2023": 5,
            "2022": 4,
            "2021": 3
        }
    }
}
```

### Search Citations
**GET** `/api/citations/search`

Search citations across all documents with advanced filtering.

**Query Parameters:**
- `q` (string): Search query (searches in title, authors, journal)
- `author` (string): Author name filter (fuzzy matching)
- `title` (string): Title keyword filter
- `journal` (string): Journal/venue filter
- `year_from` (int): Start year filter
- `year_to` (int): End year filter
- `citation_type` (string): Citation type filter
- `doi` (string): DOI exact match
- `min_confidence` (float): Minimum confidence score
- `document_ids` (list): Restrict to specific documents
- `limit` (int): Maximum results (default: 50)
- `include_context` (boolean): Include citation context

**Example Request:**
```bash
curl -X GET "http://localhost:8000/api/citations/search?author=Smith&year_from=2020&min_confidence=0.8&limit=20"
```

**Response Example:**
```json
{
    "success": true,
    "search_results": [
        {
            "id": 45,
            "document_id": 1,
            "document_title": "ML Research Paper",
            "citation": {
                "authors": "Smith, J.; Johnson, M.",
                "title": "Advanced Machine Learning Techniques",
                "journal": "Journal of AI Research",
                "year": 2023,
                "confidence_score": 0.95
            },
            "context": {
                "surrounding_text": "As demonstrated by Smith and Johnson (2023), advanced ML techniques show significant improvements...",
                "page_number": 15,
                "section": "Related Work"
            },
            "relevance_score": 0.92
        }
    ],
    "search_metadata": {
        "total_found": 25,
        "returned": 20,
        "search_time_ms": 45,
        "filters_applied": {
            "author": "Smith",
            "year_from": 2020,
            "min_confidence": 0.8
        }
    },
    "aggregations": {
        "top_authors": [
            {"name": "Smith, J.", "count": 8},
            {"name": "Johnson, M.", "count": 6}
        ],
        "publication_years": [
            {"year": 2023, "count": 12},
            {"year": 2022, "count": 8}
        ],
        "top_journals": [
            {"name": "Journal of AI Research", "count": 5},
            {"name": "Machine Learning Conference", "count": 4}
        ]
    }
}
```

### Citation Network Analysis
**GET** `/api/citations/network/{document_id}`

Generate citation network analysis for a document.

**Path Parameters:**
- `document_id` (int): Center document ID

**Query Parameters:**
- `depth` (int): Network depth (1-3, default: 2)
- `min_confidence` (float): Minimum citation confidence (default: 0.7)
- `max_nodes` (int): Maximum nodes in network (default: 50)
- `include_metrics` (boolean): Include network metrics (default: true)

**Response Example:**
```json
{
    "success": true,
    "network": {
        "center_document": {
            "id": 1,
            "title": "ML Optimization Techniques",
            "citation_count": 15,
            "cited_by_count": 8
        },
        "nodes": [
            {
                "id": "doc_1",
                "type": "document",
                "title": "ML Optimization Techniques",
                "properties": {
                    "year": 2023,
                    "citation_count": 15,
                    "centrality": 0.85,
                    "cluster": "optimization"
                }
            },
            {
                "id": "cit_45",
                "type": "citation",
                "title": "Advanced ML Techniques",
                "properties": {
                    "authors": "Smith, J.; Johnson, M.",
                    "year": 2023,
                    "confidence": 0.95,
                    "citation_type": "journal_article"
                }
            }
        ],
        "edges": [
            {
                "source": "doc_1",
                "target": "cit_45",
                "type": "cites",
                "properties": {
                    "confidence": 0.95,
                    "context": "methodology",
                    "importance": 0.88
                }
            }
        ]
    },
    "network_metrics": {
        "total_nodes": 25,
        "total_edges": 32,
        "density": 0.12,
        "average_degree": 2.56,
        "clustering_coefficient": 0.34,
        "connected_components": 3
    },
    "clusters": [
        {
            "id": "optimization",
            "size": 12,
            "keywords": ["optimization", "gradient descent", "convergence"],
            "central_nodes": ["doc_1", "cit_45"]
        }
    ],
    "insights": {
        "most_influential_citations": [
            {"id": "cit_45", "influence_score": 0.92},
            {"id": "cit_23", "influence_score": 0.87}
        ],
        "research_trends": [
            "Increased focus on optimization efficiency",
            "Growing interest in adaptive learning rates"
        ],
        "collaboration_patterns": [
            "Strong connection between optimization and neural networks research"
        ]
    }
}
```

## Settings & Configuration API

### Get Settings
**GET** `/api/settings`

Retrieve current application settings and configuration.

**Response Example:**
```json
{
    "success": true,
    "settings": {
        "rag": {
            "enabled": true,
            "gemini_api_key_configured": true,
            "auto_build_index": false,
            "default_embedding_model": "text-embedding-ada-002",
            "max_query_length": 5000,
            "default_chunk_size": 1000,
            "default_chunk_overlap": 200
        },
        "ui": {
            "theme": "light",
            "language": "en",
            "items_per_page": 50,
            "enable_animations": true,
            "auto_save": true
        },
        "storage": {
            "storage_path": "~/.ai_pdf_scholar",
            "max_file_size_mb": 100,
            "auto_cleanup": true,
            "backup_enabled": false
        },
        "performance": {
            "cache_enabled": true,
            "cache_size_mb": 512,
            "max_concurrent_operations": 5,
            "enable_compression": true
        },
        "security": {
            "rate_limiting_enabled": true,
            "requests_per_minute": 100,
            "enable_cors": true,
            "allowed_origins": ["http://localhost:3000"]
        }
    },
    "system_info": {
        "version": "2.1.0",
        "environment": "development",
        "last_updated": "2025-08-09T16:00:00Z"
    }
}
```

### Update Settings
**POST** `/api/settings`

Update application settings and configuration.

**Request Body:**
```json
{
    "rag": {
        "gemini_api_key": "your-new-api-key",
        "auto_build_index": true,
        "default_chunk_size": 1200
    },
    "ui": {
        "theme": "dark",
        "items_per_page": 25
    },
    "performance": {
        "cache_size_mb": 1024,
        "max_concurrent_operations": 8
    }
}
```

**Response Example:**
```json
{
    "success": true,
    "message": "Settings updated successfully",
    "updated_settings": [
        "rag.gemini_api_key",
        "rag.auto_build_index",
        "rag.default_chunk_size",
        "ui.theme",
        "ui.items_per_page",
        "performance.cache_size_mb",
        "performance.max_concurrent_operations"
    ],
    "warnings": [
        "API key change requires restart for full effect",
        "Cache size increase will use more memory"
    ],
    "restart_required": false,
    "validation_results": {
        "gemini_api_key": "valid",
        "chunk_size": "acceptable_range",
        "cache_size": "memory_sufficient"
    }
}
```

## WebSocket API

### Connection Endpoint
**WebSocket** `/ws/{client_id}`

Establish a WebSocket connection for real-time communication.

**Path Parameters:**
- `client_id` (string): Unique client identifier

### Message Types

#### Client → Server Messages

##### Ping
```json
{
    "type": "ping",
    "timestamp": "2025-08-09T16:00:00Z"
}
```

##### RAG Query
```json
{
    "type": "rag_query",
    "query": "What is the main contribution of this paper?",
    "document_id": 1,
    "options": {
        "max_sources": 5,
        "include_citations": true
    }
}
```

##### Subscribe to Events
```json
{
    "type": "subscribe",
    "events": [
        "document.uploaded",
        "index.built",
        "citation.extracted"
    ]
}
```

#### Server → Client Messages

##### Pong
```json
{
    "type": "pong",
    "timestamp": "2025-08-09T16:00:00Z"
}
```

##### RAG Response
```json
{
    "type": "rag_response",
    "request_id": "req_123",
    "query": "What is the main contribution of this paper?",
    "answer": "The main contribution is the development of a novel optimization algorithm...",
    "sources": [...],
    "processing_time_ms": 2150
}
```

##### Progress Updates
```json
{
    "type": "progress",
    "operation": "index_building",
    "document_id": 1,
    "progress": 65,
    "message": "Processing chunks (30/45)...",
    "estimated_completion": "2025-08-09T16:02:00Z"
}
```

##### Event Notifications
```json
{
    "type": "event",
    "event_name": "document.uploaded",
    "data": {
        "document_id": 5,
        "title": "New Research Paper",
        "file_size": 1536000
    },
    "timestamp": "2025-08-09T16:00:00Z"
}
```

### WebSocket Example Usage

#### JavaScript Client
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/client_123');

ws.onopen = () => {
    console.log('Connected to WebSocket');
    
    // Subscribe to events
    ws.send(JSON.stringify({
        type: 'subscribe',
        events: ['document.uploaded', 'index.built']
    }));
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch(message.type) {
        case 'rag_response':
            displayAnswer(message.answer, message.sources);
            break;
        case 'progress':
            updateProgressBar(message.progress, message.message);
            break;
        case 'event':
            handleSystemEvent(message.event_name, message.data);
            break;
    }
};

// Send RAG query
function sendQuery(query, documentId) {
    ws.send(JSON.stringify({
        type: 'rag_query',
        query: query,
        document_id: documentId
    }));
}
```

## Error Handling

### Standard Error Response Format
```json
{
    "detail": "Human-readable error message",
    "error_code": "ERROR_CODE_CONSTANT",
    "status_code": 400,
    "timestamp": "2025-08-09T16:00:00Z",
    "request_id": "req_1234567890",
    "validation_errors": [
        {
            "field": "document_id",
            "message": "Document ID is required",
            "code": "MISSING_FIELD"
        }
    ],
    "context": {
        "operation": "document_upload",
        "resource_id": 123,
        "user_action": "upload_pdf"
    }
}
```

### Common Error Codes

#### Document Management Errors
- `DOCUMENT_NOT_FOUND`: Document with specified ID does not exist
- `DOCUMENT_NOT_ACCESSIBLE`: Document file is not accessible
- `FILE_TOO_LARGE`: File size exceeds maximum limit
- `UNSUPPORTED_FORMAT`: File format not supported
- `DUPLICATE_DOCUMENT`: Document already exists in library
- `DOCUMENT_CORRUPTED`: Document file is corrupted or unreadable

#### RAG/AI Errors
- `RAG_SERVICE_UNAVAILABLE`: RAG service not configured or unavailable
- `API_KEY_NOT_CONFIGURED`: AI API key not set
- `VECTOR_INDEX_NOT_FOUND`: Vector index does not exist for document
- `QUERY_TOO_LONG`: Query exceeds maximum length limit
- `INSUFFICIENT_CONTEXT`: Not enough context for meaningful response
- `AI_SERVICE_ERROR`: Error from external AI service

#### Citation Errors
- `CITATION_EXTRACTION_FAILED`: Failed to extract citations from document
- `CITATION_NOT_FOUND`: Citation with specified ID does not exist
- `INVALID_CITATION_FORMAT`: Citation format is invalid
- `CITATION_PARSING_ERROR`: Error parsing citation text

#### System Errors
- `DATABASE_ERROR`: Database operation failed
- `STORAGE_ERROR`: File system error
- `INSUFFICIENT_STORAGE`: Not enough disk space
- `CONFIGURATION_ERROR`: System configuration error
- `SERVICE_UNAVAILABLE`: Service temporarily unavailable

### Error Handling Best Practices

#### Client-Side Error Handling
```javascript
async function handleApiCall(apiFunction) {
    try {
        const response = await apiFunction();
        return response;
    } catch (error) {
        if (error.status === 404) {
            showUserMessage("Document not found", "error");
        } else if (error.status === 429) {
            showUserMessage("Too many requests. Please wait and try again.", "warning");
        } else if (error.status >= 500) {
            showUserMessage("Server error. Please try again later.", "error");
            // Log error for debugging
            console.error("Server error:", error);
        } else {
            showUserMessage(error.detail || "An error occurred", "error");
        }
        throw error;
    }
}
```

#### Python Client Error Handling
```python
import requests
from typing import Dict, Any

class APIError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str, context: Dict[str, Any] = None):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.context = context or {}
        super().__init__(message)

def handle_api_response(response: requests.Response) -> Dict[str, Any]:
    if response.ok:
        return response.json()
    
    try:
        error_data = response.json()
        raise APIError(
            status_code=response.status_code,
            error_code=error_data.get('error_code', 'UNKNOWN_ERROR'),
            message=error_data.get('detail', 'An error occurred'),
            context=error_data.get('context', {})
        )
    except ValueError:
        raise APIError(
            status_code=response.status_code,
            error_code='HTTP_ERROR',
            message=f"HTTP {response.status_code}: {response.reason}"
        )

# Usage example
try:
    response = requests.get("http://localhost:8000/api/documents/999")
    data = handle_api_response(response)
except APIError as e:
    if e.error_code == 'DOCUMENT_NOT_FOUND':
        print("Document not found. Please check the document ID.")
    elif e.status_code >= 500:
        print("Server error. Please try again later.")
    else:
        print(f"Error: {e.message}")
```

## Rate Limiting

### Rate Limit Headers
All API responses include rate limiting information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1691589600
X-RateLimit-Window: 60
```

### Rate Limit Categories

#### General API Calls
- **Limit**: 100 requests per minute
- **Scope**: Per IP address
- **Reset**: Rolling window

#### File Uploads
- **Limit**: 10 uploads per minute
- **Scope**: Per IP address
- **Reset**: Rolling window

#### RAG Queries
- **Limit**: 20 queries per minute
- **Scope**: Per IP address
- **Reset**: Rolling window
- **Additional**: Token-based limiting for AI API usage

#### Citation Extraction
- **Limit**: 5 extractions per minute
- **Scope**: Per IP address
- **Reset**: Rolling window

### Rate Limit Exceeded Response
```json
{
    "detail": "Rate limit exceeded. Try again in 30 seconds.",
    "error_code": "RATE_LIMIT_EXCEEDED",
    "status_code": 429,
    "retry_after": 30,
    "limit_info": {
        "limit": 100,
        "remaining": 0,
        "reset_time": "2025-08-09T16:01:00Z",
        "window_seconds": 60
    }
}
```

## SDK Examples

### Python SDK Example

```python
"""
AI Enhanced PDF Scholar Python SDK
"""

import requests
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

class PDFScholarClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated API request"""
        url = f"{self.base_url}/api/{endpoint.lstrip('/')}"
        response = self.session.request(method, url, **kwargs)
        
        if not response.ok:
            error_data = response.json() if response.content else {}
            raise Exception(f"API Error {response.status_code}: {error_data.get('detail', response.reason)}")
        
        return response.json()
    
    # System Management
    def health_check(self) -> Dict[str, Any]:
        """Check system health status"""
        return self._request('GET', 'system/health')
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration"""
        return self._request('GET', 'system/config')
    
    # Document Management
    def list_documents(self, page: int = 1, per_page: int = 50, **filters) -> Dict[str, Any]:
        """List documents with pagination and filtering"""
        params = {'page': page, 'per_page': per_page, **filters}
        return self._request('GET', 'documents/', params=params)
    
    def get_document(self, document_id: int, include_content: bool = False) -> Dict[str, Any]:
        """Get document details"""
        params = {'include_content': include_content} if include_content else {}
        return self._request('GET', f'documents/{document_id}', params=params)
    
    def upload_document(self, file_path: Path, title: str = None, **options) -> Dict[str, Any]:
        """Upload a PDF document"""
        files = {'file': open(file_path, 'rb')}
        data = {}
        
        if title:
            data['title'] = title
        
        # Add upload options
        for key, value in options.items():
            data[key] = str(value).lower() if isinstance(value, bool) else str(value)
        
        try:
            return self._request('POST', 'documents/upload', files=files, data=data)
        finally:
            files['file'].close()
    
    def delete_document(self, document_id: int, delete_file: bool = True) -> Dict[str, Any]:
        """Delete a document"""
        params = {'delete_file': delete_file}
        return self._request('DELETE', f'documents/{document_id}', params=params)
    
    # RAG Operations
    def rag_query(self, query: str, document_id: int, **options) -> Dict[str, Any]:
        """Execute RAG query against a document"""
        data = {
            'query': query,
            'document_id': document_id,
            'options': options
        }
        return self._request('POST', 'rag/query', json=data)
    
    def build_vector_index(self, document_id: int, force_rebuild: bool = False, **options) -> Dict[str, Any]:
        """Build vector index for a document"""
        data = {
            'document_id': document_id,
            'options': {
                'force_rebuild': force_rebuild,
                **options
            }
        }
        return self._request('POST', 'rag/build-index', json=data)
    
    def check_index_status(self, document_id: int) -> Dict[str, Any]:
        """Check vector index status"""
        return self._request('GET', f'rag/status/{document_id}')
    
    # Citation Management
    def extract_citations(self, document_id: int, **options) -> Dict[str, Any]:
        """Extract citations from a document"""
        data = {'options': options} if options else {}
        return self._request('POST', f'citations/extract/{document_id}', json=data)
    
    def list_citations(self, document_id: int, page: int = 1, limit: int = 50, **filters) -> Dict[str, Any]:
        """List citations for a document"""
        params = {'page': page, 'limit': limit, **filters}
        return self._request('GET', f'citations/document/{document_id}', params=params)
    
    def search_citations(self, **search_params) -> Dict[str, Any]:
        """Search citations across all documents"""
        return self._request('GET', 'citations/search', params=search_params)
    
    # Library Management
    def library_stats(self, include_trends: bool = False) -> Dict[str, Any]:
        """Get library statistics"""
        params = {'include_trends': include_trends}
        return self._request('GET', 'library/stats', params=params)
    
    def search_library(self, query: str, **options) -> Dict[str, Any]:
        """Search library documents"""
        params = {'q': query, **options}
        return self._request('GET', 'library/search', params=params)
    
    def cleanup_library(self, operations: Dict[str, bool], dry_run: bool = False) -> Dict[str, Any]:
        """Perform library cleanup"""
        data = {'operations': operations, 'dry_run': dry_run}
        return self._request('POST', 'library/cleanup', json=data)

# Usage Example
def main():
    client = PDFScholarClient()
    
    # Check system health
    health = client.health_check()
    print(f"System status: {health['status']}")
    
    # Upload document
    doc_path = Path("research_paper.pdf")
    if doc_path.exists():
        result = client.upload_document(
            doc_path,
            title="My Research Paper",
            check_duplicates=True,
            auto_build_index=True
        )
        document_id = result['document']['id']
        print(f"Uploaded document ID: {document_id}")
        
        # Wait for index to be built, then query
        import time
        time.sleep(10)  # Wait for index building
        
        answer = client.rag_query(
            "What is this paper about?",
            document_id,
            max_sources=5
        )
        print(f"Answer: {answer['answer']}")

if __name__ == "__main__":
    main()
```

### JavaScript/TypeScript SDK Example

```typescript
/**
 * AI Enhanced PDF Scholar TypeScript SDK
 */

interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  timestamp?: string;
  request_id?: string;
}

interface Document {
  id: number;
  title: string;
  file_path: string;
  file_size: number;
  page_count: number;
  created_at: string;
  updated_at: string;
  is_file_available: boolean;
  has_vector_index: boolean;
  citation_count?: number;
  metadata?: Record<string, any>;
}

interface RAGResponse {
  answer: string;
  sources: Array<{
    chunk_id: string;
    content: string;
    relevance_score: number;
    page_number?: number;
  }>;
  query_metadata: {
    processing_time_ms: number;
    confidence_score: number;
    tokens_used?: {
      input_tokens: number;
      output_tokens: number;
      total_cost_estimate_usd: number;
    };
  };
}

class PDFScholarClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  private async request<T = any>(
    method: string,
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}/api/${endpoint.replace(/^\//, '')}`;
    
    const config: RequestInit = {
      method,
      headers: {
        ...this.defaultHeaders,
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(url, config);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `HTTP ${response.status}: ${response.statusText}`
      );
    }

    return await response.json();
  }

  // System Management
  async healthCheck(): Promise<ApiResponse> {
    return this.request('GET', 'system/health');
  }

  async getSystemConfig(): Promise<ApiResponse> {
    return this.request('GET', 'system/config');
  }

  // Document Management
  async listDocuments(
    page: number = 1,
    perPage: number = 50,
    filters: Record<string, any> = {}
  ): Promise<ApiResponse<{ documents: Document[] }>> {
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString(),
      ...Object.fromEntries(
        Object.entries(filters).map(([k, v]) => [k, String(v)])
      ),
    });

    return this.request('GET', `documents/?${params}`);
  }

  async getDocument(
    documentId: number,
    includeContent: boolean = false
  ): Promise<ApiResponse<{ document: Document }>> {
    const params = includeContent ? '?include_content=true' : '';
    return this.request('GET', `documents/${documentId}${params}`);
  }

  async uploadDocument(
    file: File,
    options: {
      title?: string;
      tags?: string;
      checkDuplicates?: boolean;
      autoBuildIndex?: boolean;
      extractCitations?: boolean;
      metadata?: Record<string, any>;
    } = {}
  ): Promise<ApiResponse<{ document: Document }>> {
    const formData = new FormData();
    formData.append('file', file);

    if (options.title) formData.append('title', options.title);
    if (options.tags) formData.append('tags', options.tags);
    if (options.checkDuplicates !== undefined) {
      formData.append('check_duplicates', options.checkDuplicates.toString());
    }
    if (options.autoBuildIndex !== undefined) {
      formData.append('auto_build_index', options.autoBuildIndex.toString());
    }
    if (options.extractCitations !== undefined) {
      formData.append('extract_citations', options.extractCitations.toString());
    }
    if (options.metadata) {
      formData.append('metadata', JSON.stringify(options.metadata));
    }

    // Remove Content-Type header to let browser set it with boundary
    const headers = { ...this.defaultHeaders };
    delete headers['Content-Type'];

    return this.request('POST', 'documents/upload', {
      body: formData,
      headers,
    });
  }

  async deleteDocument(
    documentId: number,
    deleteFile: boolean = true
  ): Promise<ApiResponse> {
    const params = `?delete_file=${deleteFile}`;
    return this.request('DELETE', `documents/${documentId}${params}`);
  }

  // RAG Operations
  async ragQuery(
    query: string,
    documentId: number,
    options: {
      maxSources?: number;
      minRelevanceScore?: number;
      includePageNumbers?: boolean;
      responseLength?: 'brief' | 'detailed' | 'comprehensive';
      temperature?: number;
    } = {}
  ): Promise<ApiResponse<RAGResponse>> {
    return this.request('POST', 'rag/query', {
      body: JSON.stringify({
        query,
        document_id: documentId,
        options,
      }),
    });
  }

  async buildVectorIndex(
    documentId: number,
    options: {
      forceRebuild?: boolean;
      chunkSize?: number;
      chunkOverlap?: number;
      embeddingModel?: string;
      chunkStrategy?: 'fixed' | 'semantic' | 'paragraph';
    } = {}
  ): Promise<ApiResponse> {
    return this.request('POST', 'rag/build-index', {
      body: JSON.stringify({
        document_id: documentId,
        options,
      }),
    });
  }

  async checkIndexStatus(documentId: number): Promise<ApiResponse> {
    return this.request('GET', `rag/status/${documentId}`);
  }

  // Citation Management
  async extractCitations(
    documentId: number,
    options: {
      confidenceThreshold?: number;
      extractMetadata?: boolean;
      resolveDoi?: boolean;
      formatStandardization?: boolean;
    } = {}
  ): Promise<ApiResponse> {
    return this.request('POST', `citations/extract/${documentId}`, {
      body: JSON.stringify({ options }),
    });
  }

  async searchCitations(searchParams: {
    q?: string;
    author?: string;
    title?: string;
    journal?: string;
    yearFrom?: number;
    yearTo?: number;
    citationType?: string;
    doi?: string;
    minConfidence?: number;
    limit?: number;
  }): Promise<ApiResponse> {
    const params = new URLSearchParams(
      Object.fromEntries(
        Object.entries(searchParams)
          .filter(([_, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      )
    );

    return this.request('GET', `citations/search?${params}`);
  }

  // Library Management
  async getLibraryStats(includeTrends: boolean = false): Promise<ApiResponse> {
    const params = includeTrends ? '?include_trends=true' : '';
    return this.request('GET', `library/stats${params}`);
  }

  async searchLibrary(
    query: string,
    options: {
      searchMode?: 'full_text' | 'semantic' | 'hybrid';
      includeContent?: boolean;
      includeMetadata?: boolean;
      limit?: number;
      minScore?: number;
    } = {}
  ): Promise<ApiResponse> {
    const params = new URLSearchParams({
      q: query,
      ...Object.fromEntries(
        Object.entries(options).map(([k, v]) => [k, String(v)])
      ),
    });

    return this.request('GET', `library/search?${params}`);
  }

  // WebSocket Connection
  createWebSocketConnection(clientId: string): WebSocket {
    const wsUrl = this.baseUrl.replace(/^http/, 'ws') + `/ws/${clientId}`;
    return new WebSocket(wsUrl);
  }
}

// Usage Example
async function main() {
  const client = new PDFScholarClient();

  try {
    // Check system health
    const health = await client.healthCheck();
    console.log('System status:', health.data?.status);

    // List documents
    const docs = await client.listDocuments(1, 10);
    console.log('Found documents:', docs.data?.documents?.length);

    // Upload and process document
    const fileInput = document.getElementById('file-input') as HTMLInputElement;
    if (fileInput?.files?.[0]) {
      const uploadResult = await client.uploadDocument(fileInput.files[0], {
        title: 'My Research Paper',
        checkDuplicates: true,
        autoBuildIndex: true,
      });

      const documentId = uploadResult.data?.document?.id;
      if (documentId) {
        // Wait for index to build, then query
        setTimeout(async () => {
          const answer = await client.ragQuery(
            'What is this paper about?',
            documentId,
            { maxSources: 5 }
          );
          console.log('AI Answer:', answer.data?.answer);
        }, 10000);
      }
    }

    // WebSocket example
    const ws = client.createWebSocketConnection('client_123');
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('WebSocket message:', message);
    };

  } catch (error) {
    console.error('API Error:', error);
  }
}

export { PDFScholarClient, type Document, type RAGResponse, type ApiResponse };
```

## Changelog

### v2.1.0 (2025-08-09)
- **Added**: Multi-document RAG queries
- **Added**: Advanced citation network analysis
- **Added**: Real-time WebSocket notifications
- **Added**: Comprehensive search with semantic matching
- **Enhanced**: Error handling with detailed error codes
- **Enhanced**: Rate limiting with per-operation limits
- **Enhanced**: Performance monitoring and metrics
- **Fixed**: Vector index consistency issues
- **Fixed**: Citation extraction accuracy improvements

### v2.0.0 (2025-07-15)
- **Breaking**: Complete migration from PyQt to Web UI
- **Added**: RESTful API with FastAPI
- **Added**: Citation extraction and management
- **Added**: Vector-based RAG system
- **Added**: WebSocket support for real-time updates
- **Added**: Comprehensive library management
- **Added**: Document integrity checking
- **Removed**: All PyQt desktop components

### v1.x (Legacy)
- Desktop application with PyQt interface
- Basic document management
- Limited AI integration

---

**Documentation Version**: 2.1.0  
**Last Updated**: 2025-08-09  
**API Compatibility**: v2.x  
**Status**: Active Development

For the most up-to-date API documentation, visit: `http://localhost:8000/api/docs`