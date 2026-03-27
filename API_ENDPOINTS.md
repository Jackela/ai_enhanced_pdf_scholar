# AI Enhanced PDF Scholar - API 端点文档

## 概述

AI Enhanced PDF Scholar 提供了完整的 RESTful API 和 WebSocket 接口，支持文档管理、RAG 查询、智能引用分析和系统管理功能。所有 API 端点都基于 FastAPI 构建，提供自动文档生成和类型验证。

**API 基础 URL**: `http://localhost:8000`  
**API 文档**: `http://localhost:8000/docs`  
**ReDoc 文档**: `http://localhost:8000/redoc`

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

**字段说明**:
- `file_type`: 规范化的文件类型/扩展名（例如 `.pdf`），可用于前端过滤和指标统计。

### 错误响应格式

```json
{
  "detail": "错误描述",
  "error_code": "ERROR_CODE",
  "status_code": 400
}
```

---

## API 端点详情

### 1. 系统管理 (`/api/system`) ✅ 已实现

#### 1.1 系统健康检查 ✅

**GET** `/api/system/health`

检查系统各组件的健康状态。

**响应示例**:
```json
{
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

#### 1.2 详细健康检查 ✅

**GET** `/api/system/health/detailed`

获取详细的系统健康信息，包括系统资源、数据库、RAG服务和存储。

#### 1.3 依赖健康检查 ✅

**GET** `/api/system/health/dependencies`

检查外部依赖（Redis、Gemini API、文件系统）的健康状态。

#### 1.4 性能健康检查 ✅

**GET** `/api/system/health/performance`

获取实时性能指标和健康评估。

#### 1.5 系统配置 ✅

**GET** `/api/system/config`

获取系统配置信息和功能可用性。

**响应示例**:
```json
{
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
  "version": "2.1.0"
}
```

#### 1.6 系统信息 ✅

**GET** `/api/system/info`

获取系统运行环境信息。

#### 1.7 API 版本 ✅

**GET** `/api/system/version`

获取 API 版本信息。

**响应示例**:
```json
{
  "version": "2.1.0",
  "name": "AI Enhanced PDF Scholar API"
}
```

#### 1.8 系统初始化 ✅

**POST** `/api/system/initialize`

初始化系统（运行数据库迁移、创建目录等）。

#### 1.9 存储信息 ✅

**GET** `/api/system/storage`

获取存储使用情况。

#### 1.10 维护任务 ✅

**POST** `/api/system/maintenance`

运行系统维护任务（清理临时文件等）。

#### 1.11 密钥管理 ✅

- **GET** `/api/system/health/secrets` - 密钥系统健康状态
- **POST** `/api/system/secrets/validate` - 验证环境密钥
- **POST** `/api/system/secrets/rotate/{secret_name}` - 轮换密钥
- **POST** `/api/system/secrets/backup` - 备份密钥
- **GET** `/api/system/secrets/audit` - 获取审计日志

#### 1.12 实时指标 ✅

- **GET** `/api/system/metrics/current` - 当前指标快照
- **GET** `/api/system/metrics/history/{metric_type}` - 历史指标
- **GET** `/api/system/metrics/system/detailed` - 详细系统指标
- **GET** `/api/system/metrics/database/status` - 数据库指标
- **GET** `/api/system/metrics/websocket/status` - WebSocket指标
- **GET** `/api/system/metrics/memory/leak-detection` - 内存泄漏检测

---

### 2. 文档管理 (`/api/documents`) ✅ 已实现

#### 2.1 文档列表 ✅

**GET** `/api/documents/`

获取文档列表，支持搜索、排序和分页。

**查询参数**:
- `search_query` (string, optional): 搜索关键词
- `sort_by` (string, optional): 排序字段 (created_at|updated_at|last_accessed|title|file_size)
- `sort_order` (string, optional): 排序方向 (asc|desc)
- `page` (int, optional): 页码，默认 1
- `per_page` (int, optional): 每页数量，默认 50，最大 200
- `show_missing` (bool, optional): 是否显示文件缺失的文档，默认 false

#### 2.2 文档详情 ✅

**GET** `/api/documents/{document_id}`

获取特定文档的详细信息。

#### 2.3 文档预览 ✅

**GET** `/api/documents/{document_id}/preview`

返回指定页面的 PNG 预览图。

**查询参数**:
- `page` (int, optional, default=1): 页面编号（从 1 开始）
- `width` (int, optional): 目标宽度（像素），自动在配置范围内裁剪

**响应**:
- `200` `image/png`: 预览图片
- `400`: 参数错误或超出限制
- `404`: 文档或页面不存在
- `415`: 非支持文件类型
- `503`: 预览功能被禁用

#### 2.4 文档缩略图 ✅

**GET** `/api/documents/{document_id}/thumbnail`

返回首页面缩略图（默认 256px），命中缓存时可快速展示。

#### 2.5 文档上传 ✅

**POST** `/api/documents/upload`

上传新的 PDF 文档。

**请求格式**: `multipart/form-data`

**参数**:
- `file` (file, required): PDF 文件
- `title` (string, optional): 文档标题
- `check_duplicates` (bool, optional): 是否检查重复，默认 true
- `auto_build_index` (bool, optional): 是否自动构建向量索引，默认 false

#### 2.6 更新文档 ✅

**PUT** `/api/documents/{document_id}`

更新文档元数据。

#### 2.7 删除文档 ✅

**DELETE** `/api/documents/{document_id}`

删除文档及其相关数据。

#### 2.8 下载文档 ✅

**GET** `/api/documents/{document_id}/download`

下载原始 PDF 文件。

#### 2.9 完整性检查 ✅

**GET** `/api/documents/{document_id}/integrity`

检查文档和索引的完整性。

---

### 3. 库管理 (`/api/library`) ✅ 已实现

#### 3.1 库统计 ✅

**GET** `/api/library/stats`

获取文档库的详细统计信息。

#### 3.2 重复文档检测 ✅

**GET** `/api/library/duplicates`

查找重复文档。

#### 3.3 库清理 ✅

**POST** `/api/library/cleanup`

执行库清理操作（删除孤立索引、修复损坏数据等）。

#### 3.4 库健康检查 ✅

**GET** `/api/library/health`

检查库的健康状态。

#### 3.5 库优化 ✅

**POST** `/api/library/optimize`

优化库存储和性能。

#### 3.6 搜索文档 ✅

**GET** `/api/library/search`

搜索文档内容。

**查询参数**:
- `q` (string, required): 搜索查询
- `limit` (int, optional): 结果限制，默认 50

#### 3.7 最近文档 ✅

**GET** `/api/library/recent`

获取最近访问的文档。

---

### 4. 查询管理 (`/api/queries`) ✅ 已实现

#### 4.1 RAG 查询 ✅

**POST** `/api/queries/`

执行 RAG（检索增强生成）查询。

**请求体示例**:
```json
{
  "query": "这篇论文的主要观点是什么？",
  "document_id": 1
}
```

**注意**: 此功能需要配置 Gemini API 密钥。

#### 4.2 多文档查询 ✅

**POST** `/api/queries/multi-document`

对多个文档执行 RAG 查询。

#### 4.3 查询历史 ✅

**GET** `/api/queries/history`

获取查询历史记录。

#### 4.4 删除查询历史 ✅

**DELETE** `/api/queries/history/{query_id}`

删除特定的查询历史记录。

---

### 5. 索引管理 (`/api/indexes`) ✅ 已实现

#### 5.1 索引列表 ✅

**GET** `/api/indexes/`

获取所有向量索引的列表。

#### 5.2 索引详情 ✅

**GET** `/api/indexes/{document_id}`

获取特定文档的索引详情。

#### 5.3 构建索引 ✅

**POST** `/api/indexes/{document_id}/build`

为文档构建向量索引。

**请求体示例**:
```json
{
  "force_rebuild": false
}
```

#### 5.4 删除索引 ✅

**DELETE** `/api/indexes/{document_id}`

删除文档的向量索引。

#### 5.5 重建索引 ✅

**POST** `/api/indexes/{document_id}/rebuild`

重建文档的向量索引。

#### 5.6 批量索引 ✅

**POST** `/api/indexes/batch`

批量构建多个文档的索引。

---

### 6. 引用管理 (`/api/citations`) ✅ 已实现

#### 6.1 提取文档引用 ✅

**POST** `/api/citations/extract/{document_id}`

从指定文档中提取学术引用。

#### 6.2 获取文档引用列表 ✅

**GET** `/api/citations/document/{document_id}`

获取指定文档的所有引用。

#### 6.3 搜索引用 ✅

**GET** `/api/citations/search`

按多种条件搜索引用。

**查询参数**:
- `author` (str, 可选): 作者名称（模糊匹配）
- `title` (str, 可选): 标题关键词（模糊匹配）
- `year_from` (int, 可选): 起始年份
- `year_to` (int, 可选): 结束年份
- `citation_type` (str, 可选): 引用类型
- `doi` (str, 可选): DOI精确匹配
- `min_confidence` (float, 可选): 最小置信度
- `limit` (int, 可选): 结果数量限制，默认50

#### 6.4 获取引用详情 ✅

**GET** `/api/citations/{citation_id}`

获取特定引用的详细信息。

#### 6.5 更新引用信息 ✅

**PUT** `/api/citations/{citation_id}`

更新引用的字段信息（人工校正）。

#### 6.6 删除引用 ✅

**DELETE** `/api/citations/{citation_id}`

删除指定引用。

#### 6.7 引用统计信息 ✅

**GET** `/api/citations/statistics`

获取引用系统的统计信息。

---

### 7. 引用网络分析 (`/api/citations/network`) ✅ 已实现

#### 7.1 构建引用网络 ✅

**GET** `/api/citations/network/{document_id}`

构建以指定文档为中心的引用网络。

#### 7.2 创建引用关系 ✅

**POST** `/api/citations/network/relations`

手动创建文档间的引用关系。

#### 7.3 获取引用关系 ✅

**GET** `/api/citations/network/relations`

查询引用关系。

---

### 8. 多文档管理 (`/api/multi-document`) ✅ 已实现

#### 8.1 创建集合 ✅

**POST** `/api/multi-document/collections`

创建多文档集合。

#### 8.2 获取集合列表 ✅

**GET** `/api/multi-document/collections`

获取所有集合列表。

#### 8.3 获取集合详情 ✅

**GET** `/api/multi-document/collections/{collection_id}`

获取特定集合的详细信息。

#### 8.4 更新集合 ✅

**PUT** `/api/multi-document/collections/{collection_id}`

更新集合信息。

#### 8.5 删除集合 ✅

**DELETE** `/api/multi-document/collections/{collection_id}`

删除集合。

#### 8.6 添加文档到集合 ✅

**POST** `/api/multi-document/collections/{collection_id}/documents`

添加文档到集合。

#### 8.7 从集合移除文档 ✅

**DELETE** `/api/multi-document/collections/{collection_id}/documents/{document_id}`

从集合中移除文档。

#### 8.8 集合查询 ✅

**POST** `/api/multi-document/collections/{collection_id}/query`

对集合执行查询。

---

### 9. 设置管理 (`/api/settings`) ✅ 已实现

#### 9.1 获取设置 ✅

**GET** `/api/settings`

获取应用设置。

#### 9.2 保存设置 ✅

**POST** `/api/settings`

保存应用设置。

#### 9.3 测试 API 密钥 ✅

**POST** `/api/settings/test-api-key`

测试 API 密钥的有效性。

#### 9.4 获取系统状态 ✅

**GET** `/api/settings/status`

获取系统状态概览。

---

### 10. 缓存管理 (`/api/cache`) ✅ 已实现

#### 10.1 缓存健康检查 ✅

**GET** `/api/cache/health`

获取缓存系统健康状态。

#### 10.2 缓存统计 ✅

**GET** `/api/cache/statistics`

获取缓存使用统计。

#### 10.3 缓存配置 ✅

**GET** `/api/cache/configuration`

获取缓存配置。

#### 10.4 缓存失效 ✅

**POST** `/api/cache/invalidate`

使指定缓存项失效。

#### 10.5 缓存预热 ✅

**POST** `/api/cache/warm`

预热缓存。

#### 10.6 清空缓存 ✅

**DELETE** `/api/cache/clear`

清空所有缓存。

---

### 11. 性能监控 (`/api/monitoring`) ✅ 已实现

#### 11.1 性能概览 ✅

**GET** `/api/monitoring/overview`

获取性能概览。

#### 11.2 健康状态 ✅

**GET** `/api/monitoring/health`

获取监控服务健康状态。

#### 11.3 综合报告 ✅

**GET** `/api/monitoring/report/comprehensive`

获取综合性能报告。

#### 11.4 性能趋势 ✅

**GET** `/api/monitoring/trends`

获取性能趋势数据。

#### 11.5 告警管理 ✅

- **GET** `/api/monitoring/alerts` - 获取当前告警
- **GET** `/api/monitoring/alerts/history` - 获取告警历史
- **POST** `/api/monitoring/alerts/rules` - 创建告警规则

---

### 12. 速率限制管理 (`/api/rate-limit`) ✅ 已实现

#### 12.1 速率限制状态 ✅

**GET** `/api/rate-limit/status`

获取速率限制状态。

#### 12.2 速率限制指标 ✅

**GET** `/api/rate-limit/metrics`

获取速率限制指标。

#### 12.3 IP 分析 ✅

**GET** `/api/rate-limit/ip/{client_ip}`

分析特定 IP 的请求模式。

#### 12.4 可疑 IP ✅

**GET** `/api/rate-limit/suspicious-ips`

获取可疑 IP 列表。

---

### 13. RBAC 管理 (`/api/rbac`) ✅ 已实现

#### 13.1 角色管理 ✅

- **GET** `/api/rbac/roles` - 获取角色列表
- **POST** `/api/rbac/roles` - 创建角色
- **DELETE** `/api/rbac/roles/{role_name}` - 删除角色

#### 13.2 权限分配 ✅

- **POST** `/api/rbac/assign-role` - 分配角色
- **POST** `/api/rbac/revoke-role` - 撤销角色
- **POST** `/api/rbac/grant-permission` - 授予权限

#### 13.3 权限查询 ✅

- **GET** `/api/rbac/permissions` - 获取权限列表
- **GET** `/api/rbac/users/{user_id}/permissions` - 获取用户权限
- **GET** `/api/rbac/my-permissions` - 获取当前用户权限

---

### 14. 异步 RAG (`/api/async-rag`) ✅ 已实现

#### 14.1 异步查询 ✅

**POST** `/api/async-rag/query/async`

提交异步 RAG 查询任务。

#### 14.2 查询任务状态 ✅

**GET** `/api/async-rag/query/async/{task_id}`

获取异步查询任务状态。

#### 14.3 取消查询任务 ✅

**DELETE** `/api/async-rag/query/async/{task_id}`

取消异步查询任务。

#### 14.4 混合查询 ✅

**POST** `/api/async-rag/query/hybrid`

执行混合查询（同步 + 异步）。

---

## WebSocket 接口 ✅ 已实现

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
2. **rag_progress** - 查询进度更新
3. **rag_response** - 查询结果
4. **rag_error** - 查询错误
5. **citation_extraction_progress** - 引用提取进度
6. **citation_extraction_complete** - 引用提取完成
7. **citation_network_updated** - 引用网络更新通知

---

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

---

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
response = requests.post(f"{BASE_URL}/api/queries/", json=query_data)
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

---

## 实现状态汇总

| 模块 | 状态 | 端点数量 | 说明 |
|------|------|----------|------|
| 系统管理 | ✅ 已实现 | 20+ | 健康检查、配置、指标、密钥管理 |
| 文档管理 | ✅ 已实现 | 9 | CRUD、预览、下载、完整性检查 |
| 库管理 | ✅ 已实现 | 7 | 统计、重复检测、清理、搜索 |
| 查询管理 | ✅ 已实现 | 4 | RAG查询、历史记录 |
| 索引管理 | ✅ 已实现 | 6 | 索引构建、状态、重建 |
| 引用管理 | ✅ 已实现 | 7 | 提取、搜索、更新、统计 |
| 引用网络 | ✅ 已实现 | 3 | 网络构建、关系管理 |
| 多文档 | ✅ 已实现 | 9 | 集合管理、批量查询 |
| 设置管理 | ✅ 已实现 | 4 | 配置、API密钥测试 |
| 缓存管理 | ✅ 已实现 | 9 | 健康、统计、预热、清理 |
| 性能监控 | ✅ 已实现 | 15+ | 概览、报告、告警 |
| 速率限制 | ✅ 已实现 | 9 | 状态、指标、IP分析 |
| RBAC | ✅ 已实现 | 10 | 角色、权限、审计 |
| 异步RAG | ✅ 已实现 | 4 | 异步任务、混合查询 |
| WebSocket | ✅ 已实现 | 1 | 实时通信 |

**总计**: 80+ 端点已实现

---

## 开发注意事项

1. **API 版本控制**: 当前 API 版本为 2.1.0
2. **并发限制**: 系统设计为单用户使用，高并发下可能需要额外优化
3. **文件存储**: 所有文件存储在用户本地 `~/.ai_pdf_scholar/` 目录
4. **日志记录**: 详细的 API 调用日志记录在应用日志中
5. **性能**: 大文件上传和 RAG 查询可能需要较长时间

---

## 更新历史

- **v2.1.0** (2026-03-27): 文档同步更新，添加性能监控、RBAC、异步RAG端点
- **v2.0.0** (2025-07-20): 完全基于 Web 的架构，移除所有 PyQt6 依赖
- **v1.x**: PyQt桌面架构（已废弃）

---

**文档最后更新**: 2026-03-27  
**API 版本**: 2.1.0  
**状态**: ✅ 所有核心功能已实现
