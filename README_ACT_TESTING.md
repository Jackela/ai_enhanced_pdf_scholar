# 🚀 Act Local CI/CD Testing Guide - Updated

## 📋 Overview

This guide documents how to run and test the GitHub Actions CI/CD pipeline locally using the `act` CLI tool, including issues found and fixes applied.

## ✅ Issues Found and Fixed

### Issue 1: Invalid Cache Configuration File
**Problem**: `cache-config.yml` was not a valid GitHub Actions workflow but was treated as one by act.

**Fix Applied**:
```bash
# Move invalid config file to documentation
mkdir -p docs/ci-config
mv .github/workflows/cache-config.yml docs/ci-config/
```

### Issue 2: Circular Environment Variable Reference
**Problem**: `ci-enhanced.yml` had circular reference to `env.TEST_PARALLELISM`.

**Error**: `Line: 464 Column 34: Unknown Variable Access env`

**Fix Applied**: Direct references instead of env variable references
- Lines 464, 544, 558, 570, 583, 872 updated

**Status**: ✅ All issues resolved

## 🛠️ 准备工作

### 1. 安装Act工具

```bash
# Windows (推荐)
winget install nektos.act

# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

### 2. 启动Docker Desktop

确保Docker Desktop正在运行，Act需要Docker来模拟GitHub Actions环境。

### 3. 配置文件

项目已包含以下配置文件：
- `.actrc` - Act配置文件
- `.env` - 环境变量配置
- `test_cicd_complete.sh` - 完整测试脚本
- `act_quick_test.sh` - 快速测试脚本

## 🚀 快速开始

### 1. 快速验证

```bash
# 运行快速测试
./act_quick_test.sh
```

### 2. 完整测试

```bash
# 运行完整测试套件
./test_cicd_complete.sh
```

### 3. 手动测试

```bash
# 测试强制完整执行
act workflow_dispatch \
  --input force_full_pipeline=true \
  --workflows .github/workflows/main-pipeline.yml

# 测试智能检测
act push \
  --workflows .github/workflows/main-pipeline.yml
```

## 📊 测试场景

### 🎯 强制完整执行测试

**目的**: 验证所有6个CI/CD阶段都能正确执行

```bash
act workflow_dispatch \
  --input force_full_pipeline=true \
  --workflows .github/workflows/main-pipeline.yml \
  --verbose
```

**预期结果**:
- ✅ 所有6个阶段都会执行
- ✅ 不会因为变更检测而跳过任何job
- ✅ 可以验证每个阶段的实际功能

### 🔍 智能检测测试

**目的**: 验证智能变更检测机制

```bash
act push \
  --workflows .github/workflows/main-pipeline.yml \
  --verbose
```

**预期结果**:
- 🔍 根据文件变更智能选择执行阶段
- ⚡ 提高执行效率，跳过不相关的job
- 📈 这是正常的优化行为

### 🧪 单个Workflow测试

```bash
# 测试质量检查
act workflow_call \
  --workflows .github/workflows/quality-lightning.yml \
  --input frontend-changed=true \
  --input backend-changed=true

# 测试构建阶段
act workflow_call \
  --workflows .github/workflows/build-intelligent.yml \
  --input frontend-changed=true \
  --input backend-changed=true
```

## 🎛️ 测试选项

### 基本选项

```bash
# 干跑测试（不实际执行）
act --dryrun

# 详细输出
act --verbose

# 列出所有workflows
act --list

# 指定特定workflow
act --workflows .github/workflows/main-pipeline.yml
```

### 高级选项

```bash
# 限制并行度
act --max-parallel 2

# 设置资源限制
act --memory 4g --cpus 2

# 清理容器
act --rm

# 重用容器
act --reuse
```

## 📋 CI/CD阶段验证清单

### 🔍 变更检测阶段
- [ ] 正确识别前端变更
- [ ] 正确识别后端变更
- [ ] 正确识别配置变更
- [ ] 强制执行参数生效

### ⚡ 质量检查阶段
- [ ] 前端代码质量检查
- [ ] 后端代码质量检查
- [ ] TypeScript类型检查
- [ ] Python代码格式检查

### 🔧 构建阶段
- [ ] 前端构建成功
- [ ] 后端构建成功
- [ ] Docker镜像构建
- [ ] 构建产物上传

### 🧪 测试阶段
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] E2E测试通过
- [ ] 覆盖率报告生成

### 🔒 安全扫描阶段
- [ ] 依赖漏洞扫描
- [ ] 代码安全扫描
- [ ] 许可证检查
- [ ] 安全报告生成

### 📊 性能测试阶段
- [ ] 前端性能测试
- [ ] 后端性能测试
- [ ] 数据库性能测试
- [ ] 性能回归检测

### 🚀 部署阶段
- [ ] 前端部署
- [ ] 后端部署
- [ ] 健康检查
- [ ] 部署验证

## 🔧 故障排除

### 常见问题

1. **Docker权限问题**
   ```bash
   # 解决方案：确保Docker Desktop正在运行
   docker info
   ```

2. **内存不足**
   ```bash
   # 解决方案：增加Docker内存限制或使用更小的镜像
   act --memory 2g
   ```

3. **网络问题**
   ```bash
   # 解决方案：使用host网络
   act --network host
   ```

4. **容器清理**
   ```bash
   # 清理所有act容器
   docker system prune -f
   ```

### 调试技巧

```bash
# 查看详细日志
act --verbose

# 进入容器调试
act --interactive

# 保持容器运行
act --reuse

# 查看workflow步骤
act --list --workflows .github/workflows/main-pipeline.yml
```

## 📈 性能优化

### 缓存优化

```bash
# 启用容器重用
act --reuse

# 使用本地缓存
act --artifact-server-path /tmp/artifacts
```

### 并行优化

```bash
# 限制并行度避免资源冲突
act --max-parallel 2

# 使用更小的镜像
act -P ubuntu-latest=catthehacker/ubuntu:act-latest-slim
```

## 📊 测试报告

测试完成后，检查以下输出：

1. **成功率统计**
2. **执行时间分析**
3. **资源使用情况**
4. **错误日志详情**

## 🎯 下一步

完成本地测试后：

1. **修复发现的问题**
2. **优化CI/CD配置**
3. **提交到GitHub进行实际测试**
4. **监控生产环境性能**

## 📞 支持

如果遇到问题：

1. 检查Act官方文档：https://github.com/nektos/act
2. 查看GitHub Actions文档
3. 检查项目的`CLAUDE.md`文件
4. 提交Issue到项目仓库

---

**记住**: 本地测试的目的是验证CI/CD流水线的功能性，确保所有阶段都能正确执行，而不只是被智能检测跳过。