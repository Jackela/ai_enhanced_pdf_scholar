# Claude Code 开发指令与记忆

## 核心开发原则

### 📋 文档同步开发原则
**CRITICAL**: 在编写或修改代码时，必须同步更新或创建相应的文档。代码与文档必须保持100%一致性。

### 🔄 开发-文档循环流程
1. **代码修改时**：立即评估是否需要更新现有文档
2. **新功能开发时**：同时创建或扩展相关文档
3. **API 变更时**：必须更新 `API_ENDPOINTS.md` 和 `PROJECT_DOCS.md`
4. **架构调整时**：更新 `PROJECT_DOCS.md` 中的架构图和说明

## 📚 文档体系结构

### 主要文档文件
- **`PROJECT_DOCS.md`**: 项目主文档，包含架构、组件、流程图
- **`API_ENDPOINTS.md`**: 详细的 API 端点文档，包含示例和错误处理
- **`DEVELOPMENT_PLAN.md`**: 开发计划和功能路线图
- **`TECHNICAL_DESIGN.md`**: 技术设计决策和架构细节
- **`CLAUDE.md`** (本文件): Claude Code 开发指令和记忆

### 文档更新触发条件

#### 1. 代码结构变更时
- 新增/删除 Python 模块 → 更新 `PROJECT_DOCS.md` 项目结构图
- 修改类/函数接口 → 更新核心组件文档
- 变更数据库模式 → 更新数据库设计图

#### 2. API 变更时
- 新增 API 端点 → 在 `API_ENDPOINTS.md` 中添加详细说明
- 修改 API 参数/响应 → 更新对应端点的文档和示例
- API 状态码变更 → 更新错误处理部分

#### 3. 架构调整时
- 新增服务层 → 更新架构图和交互流程
- 修改依赖关系 → 更新组件关系图
- 变更数据流 → 更新序列图和流程图

#### 4. 配置变更时
- 新增配置项 → 更新配置说明文档
- 环境要求变更 → 更新部署和运行文档

## 🎯 具体执行指令

### 每次代码修改后执行检查列表
```
□ 代码修改是否影响 API 接口？
  ↳ 是 → 更新 API_ENDPOINTS.md 相关部分
□ 代码修改是否影响项目结构？
  ↳ 是 → 更新 PROJECT_DOCS.md 项目结构图
□ 代码修改是否引入新的组件或服务？
  ↳ 是 → 在 PROJECT_DOCS.md 中添加组件说明
□ 代码修改是否改变数据流或交互逻辑？
  ↳ 是 → 更新序列图和流程图
□ 是否需要创建新的文档文件？
  ↳ 是 → 创建并链接到主文档
```

### 新功能开发流程
```
1. 分析功能需求
2. 设计技术方案
3. 创建/更新设计文档
4. 编写代码
5. 同时更新 API 文档（如适用）
6. 更新项目文档中的相关部分
7. 验证文档与代码的一致性
```

## 📝 文档写作标准

### Mermaid 图表要求
- 项目结构使用 `graph TD` (top-down)
- 序列图使用 `sequenceDiagram`
- 类关系使用 `classDiagram`
- 数据库关系使用 `erDiagram`
- 流程图使用 `flowchart TD`

### API 文档要求
- 每个端点必须包含：请求格式、响应示例、错误代码、使用说明
- 必须提供实际可运行的代码示例
- 错误处理必须详细说明状态码和错误信息
- 所有示例必须与实际 API 行为一致

### 代码文档要求
- 核心类和函数必须包含详细的 docstring
- 复杂业务逻辑必须有中文注释说明
- 接口变更必须在文档中标注版本和变更日期

## 🚨 强制执行规则

### 代码提交前检查
1. **API 一致性**：手动测试 API 端点，确保文档示例可用
2. **架构一致性**：验证架构图反映实际代码结构
3. **文档完整性**：确保新功能有对应文档
4. **示例有效性**：确保所有代码示例可执行
5. **测试性能**：运行性能基准测试验证优化效果
6. **文档谦逊性**：避免夸大数据，保持中英文双版本

### 文档质量标准
- **准确性**：文档内容必须与代码实现100%一致
- **完整性**：主要功能和 API 必须有完整文档
- **时效性**：文档更新日期必须及时更新
- **可用性**：示例代码必须可直接运行

