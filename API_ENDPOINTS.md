# AI Enhanced PDF Scholar - API 端点文档

## 概述

AI Enhanced PDF Scholar 提供了完整的 RESTful API 和 WebSocket 接口，支持文档管理、RAG 查询和系统管理功能。所有 API 端点都基于 FastAPI 构建，提供自动文档生成和类型验证。

**API 基础 URL**: `http://localhost:8000`
**API 文档**: `http://localhost:8000/api/docs`
**ReDoc 文档**: `http://localhost:8000/api/redoc`

### 文件管理策略

系统采用**集中托管存储**策略：
- **上传文件**：临时存储在 `~/.ai_pdf_scholar/uploads/`
- **永久存储**：复制到 `~/.ai_pdf_scholar/documents/` 并以文件hash命名
- **数据安全**：原文件变化不影响系统，所有文档数据完全受系统管理
- **完整性保证**：每个文档的 `is_file_available` 字段表示托管文件是否存在

## 认证

当前版本为单用户本地应用，无需认证。未来版本可能会添加 API 密钥认证。

## 响应格式

### 标准响应格式

所有 API 响应都遵循统一的格式：

```json
{
  "success": true,
  "message": "操作成功",
  "data": {
    // 实际数据内容
  }
}
```

### 错误响应格式

```json
{
  "detail": "错误描述",
  "error_code": "ERROR_CODE",
  "status_code": 400
}
```

## API 端点详情

### 1. 系统管理 (`/api/system`)

#### 1.1 系统健康检查

**GET** `/api/system/health`

检查系统各组件的健康状态。

**响应示例**:
```json
{
  "success": true,
  "status": "degraded",
  "database_connected": true,
  "rag_service_available": false,
  "api_key_configured": false,
  "storage_health": "healthy",
  "uptime_seconds": 123.45
}
```

**状态说明**:
- `healthy`: 所有组件正常
- `degraded`: 部分组件不可用（如未配置 API 密钥）
- `unhealthy`: 关键组件故障

#### 1.2 系统配置

**GET** `/api/system/config`

获取系统配置信息和功能可用性。

**响应示例**:
```json
{
  "success": true,
  "features": {
    "document_upload": true,
    "rag_queries": false,
    "vector_indexing": false,
    "cache_system": true,
    "websocket_support": true,
    "duplicate_detection": true,
    "library_management": true
  },
  "limits": {
    "max_file_size_mb": 100,
    "max_query_length": 2000,
    "allowed_file_types": [".pdf"],
    "max_documents": 10000,
    "max_concurrent_queries": 10
  },
  "version": "2.0.0"
}
```

#### 1.3 系统信息

**GET** `/api/system/info`

获取系统运行环境信息。

#### 1.4 API 版本

**GET** `/api/system/version`

获取 API 版本信息。

**响应示例**:
```json
{
  "version": "2.0.0",
  "name": "AI Enhanced PDF Scholar API"
}
```

#### 1.5 系统初始化

**POST** `/api/system/initialize`

初始化系统（运行数据库迁移、创建目录等）。

#### 1.6 存储信息

**GET** `/api/system/storage`

获取存储使用情况。

#### 1.7 维护任务

**POST** `/api/system/maintenance`

运行系统维护任务（清理临时文件等）。

### 2. 文档管理 (`/api/documents`)

#### 2.1 文档列表

**GET** `/api/documents/`

获取文档列表，支持搜索、排序和分页。

**查询参数**:
- `search_query` (string, optional): 搜索关键词
- `sort_by` (string, optional): 排序字段 (created_at|updated_at|last_accessed|title|file_size)
- `sort_order` (string, optional): 排序方向 (asc|desc)
- `page` (int, optional): 页码，默认 1
- `per_page` (int, optional): 每页数量，默认 50，最大 200
- `show_missing` (bool, optional): 是否显示文件缺失的文档，默认 false

**响应示例**:
```json
{
  "success": true,
  "documents": [
    {
      "id": 1,
      "title": "研究论文.pdf",
      "file_path": "/path/to/file.pdf",
      "file_size": 1024000,
      "page_count": 20,
      "created_at": "2023-01-01T00:00:00",
      "updated_at": "2023-01-01T00:00:00",
      "last_accessed": "2023-01-01T00:00:00",
      "file_hash": "abcd1234...",
      "content_hash": "efgh5678...",
      "metadata": {},
      "is_file_available": true
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 50
}
```

#### 2.2 文档详情

**GET** `/api/documents/{document_id}`

获取特定文档的详细信息。

#### 2.3 文档上传

**POST** `/api/documents/upload`

上传新的 PDF 文档。

**请求格式**: `multipart/form-data`

**参数**:
- `file` (file, required): PDF 文件
- `title` (string, optional): 文档标题
- `check_duplicates` (bool, optional): 是否检查重复，默认 true
- `auto_build_index` (bool, optional): 是否自动构建向量索引，默认 false

