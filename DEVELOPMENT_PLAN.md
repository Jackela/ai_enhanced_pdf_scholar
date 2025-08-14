# AI Enhanced PDF Scholar - 文档管理与RAG增强开发计划

## 📋 项目目标

将当前的PDF阅读工具升级为完整的文档管理和智能问答系统，重点实现：

1. **RAG数据库持久化** - 避免重复处理，提供高效查询
2. **内容级去重检测** - 基于文档内容哈希，而非文件路径
3. **文档书架管理** - 用户友好的文档组织界面
4. **向后兼容性** - 保持现有功能稳定

## 🎯 设计原则

- **SOLID原则** - 单一职责、开闭原则、依赖倒置
- **测试优先** - 完善的测试覆盖，性能优化
- **渐进式增强** - 分阶段实施，确保稳定性
- **用户体验优先** - 关注性能和可用性
- **性能导向** - 持续优化测试和CI/CD效率

## 🏗️ 技术架构设计

### 数据库设计
```sql
-- 文档表
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    file_path TEXT,
    file_hash TEXT UNIQUE NOT NULL,
    file_size INTEGER,
    page_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME,
    metadata JSON
);

-- 向量索引表
CREATE TABLE vector_indexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    index_path TEXT NOT NULL,
    index_hash TEXT UNIQUE NOT NULL,
    chunk_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents (id)
);

-- 标签表（未来扩展）
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT
);

-- 文档标签关联表
CREATE TABLE document_tags (
    document_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (document_id) REFERENCES documents (id),
    FOREIGN KEY (tag_id) REFERENCES tags (id)
);
```

### 新增模块结构
```
src/
├── database/
│   ├── __init__.py
│   ├── connection.py         # 数据库连接管理
│   ├── migrations.py         # 数据库迁移
│   └── models.py            # 数据模型定义
├── repositories/
│   ├── __init__.py
│   ├── base_repository.py    # 基础仓储模式
│   ├── document_repository.py # 文档数据访问
│   └── vector_repository.py  # 向量索引数据访问
├── services/
│   ├── document_library_service.py  # 文档库业务逻辑
│   ├── content_hash_service.py      # 内容哈希服务
│   └── enhanced_rag_service.py      # 增强的RAG服务
├── ui/
│   ├── document_library_panel.py    # 文档库UI面板
│   ├── document_import_dialog.py    # 导入对话框
│   └── document_search_widget.py    # 搜索组件
└── controllers/
    └── library_controller.py        # 文档库控制器
```

## 📅 开发里程碑

### ✅ 阶段一：数据持久化基础 (完成)
- [x] 数据库设计和迁移系统
- [x] 基础Repository模式实现
- [x] 内容哈希服务开发
- [x] 单元测试覆盖

### ✅ 阶段二：智能引用系统 (完成 - v2.1.0)
- [x] 引用数据模型设计 (CitationModel, CitationRelationModel)
- [x] 引用解析算法实现 (CitationParsingService)
- [x] 引用仓储层实现 (CitationRepository, CitationRelationRepository)
- [x] 引用业务逻辑服务 (CitationService)
- [x] 引用网络分析基础
- [x] TDD完整测试套件 (63个测试用例)
- [x] 数据库迁移003 (citations, citation_relations表)
- [x] E2E工作流验证

### 🔄 阶段三：引用系统完善 (进行中)
- [ ] 引用解析算法优化 (目标>40%精度)
- [ ] 完整引用网络分析功能
- [ ] 引用API端点实现
- [ ] 引用数据导出功能 (BibTeX, EndNote)
- [ ] 前端引用管理界面

### 阶段四：RAG服务增强 (Week 3-4)
- [ ] 增强RAG服务集成数据库
- [ ] 重复检测和去重机制
- [ ] 向量索引持久化优化
- [ ] 集成测试

### 阶段五：文档书架UI (Week 5-6)
- [ ] 文档库面板组件
- [ ] 导入/删除功能
- [ ] 搜索和过滤
- [ ] 用户体验优化

