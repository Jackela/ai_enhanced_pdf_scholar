#!/bin/bash
# 🚀 Pipeline Force Test Script
# 测试强制执行功能的本地验证脚本

set -e

echo "🚀 AI Enhanced PDF Scholar - Force Pipeline Test"
echo "=================================================="

# 检查 act 是否安装
if ! command -v act &> /dev/null; then
    echo "❌ Act not found. Please install act first:"
    echo "   npm install -g @nektos/act"
    echo "   Or download from: https://github.com/nektos/act"
    exit 1
fi

echo "✅ Act found: $(act --version)"

# 检查 Docker 是否运行
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# 创建测试输入文件
echo "📋 Creating test inputs..."
cat > .github/workflows/test-inputs.json << EOF
{
  "test_mode": true,
  "force_full_pipeline": true
}
EOF

echo "🧪 Test Configuration:"
echo "- Test Mode: true (forces all changes)"
echo "- Force Full Pipeline: true"
echo "- Expected: All jobs should run"

# 测试选项
echo ""
echo "🎯 Test Options:"
echo "1. Test Change Detection only"
echo "2. Test Quality Lightning only"  
echo "3. Test Full Pipeline (WARNING: Very long)"
echo "4. List all available workflows"
echo ""

read -p "Select test option (1-4): " choice

case $choice in
    1)
        echo "🔍 Testing Change Detection..."
        act workflow_dispatch \
            --workflows .github/workflows/main-pipeline.yml \
            --job detect-changes \
            --input-file .github/workflows/test-inputs.json \
            --verbose
        ;;
    2)
        echo "⚡ Testing Quality Lightning..."
        act workflow_dispatch \
            --workflows .github/workflows/main-pipeline.yml \
            --job quality-lightning \
            --input-file .github/workflows/test-inputs.json \
            --verbose
        ;;
    3)
        echo "🚀 Testing Full Pipeline (This will take a long time!)..."
        echo "⚠️  Press Ctrl+C to cancel within 5 seconds..."
        sleep 5
        
        act workflow_dispatch \
            --workflows .github/workflows/main-pipeline.yml \
            --input-file .github/workflows/test-inputs.json \
            --verbose
        ;;
    4)
        echo "📋 Available workflows:"
        act --list
        ;;
    *)
        echo "❌ Invalid option. Exiting."
        exit 1
        ;;
esac

# 清理测试文件
rm -f .github/workflows/test-inputs.json

echo ""
echo "✅ Test completed!"
echo "📊 Check the output above for results"
echo ""
echo "💡 Tips for troubleshooting:"
echo "- If Docker issues: Restart Docker Desktop"
echo "- If permission issues: Run with sudo (Linux/Mac)"
echo "- If workflow not found: Check .github/workflows/ directory"
echo "- If container issues: Try: docker system prune -f"