## 🔍 验证机制

### 自动化检查
```bash
# API 端点验证脚本
python test_complete_workflow.py

# 文档链接检查
# 验证所有内部链接的有效性

# 代码示例验证
# 确保文档中的代码示例语法正确
```

### 手动验证
- 每个 API 端点至少手动测试一次
- 每个架构图与实际代码结构对比验证
- 每个序列图与实际调用流程对比验证

## 💡 开发记忆要点

### 项目特征记忆
- **纯 Web 架构**：已完全移除 PyQt6 依赖
- **API 优先**：所有功能通过 RESTful API 提供
- **文档驱动**：架构设计和 API 设计都有详细文档
- **测试完备**：每个主要功能都有对应测试

### 技术栈记忆
- **后端**：FastAPI + SQLite + LlamaIndex
- **前端**：React + TypeScript + Tailwind CSS
- **API**：RESTful + WebSocket
- **数据库**：SQLite 3 with Repository Pattern
- **AI**：Google Gemini API for RAG

### 开发风格记忆
- **SOLID 原则**：严格遵循面向对象设计原则
- **依赖注入**：使用 FastAPI 的依赖注入系统
- **错误处理**：完整的异常处理和日志记录
- **类型安全**：完整的 Python 类型提示
- **性能优先**：优化测试执行和CI/CD效率
- **测试驱动**：共享fixtures和并行执行

## 🎯 特殊注意事项

### API 开发注意
- 新增端点必须遵循现有的命名约定
- 响应格式必须一致（success, message, data 结构）
- 错误处理必须使用标准 HTTP 状态码
- 所有端点必须有对应的 Pydantic 模型

### 文档维护注意
- Mermaid 图表必须在 GitHub 和本地都能正确渲染
- 文档中的文件路径必须使用相对路径
- 代码示例必须使用正确的语法高亮
- 更新日期格式统一使用 YYYY-MM-DD
- **保持谦逊**：避免夸大性能数据和指标
- **双语文档**：重要文档提供中英文版本

### 代码风格注意
- 中文注释用于业务逻辑说明
- 英文注释用于技术实现说明
- 类和函数名使用英文
- 变量名使用英文且具有描述性

---

**记忆创建日期**: 2025-07-13
**最后更新**: 2025-01-12
**适用版本**: AI Enhanced PDF Scholar v2.1.0+
**更新要求**: 每次重大架构变更时更新此文档

## ⚡ 最新开发实践

### 📦 DocumentLibraryService 依赖注入重构 (2025-01-12)

#### 🎯 重构目标
将 DocumentLibraryService 从静态依赖迁移到依赖注入模式，提升可测试性和解耦度。

#### 🔄 架构变更

**修改前（Legacy）:**
```python
class DocumentLibraryService:
    def __init__(self, documents_dir: str | None = None):
        self.document_repo = DocumentRepository(db)  # Hard-coded dependency
        # Static method call
        content_hash = ContentHashService.calculate_content_hash(content)
```

**修改后（DI Pattern）:**
```python
class DocumentLibraryService:
    def __init__(
        self,
        document_repository: IDocumentRepository,  # Injected interface
        hash_service: IContentHashService,          # Injected interface
        documents_dir: str | None = None,
    ):
        self.document_repo = document_repository
        self.hash_service = hash_service

    # Instance method call
    content_hash = self.hash_service.calculate_content_hash(content)
```

#### 📋 修改文件清单

**核心服务层（1个文件）:**
1. `src/services/document_library_service.py`
   - 构造函数：新增2个DI参数
   - 4处方法调用：从静态调用改为实例方法

**服务集成层（2个文件）:**
2. `src/services/document_service.py` - 使用DI实例化
3. `src/controllers/library_controller.py` - Fallback实例化

**测试层（5个文件）:**
4. `tests/services/test_document_library_service.py` - 主测试文件
5. `tests/services/test_document_library_service_enhancements.py` - 增强测试
6. `tests/integration/test_real_document_library.py` - 集成测试
7. `tests/integration/test_real_pdf_processing.py` - PDF处理测试
8. `tests/integration/test_mock_replacement_demo.py` - Mock演示

**总计：8个文件更新**

