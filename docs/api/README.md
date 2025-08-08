# 📖 AI Enhanced PDF Scholar - API Documentation

## 🎯 Overview

This directory contains comprehensive API documentation for the **AI Enhanced PDF Scholar** platform. The API provides enterprise-grade functionality for intelligent document management, RAG operations, citation analysis, and real-time features.

## 📁 Documentation Structure

```
docs/api/
├── README.md                 # This file - API documentation overview
├── openapi_spec.yaml        # Complete OpenAPI 3.0 specification
├── examples/                 # Request/response examples and code samples
│   ├── authentication.md    # Authentication examples
│   ├── document_upload.md   # Document upload examples
│   ├── rag_queries.md      # RAG query examples
│   └── citation_analysis.md # Citation analysis examples
├── guides/                  # Integration guides and tutorials
│   ├── quick_start.md      # Quick start guide for developers
│   ├── authentication.md   # Authentication guide
│   ├── rate_limiting.md    # Rate limiting details
│   └── websockets.md       # WebSocket integration guide
└── schemas/                 # JSON schema definitions
    ├── models.json         # All data models
    ├── requests.json       # Request schemas
    └── responses.json      # Response schemas
```

## 🚀 Quick Start

### Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://api.pdf-scholar.com`

### Authentication
Most endpoints require JWT authentication. Include your token in the Authorization header:

```bash
curl -H "Authorization: Bearer <your_jwt_token>" \
     -H "Content-Type: application/json" \
     https://api.pdf-scholar.com/api/documents
```

### Interactive Documentation
- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`

## 🔧 Core API Endpoints

### 🔐 Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh JWT token
- `POST /api/auth/logout` - User logout

### 📄 Document Management
- `GET /api/documents` - List documents with filtering
- `POST /api/documents` - Upload new document
- `GET /api/documents/{id}` - Get document details
- `PATCH /api/documents/{id}` - Update document metadata
- `DELETE /api/documents/{id}` - Delete document
- `GET /api/documents/{id}/download` - Download document file

### 🧠 RAG (Retrieval-Augmented Generation)
- `POST /api/rag/query` - Query documents with AI
- `POST /api/rag/index/{id}` - Index document for RAG
- `GET /api/rag/status/{id}` - Check indexing status

### 📊 Citation Analysis
- `POST /api/citations/extract` - Extract citations from document
- `GET /api/citations/network/{id}` - Build citation network
- `POST /api/citations/export` - Export citations (BibTeX, EndNote, etc.)

### 📚 Library Management
- `GET /api/library/stats` - Get library statistics
- `GET /api/library/health` - Check library integrity

### 🔍 System & Monitoring
- `GET /api/system/health` - System health check
- `GET /api/system/version` - Get version info
- `GET /api/performance/overview` - Performance metrics
- `GET /api/performance/cache/analytics` - Cache analytics

### 🌐 Real-time Features
- `WebSocket /ws/{client_id}` - Real-time communication

## 📝 Request/Response Format

### Standard Response Structure
All API responses follow a consistent structure:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Actual response data
  },
  "timestamp": "2025-01-19T10:30:00Z"
}
```

### Error Response Structure
```json
{
  "success": false,
  "message": "Error description",
  "error_code": "VALIDATION_ERROR",
  "details": {
    // Additional error details
  },
  "timestamp": "2025-01-19T10:30:00Z"
}
```

## 🔒 Security Features

### JWT Authentication
- **Access tokens**: Short-lived (15 minutes)
- **Refresh tokens**: Long-lived (7 days)
- **Algorithm**: RS256 with key rotation

### Rate Limiting
- **Default**: 100 requests/minute per IP
- **Global**: 1000 requests/hour per IP
- **Authenticated users**: Higher limits

### Request Validation
- Input sanitization and XSS protection
- File type and size validation
- SQL injection prevention
- CORS policy enforcement

### Security Headers
- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options, X-Content-Type-Options
- Referrer Policy

## 📊 Performance Features

### Caching Strategy
- **Redis**: Distributed caching for production
- **In-Memory**: Development fallback
- **Cache layers**: API responses, vector indexes, metadata

### Optimization
- **Pagination**: All list endpoints support pagination
- **Compression**: Gzip compression for responses
- **Connection pooling**: Database connection optimization
- **Async processing**: Background tasks for heavy operations

### Monitoring
- **APM**: Application performance monitoring
- **Metrics**: Request latency, throughput, error rates
- **Health checks**: Component status monitoring
- **Alerting**: Automated performance alerts

## 🧪 Testing & Development

### Testing the API
```bash
# Health check (no auth required)
curl http://localhost:8000/api/system/health

# Login to get token
curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "test@example.com", "password": "password123"}'

# Use token for authenticated requests
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/documents
```

### OpenAPI Integration
The API is fully documented with OpenAPI 3.0 specification:
- **File**: [`openapi_spec.yaml`](./openapi_spec.yaml)
- **Usage**: Import into Postman, Insomnia, or other API tools
- **Code generation**: Generate client SDKs for various languages

## 🔗 Integration Examples

### Python Client
```python
import requests

class PDFScholarClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def upload_document(self, file_path):
        with open(file_path, 'rb') as f:
            files = {"file": f}
            response = requests.post(
                f"{self.base_url}/api/documents",
                files=files,
                headers=self.headers
            )
        return response.json()
    
    def query_rag(self, query, document_id=None):
        data = {"query": query}
        if document_id:
            data["document_id"] = document_id
            
        response = requests.post(
            f"{self.base_url}/api/rag/query",
            json=data,
            headers=self.headers
        )
        return response.json()
```

### JavaScript/TypeScript Client
```typescript
class PDFScholarAPI {
  private baseUrl: string;
  private token: string;

  constructor(baseUrl: string, token: string) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  async uploadDocument(file: File): Promise<DocumentResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/api/documents`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`
      },
      body: formData
    });

    return response.json();
  }

  async queryRAG(query: string, documentId?: number): Promise<RAGResponse> {
    const response = await fetch(`${this.baseUrl}/api/rag/query`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query,
        document_id: documentId
      })
    });

    return response.json();
  }
}
```

## 📞 Support & Resources

- **GitHub Issues**: [Report API issues](https://github.com/Jackela/ai_enhanced_pdf_scholar/issues)
- **Discussions**: [API questions and feedback](https://github.com/Jackela/ai_enhanced_pdf_scholar/discussions)
- **Email**: Contact support for enterprise inquiries
- **Documentation**: Full API documentation at `/api/docs`

## 🔄 API Versioning

- **Current Version**: v2.1.0
- **Versioning Strategy**: Semantic versioning (SemVer)
- **Backward Compatibility**: Maintained for major versions
- **Breaking Changes**: Communicated via deprecation notices

---

**📊 Last Updated**: 2025-01-19  
**🔖 Version**: 2.1.0  
**👥 Maintained by**: AI Enhanced PDF Scholar Team

*For complete implementation details, see the [OpenAPI specification](./openapi_spec.yaml)*