**响应示例**:
```json
{
  "success": true,
  "document": {
    "id": 1,
    "title": "AI辅助项目完成模式",
    "file_path": "C:\\Users\\user\\.ai_pdf_scholar\\documents\\fe4086dc.pdf",
    "file_size": 151676,
    "page_count": 3,
    "file_hash": "fe4086dc365fc6a2",
    "created_at": "2025-07-14T06:14:12.019558",
    "updated_at": "2025-07-14T06:14:12.019558",
    "is_file_available": true,
    "metadata": {
      "content_hash": "9a2348429051aec0",
      "import_timestamp": "2025-07-14T06:14:12.055233",
      "original_path": "C:\\path\\to\\original\\file.pdf",
      "managed_path": "C:\\Users\\user\\.ai_pdf_scholar\\documents\\fe4086dc.pdf",
      "file_valid": true
    }
  }
}
```

**错误代码**:
- `400`: 无效文件格式（仅支持 PDF）
- `409`: 文档重复
- `413`: 文件过大

#### 2.4 更新文档

**PUT** `/api/documents/{document_id}`

更新文档元数据。

**请求体示例**:
```json
{
  "title": "新标题",
  "metadata": {
    "author": "作者名",
    "tags": ["tag1", "tag2"]
  }
}
```

#### 2.5 删除文档

**DELETE** `/api/documents/{document_id}`

删除文档及其相关数据。

#### 2.6 下载文档

**GET** `/api/documents/{document_id}/download`

下载原始 PDF 文件。

#### 2.7 完整性检查

**GET** `/api/documents/{document_id}/integrity`

检查文档和索引的完整性。

**响应示例**:
```json
{
  "success": true,
  "document_id": 1,
  "exists": true,
  "file_exists": true,
  "file_accessible": true,
  "hash_matches": true,
  "vector_index_exists": false,
  "vector_index_valid": false,
  "is_healthy": true,
  "errors": [],
  "warnings": ["Vector index not found"]
}
```

### 3. 库管理 (`/api/library`)

#### 3.1 库统计

**GET** `/api/library/stats`

获取文档库的详细统计信息。

**响应示例**:
```json
{
  "success": true,
  "documents": {
    "total_documents": 10,
    "size_stats": {
      "count": 10,
      "avg_size": 2048000,
      "min_size": 512000,
      "max_size": 5120000,
      "total_size": 20480000
    },
    "page_stats": {
      "count": 10,
      "avg_pages": 15.5,
      "min_pages": 5,
      "max_pages": 50
    },
    "recent_activity": {
      "recent_count": 3
    }
  },
  "vector_indexes": {
    "total_indexes": 8,
    "chunk_stats": {
      "count": 8,
      "avg_chunks": 25.0,
      "total_chunks": 200
    },
    "coverage": {
      "documents_with_index": 8,
      "total_documents": 10
    },
    "orphaned_count": 0,
    "invalid_count": 0
  },
  "health": {
    "orphaned_indexes": 0,
    "invalid_indexes": 0,
    "index_coverage": 80
  }
}
```

#### 3.2 重复文档检测

**GET** `/api/library/duplicates`

查找重复文档。

#### 3.3 库清理

**POST** `/api/library/cleanup`

执行库清理操作（删除孤立索引、修复损坏数据等）。

#### 3.4 库健康检查

**GET** `/api/library/health`

检查库的健康状态。

#### 3.5 库优化

**POST** `/api/library/optimize`

优化库存储和性能。

#### 3.6 搜索文档

**GET** `/api/library/search`

搜索文档内容。

**查询参数**:
- `q` (string, required): 搜索查询
- `limit` (int, optional): 结果限制，默认 50

#### 3.7 最近文档

**GET** `/api/library/recent`

获取最近访问的文档。

**查询参数**:
- `limit` (int, optional): 结果限制，默认 20

### 4. RAG 查询 (`/api/rag`)

#### 4.1 RAG 查询

**POST** `/api/rag/query`

执行 RAG（检索增强生成）查询。

**请求体示例**:
```json
{
  "query": "这篇论文的主要观点是什么？",
  "document_id": 1
}
```

**响应示例**:
```json
{
  "success": true,
  "answer": "基于文档内容的详细回答...",
  "sources": [
    {
      "chunk_id": "chunk_1",
      "content": "相关文档片段...",
      "score": 0.85
    }
  ],
  "query": "这篇论文的主要观点是什么？",
  "document_id": 1
}
```

**注意**: 此功能需要配置 Gemini API 密钥。

#### 4.2 构建向量索引

**POST** `/api/rag/build-index`

为文档构建向量索引。

**请求体示例**:
```json
{
  "document_id": 1,
  "force_rebuild": false
}
```

#### 4.3 索引状态

**GET** `/api/rag/status/{document_id}`

检查文档的 RAG 索引状态。

### 5. 设置管理 (`/api`)