#### ✅ 验证结果

**测试通过率:**
- 单元测试：13 passed, 1 failed (无关fixture issue), 1 error (无关文件问题)
- 集成测试：所有DI相关测试通过

**生产环境验证:**
```bash
# API 端点测试
POST /api/documents
Response: 201 Created
{
  "success": true,
  "data": {
    "id": 1,
    "file_hash": "fb4489b5938e9206",
    "content_hash": "4837479125758add"  # ✅ ContentHashService via DI working
  }
}
```

#### 🛠️ 后端启动问题修复

**问题诊断:**
- `.trunk/tmp` 目录存在循环符号链接
- Uvicorn WatchFiles 检测到文件系统循环导致崩溃
- 用户症状：前端 `ERR_CONNECTION_REFUSED`

**解决方案:**
```bash
rm -rf .trunk/tmp  # 删除循环符号链接目录
```

**结果:** 后端成功启动，监听端口 8000

#### 📝 DI模式最佳实践

**依赖注入优势:**
- ✅ 接口隔离：依赖抽象接口而非具体实现
- ✅ 可测试性：轻松注入 Mock 对象
- ✅ 单一职责：服务专注业务逻辑，不负责依赖创建
- ✅ 解耦合：降低模块间的耦合度

**实例化模式:**
```python
# 方式1: FastAPI Dependency Injection (推荐)
def get_document_library_service(
    doc_repo: IDocumentRepository = Depends(get_document_repository),
    hash_service: IContentHashService = Depends(get_content_hash_service),
) -> IDocumentLibraryService:
    return DocumentLibraryService(
        document_repository=doc_repo,
        hash_service=hash_service
    )

# 方式2: 直接实例化 (Fallback)
doc_repo = DocumentRepository(db)
hash_service = ContentHashService()
service = DocumentLibraryService(
    document_repository=doc_repo,
    hash_service=hash_service
)
```

#### 🎓 经验总结

**重构原则:**
1. **接口优先**：定义清晰的接口（IDocumentRepository, IContentHashService）
2. **向后兼容**：保持公共API不变，仅修改内部实现
3. **测试先行**：确保所有测试用例更新并通过
4. **生产验证**：实际API调用验证功能正常

**避免的陷阱:**
- ❌ 不要在服务内部直接创建依赖对象
- ❌ 不要使用全局单例（除非通过DI容器管理）
- ❌ 不要静态方法调用外部服务
- ✅ 始终通过构造函数注入依赖

---

## 🔧 历史开发实践

### 🎯 引用提取系统架构完成状态 (2025-01-19)
- **数据层**：CitationModel + CitationRelationModel (24个测试通过)
- **仓库层**：Repository Pattern + SOLID原则 (21个测试通过)
- **服务层**：业务逻辑 + 智能解析 (18个测试通过)
- **总计**：63个单元测试，100%通过率

### 🎯 引用提取系统架构完成状态
- **数据层**：CitationModel + CitationRelationModel (24个测试通过)
- **仓库层**：Repository Pattern + SOLID原则 (21个测试通过)
- **服务层**：业务逻辑 + 智能解析 (18个测试通过)
- **总计**：63个单元测试，100%通过率

### 🏗️ 模块化架构设计原则
- **接口隔离**：每个模块使用抽象接口，降低耦合度
- **依赖注入**：构造函数注入，便于独立LLM模块开发
- **单一职责**：每个类/服务专注单一功能领域
- **可扩展性**：使用Plugin Pattern支持新解析算法

### 📋 LLM模块开发指南
```python
# 模块边界清晰，便于LLM独立开发
class CitationParsingService:  # 可独立优化
class CitationService:         # 业务逻辑层
class ICitationRepository:     # 接口定义层
```

### 性能优化开发实践
- **测试优化**：使用 `tests/conftest.py` 共享fixtures减少设置开销
- **并行执行**：pytest 配置 `-n auto --dist=loadfile` 实现多核加速
- **CI优化**：GitHub Actions 流水线超时从30分钟优化到15分钟
- **性能监控**：使用 `scripts/benchmark_tests.py` 自动验证性能指标
- **智能清理**：表级清理替代完整数据库重建