### 阶段六：系统集成与优化 (Week 7-8)
- [ ] 性能优化
- [ ] 错误处理完善
- [ ] 用户文档
- [ ] 端到端测试

## 🧪 测试策略

### 测试层次
1. **单元测试** - 每个Service、Repository独立测试
2. **集成测试** - 数据库交互、文件系统操作
3. **UI测试** - 关键用户交互流程
4. **性能测试** - 基础性能基准验证

### 测试覆盖率目标
- 核心功能测试覆盖完整
- 关键路径验证
- 自动化回归测试

### ✅ 测试性能优化 (已完成)
- **共享测试fixtures** - 减少数据库重复创建
- **并行测试执行** - 支持多核加速
- **CI/CD优化** - 缩短流水线执行时间
- **性能基准测试** - 自动性能验证脚本

## 📏 质量保证

### 代码质量
- 遵循PEP 8代码规范
- 类型注解覆盖
- 文档字符串完整
- Code Review流程

### 性能指标
- 基础功能响应正常
- 数据库操作稳定
- 测试执行效率优化
- 合理的资源使用

## 🔄 向后兼容性

### 兼容性保证
- 现有配置文件格式保持不变
- 原有缓存目录平滑迁移
- API接口向前兼容
- 用户数据零丢失

### 迁移策略
- 检测现有缓存文件
- 自动导入到新数据库
- 保留原缓存作为备份
- 渐进式迁移提示

## 📊 风险管理

### 技术风险
- **数据库性能** - 采用索引优化和分页查询
- **大文件处理** - 流式处理和进度反馈
- **向量存储** - 预留扩展接口支持外部向量数据库

### 用户体验风险
- **迁移复杂性** - 自动化迁移，用户无感知
- **学习成本** - 保持界面一致性，渐进式引导
- **性能退化** - 性能基准测试，持续监控

## 🎓 引用系统技术设计

### 引用解析架构
```python
# 引用解析服务设计模式
class CitationParsingService:
    def parse_citations_from_text(self, text: str) -> list[dict]:
        # 多格式支持 (APA, MLA, Chicago, IEEE)
        # 正则表达式 + 规则引擎
        # 置信度评分算法
        pass
```

### 网络分析设计
```python
# 引用网络构建
class CitationService:
    def build_citation_network(self, document_id: int, depth: int = 1) -> dict:
        # 图遍历算法
        # 多层关系建模
        # 网络统计分析
        pass
```

### 数据库优化策略
- **索引策略**: 按作者、年份、类型等常用查询优化
- **关系建模**: 支持document-to-document和citation-to-citation映射
- **性能考虑**: 分页查询、缓存机制、批量操作

### 质量保证体系
- **TDD开发**: 63个测试用例覆盖所有关键功能
- **置信度评分**: 每个解析结果都有0.0-1.0的质量评分
- **数据验证**: 严格的输入验证和错误处理
- **性能基准**: E2E测试验证系统性能指标

### 扩展性设计
- **模块化**: 解析算法可独立升级
- **接口驱动**: 支持不同解析引擎的插拔
- **格式支持**: 易于添加新的学术引用格式
- **API就绪**: 完整的RESTful API设计

## 🎉 成功标准

### 功能完整性
- [x] 基础文档导入功能
- [x] RAG查询功能正常
- [x] 智能引用提取与分析系统
- [x] 基础用户交互
- [x] 数据一致性

### 引用系统成功指标
- [x] 多格式引用解析 (APA, MLA, Chicago, IEEE)
- [x] 置信度评分系统 (0.0-1.0)
- [x] 引用网络分析基础
- [x] TDD测试覆盖 (63个测试用例)
- [x] 数据库优化设计
- [ ] 解析精度 >40% (当前33%)
- [ ] 完整API端点实现
- [ ] 前端管理界面

### 项目价值
- [x] 完善的代码架构 (SOLID原则)
- [x] 优化的测试体系 (TDD方法论)
- [x] 现代化的开发流程
- [x] 持续的性能改进
- [x] 学术研究支持能力