#### 5.1 获取设置

**GET** `/api/settings`

获取应用设置。

**响应示例**:
```json
{
  "success": true,
  "rag_enabled": false,
  "gemini_api_key_configured": false,
  "auto_build_index": false,
  "cache_enabled": true,
  "ui_theme": "light"
}
```

#### 5.2 保存设置

**POST** `/api/settings`

保存应用设置。

**请求体示例**:
```json
{
  "gemini_api_key": "your-api-key-here",
  "rag_enabled": true,
  "auto_build_index": true,
  "ui_theme": "dark"
}
```

## WebSocket 接口

### 连接端点

**WebSocket** `/ws/{client_id}`

建立 WebSocket 连接进行实时通信。

### 消息类型

#### 发送到服务器

1. **ping** - 心跳检测
```json
{
  "type": "ping"
}
```

2. **rag_query** - RAG 查询请求
```json
{
  "type": "rag_query",
  "query": "问题内容",
  "document_id": 1
}
```

#### 从服务器接收

1. **pong** - 心跳响应
```json
{
  "type": "pong"
}
```

2. **rag_progress** - 查询进度更新
```json
{
  "type": "rag_progress",
  "message": "正在分析文档..."
}
```

3. **rag_response** - 查询结果
```json
{
  "type": "rag_response",
  "query": "问题内容",
  "response": "回答内容",
  "document_id": 1
}
```

4. **rag_error** - 查询错误
```json
{
  "type": "rag_error",
  "error": "错误信息"
}
```

## 错误处理

### HTTP 状态码

- `200 OK`: 成功
- `400 Bad Request`: 请求参数错误
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突（如重复文档）
- `413 Payload Too Large`: 文件过大
- `500 Internal Server Error`: 服务器内部错误
- `503 Service Unavailable`: 服务不可用

### 常见错误

1. **未配置 API 密钥**
```json
{
  "detail": "RAG service is not available. Please configure Gemini API key.",
  "status_code": 503
}
```

2. **文档不存在**
```json
{
  "detail": "Document 123 not found",
  "status_code": 404
}
```

3. **文件格式不支持**
```json
{
  "detail": "Only PDF files are allowed",
  "status_code": 400
}
```

## 使用示例

### Python 客户端示例

```python
import requests
import json

# 基础 URL
BASE_URL = "http://localhost:8000"

# 1. 检查系统健康状态
response = requests.get(f"{BASE_URL}/api/system/health")
health = response.json()
print(f"System status: {health['status']}")

# 2. 获取文档列表
response = requests.get(f"{BASE_URL}/api/documents/")
documents = response.json()
print(f"Total documents: {documents['total']}")

# 3. 上传文档
with open("document.pdf", "rb") as f:
    files = {"file": f}
    data = {"title": "My Document"}
    response = requests.post(f"{BASE_URL}/api/documents/upload", files=files, data=data)
    result = response.json()
    print(f"Upload result: {result['success']}")

# 4. RAG 查询
query_data = {
    "query": "What is this document about?",
    "document_id": 1
}
response = requests.post(f"{BASE_URL}/api/rag/query", json=query_data)
if response.status_code == 200:
    result = response.json()
    print(f"Answer: {result['answer']}")
```

### JavaScript 客户端示例

```javascript
const BASE_URL = 'http://localhost:8000';

// 1. 获取系统配置
async function getSystemConfig() {
    const response = await fetch(`${BASE_URL}/api/system/config`);
    const config = await response.json();
    return config;
}

// 2. 上传文档
async function uploadDocument(file, title) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    
    const response = await fetch(`${BASE_URL}/api/documents/upload`, {
        method: 'POST',
        body: formData
    });
    
    return await response.json();
}

// 3. WebSocket 连接
function connectWebSocket(clientId) {
    const ws = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        console.log('Received:', message);
    };
    
    // 发送 RAG 查询
    function sendRAGQuery(query, documentId) {
        ws.send(JSON.stringify({
            type: 'rag_query',
            query: query,
            document_id: documentId
        }));
    }
    
    return { ws, sendRAGQuery };
}
```

## 开发注意事项

1. **API 版本控制**: 当前 API 版本为 2.0.0，未来版本可能会有 breaking changes
2. **并发限制**: 系统设计为单用户使用，高并发下可能需要额外优化
3. **文件存储**: 所有文件存储在用户本地 `~/.ai_pdf_scholar/` 目录
4. **日志记录**: 详细的 API 调用日志记录在应用日志中
5. **性能**: 大文件上传和 RAG 查询可能需要较长时间

## 更新历史

- **v2.0.0**: 完全基于 Web 的架构，移除所有 PyQt6 依赖
- **v1.x**: 混合桌面/Web 架构（已废弃）

---

**文档最后更新**: 2025-07-13  
**API 版本**: 2.0.0  
**状态**: ✅ 已验证并与实际实现保持一致