### 集成测试策略
- **分层测试**：单元 → 集成 → 端到端
- **Mock策略**：外部依赖使用Mock，内部组件使用真实实现
- **数据驱动**：使用真实PDF样本进行端到端验证
- **性能基准**：集成测试包含性能指标验证

### 文档更新标准
- **避免具体数字**：除非有明确测试结果支持
- **保持谦逊语调**：使用"改进"、"优化"而非"大幅提升"
- **双语支持**：重要文档同时提供中英文版本
- **性能基准**：使用相对改进而非绝对数字

## 🔧 CI/CD环境差异解决方案 (2025-01-17)

### ✅ 已解决：TypeScript模块路径解析的PWA插件兼容性问题

#### 🎯 问题根源：PWA插件绕过Vite别名解析器

**症状表现**：
```bash
# 本地环境 (Windows + Node.js v22)
✅ npm run build  # 成功
✅ export CI=true && npx vite build  # 成功

# CI环境 (Ubuntu + Node.js v20) - 修复前
❌ npx vite build --mode production  # 失败
Error: Could not load /src/lib/utils (missing .ts extension)

# CI环境 - 修复后
✅ npx vite build --mode production  # 成功
✅ PWA manifest.webmanifest + sw.js 正常生成
```

#### 🔍 根本原因分析

| 差异维度 | 本地环境 | CI环境 | 影响 |
|---------|---------|--------|------|
| **操作系统** | Windows (NTFS) | Ubuntu (ext4) | 文件系统大小写敏感性 |
| **Node.js版本** | v22.17.0 | v20 | 模块解析算法差异 |
| **工作目录** | 相对路径 | `/home/runner/work/...` | 绝对路径解析基准不同 |
| **vite-plugin-pwa** | 本地缓存辅助 | 干净环境构建 | PWA插件绕过别名解析器 |

#### 🛠️ 解决方案演进历程

**第一阶段：对象别名配置 (失败)**
```typescript
// ❌ 被PWA插件绕过
alias: {
  '@/lib/utils': resolve(__dirname, './src/lib/utils.ts')
}
```

**第二阶段：自定义Rollup插件 (部分成功)**
```typescript
// ⚠️ 仅在主构建阶段生效，PWA构建阶段失效
plugins: [{
  name: 'ci-path-resolver',
  resolveId(id) { /* ... */ }
}]
```

**最终解决方案：PWA插件兼容的双重解析器 (成功)**
```typescript
// ✅ 核心解决方案：数组别名 + 自定义Rollup插件
resolve: {
  alias: [
    // CRITICAL: 具体文件映射优先，PWA插件兼容
    { find: '@/lib/utils', replacement: resolve(__dirname, './src/lib/utils.ts') },
    { find: '@/lib/api', replacement: resolve(__dirname, './src/lib/api.ts') },

    // PATTERN: 目录正则匹配
    { find: /^@\/components\/(.*)/, replacement: resolve(__dirname, './src/components/$1') },

    // BASE: 根目录映射 (必须最后)
    { find: '@', replacement: resolve(__dirname, './src') }
  ]
},

rollupOptions: {
  plugins: [{
    name: 'ci-path-resolver',
    order: 'pre', // 关键：在PWA插件之前运行
    resolveId(id) {
      if (id === '@/lib/utils') return resolve(__dirname, './src/lib/utils.ts')
      if (id === '@/lib/api') return resolve(__dirname, './src/lib/api.ts')
      return null
    }
  }]
}
```

#### 🧪 验证策略

**本地CI模拟验证**：
```bash
# 1. 标准构建测试
npm run build

# 2. CI环境模拟
export CI=true && npx vite build --mode production

# 3. PWA插件兼容性
# 验证dist/manifest.webmanifest和sw.js生成
```

**关键验证指标**：
- TypeScript编译: `tsc --noEmit` ✅
- Vite构建: `vite build` ✅
- PWA生成: `manifest.webmanifest + sw.js` ✅
- 构建时间: ~5.2s (无性能回归) ✅

#### 🚨 预防机制

**1. 环境一致性检查**
```yaml
# .github/workflows/ci.yml
env:
  NODE_VERSION: '20'  # 固定Node.js版本
  CI: 'true'          # 明确CI环境标识
```

