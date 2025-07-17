#!/bin/bash
# 🚀 快速Act测试脚本
# 用于快速验证CI/CD流水线的核心功能

set -e

echo "🔍 快速Act测试开始..."

# 1. 检查act是否安装
if ! command -v act &> /dev/null; then
    echo "❌ Act未安装，请先安装act工具"
    echo "💡 安装命令: winget install nektos.act"
    exit 1
fi

echo "✅ Act已安装: $(act --version)"

# 2. 检查Docker是否运行
if ! docker info &> /dev/null; then
    echo "❌ Docker未运行，请启动Docker Desktop"
    exit 1
fi

echo "✅ Docker运行正常"

# 3. 列出所有可用的workflow
echo "📋 可用的workflow列表:"
act --list

# 4. 测试主流水线语法
echo "🔍 测试主流水线语法..."
if act --list --workflows .github/workflows/main-pipeline.yml; then
    echo "✅ 主流水线语法正确"
else
    echo "❌ 主流水线语法错误"
    exit 1
fi

# 5. 干跑测试 - 强制完整执行
echo "🧪 测试强制完整执行模式(干跑)..."
if act workflow_dispatch \
    --input force_full_pipeline=true \
    --workflows .github/workflows/main-pipeline.yml \
    --dryrun; then
    echo "✅ 强制完整执行测试通过"
else
    echo "❌ 强制完整执行测试失败"
    exit 1
fi

# 6. 干跑测试 - 智能检测
echo "🔍 测试智能检测模式(干跑)..."
if act push \
    --workflows .github/workflows/main-pipeline.yml \
    --dryrun; then
    echo "✅ 智能检测测试通过"
else
    echo "❌ 智能检测测试失败"
    exit 1
fi

echo "🎉 快速测试完成！所有基本功能正常"
echo "💡 现在可以运行完整测试: ./test_cicd_complete.sh"
echo "🚀 或者直接运行实际测试: act workflow_dispatch --input force_full_pipeline=true"