**2. 本地CI模拟工具**
```bash
# package.json scripts
"build:ci": "cross-env CI=true NODE_ENV=production vite build"
"test:ci-local": "act --container-architecture linux/amd64"
```

**3. 文档化配置模式**
```typescript
// vite.config.ts - 注释说明别名优先级
alias: [
  // 🎯 CRITICAL: 具体文件映射必须在前，确保PWA插件兼容
  { find: '@/lib/utils', replacement: resolve(__dirname, './src/lib/utils.ts') },
  // 🔧 PATTERN: 目录模式匹配
  { find: /^@\/components\/(.*)/, replacement: resolve(__dirname, './src/components/$1') },
  // 🏠 BASE: 根映射必须最后，避免覆盖具体规则
  { find: '@', replacement: resolve(__dirname, './src') }
]
```

#### 📋 故障排除检查清单

当CI构建失败而本地成功时，按以下顺序检查：

1. **[ ]** Node.js版本一致性 (`package.json` engines vs CI)
2. **[ ]** 文件扩展名显式性 (`.ts` vs 省略)
3. **[ ]** 路径别名优先级 (数组顺序很关键)
4. **[ ]** PWA插件兼容性 (是否绕过别名解析)
5. **[ ]** 工作目录上下文 (`__dirname` 解析基准)
6. **[ ]** 大小写敏感性 (Linux vs Windows)

#### 🎯 最佳实践总结

**配置原则**：
- **显式优于隐式**：明确指定文件扩展名和绝对路径
- **优先级明确**：使用数组别名确保解析顺序
- **插件兼容**：考虑第三方插件的解析机制
- **环境一致**：本地尽可能模拟CI环境

**开发工作流**：
```bash
# 每次别名配置变更后的验证序列
1. npm run type-check    # TypeScript编译检查
2. npm run build         # 本地标准构建
3. npm run build:ci      # 本地CI模拟构建
4. git commit && git push # 触发实际CI验证


After each code modification or feature addition, you must update or create a project documentation file named `PROJECT_DOCS.md` at the root of the project. This file is crucial for maintaining context across sessions.

Your primary goal is to create documentation that allows future AI sessions to understand the project's architecture, key components, and logic without needing to read the entire codebase.

**Documentation Structure and Content:**

1.  **Project Overview:**
    * Start with a brief, high-level summary of the project's purpose and main functionality.

2.  **Project Structure (`Project Structure`):**
    * Use a Mermaid.js `graph TD` (top-down) diagram to visualize the project's directory and file structure.
    * Focus on key files and directories, omitting trivial ones (e.g., `node_modules`, `.git`).
    * Update this diagram whenever files or directories are added, removed, or renamed.

3.  **Core Components & Logic (`Core Components & Logic`):**
    * Document the most important classes, functions, methods, and components.
    * For each component, provide:
        * **Name:** The name of the class, function, or component.
        * **Purpose:** A concise explanation of what it does.
        * **Parameters/Props:** A list of its inputs, their types, and a brief description.
        * **Returns:** What it outputs, if applicable.
        * **Example Usage:** A short code snippet showing how to use it.

4.  **Interaction and Data Flow Diagrams (`Interaction and Data Flow`):**
    * Use Mermaid.js diagrams extensively to illustrate relationships and processes. This is critical for avoiding ambiguity.
    * **Sequence Diagrams (`sequenceDiagram`):** Use these to show the sequence of calls between different functions or components for a specific user action (e.g., "User Login Sequence").
    * **Class Diagrams (`classDiagram`):** Use these to model the relationships between classes, including inheritance and composition.
    * **Flowcharts (`flowchart TD`):** Use these to describe complex logic, algorithms, or data flow within a function or across the application.

**Updating the Documentation:**

* **Reflect All Changes:** After you modify, add, or delete any code, you MUST immediately update the relevant sections in `PROJECT_DOCS.md`.
* **Update Diagrams:** If a code change affects the project structure, class relationships, or interaction flows, the corresponding Mermaid diagrams must be updated to reflect the new state accurately.
* **Be Concise and Clear:** The documentation should be easy to parse. Use clear headings, bullet points, and code blocks. Avoid jargon where simpler terms suffice.

By strictly following this rule, you will ensure that project knowledge is preserved and readily available, enabling consistent and context-aware assistance across all future interactions.
```