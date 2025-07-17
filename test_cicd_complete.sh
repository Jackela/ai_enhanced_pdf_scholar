#!/bin/bash
# 🚀 完整CI/CD流水线本地测试脚本
# AI Enhanced PDF Scholar - Act Local Testing

set -e

# 🎨 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 📊 统计变量
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 🔧 辅助函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    ((PASSED_TESTS++))
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((FAILED_TESTS++))
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_header() {
    echo -e "\n${PURPLE}========================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}========================================${NC}\n"
}

# 🧪 测试函数
test_act_installation() {
    log_header "1. 检查Act安装状态"
    ((TOTAL_TESTS++))
    
    if command -v act &> /dev/null; then
        log_success "Act已安装: $(act --version)"
        return 0
    else
        log_error "Act未安装，请先安装: https://github.com/nektos/act"
        return 1
    fi
}

test_docker_status() {
    log_header "2. 检查Docker状态"
    ((TOTAL_TESTS++))
    
    if docker info &> /dev/null; then
        log_success "Docker运行正常"
        return 0
    else
        log_error "Docker未运行，请启动Docker"
        return 1
    fi
}

test_workflow_syntax() {
    log_header "3. 检查Workflow语法"
    ((TOTAL_TESTS++))
    
    log_info "检查所有workflow文件语法..."
    
    local syntax_errors=0
    for workflow in .github/workflows/*.yml; do
        if [ -f "$workflow" ]; then
            log_info "检查: $workflow"
            if act --list --workflows "$workflow" &> /dev/null; then
                log_success "语法正确: $(basename "$workflow")"
            else
                log_error "语法错误: $(basename "$workflow")"
                ((syntax_errors++))
            fi
        fi
    done
    
    if [ $syntax_errors -eq 0 ]; then
        log_success "所有workflow语法检查通过"
        return 0
    else
        log_error "发现 $syntax_errors 个语法错误"
        return 1
    fi
}

test_main_pipeline_dryrun() {
    log_header "4. 主流水线干跑测试"
    ((TOTAL_TESTS++))
    
    log_info "测试主流水线干跑..."
    
    if act workflow_dispatch \
        --input force_full_pipeline=true \
        --workflows .github/workflows/main-pipeline.yml \
        --dryrun; then
        log_success "主流水线干跑测试通过"
        return 0
    else
        log_error "主流水线干跑测试失败"
        return 1
    fi
}

test_individual_workflows() {
    log_header "5. 单个Workflow测试"
    
    local workflows=(
        "quality-lightning.yml"
        "build-intelligent.yml"
        "test-comprehensive.yml"
        "security-optimized.yml"
        "performance-benchmark.yml"
        "deploy-intelligent.yml"
    )
    
    for workflow in "${workflows[@]}"; do
        ((TOTAL_TESTS++))
        log_info "测试: $workflow"
        
        if act workflow_call \
            --workflows ".github/workflows/$workflow" \
            --input frontend-changed=true \
            --input backend-changed=true \
            --dryrun; then
            log_success "$workflow 测试通过"
        else
            log_error "$workflow 测试失败"
        fi
    done
}

test_force_full_execution() {
    log_header "6. 强制完整执行测试"
    ((TOTAL_TESTS++))
    
    log_info "测试强制完整执行模式..."
    
    if act workflow_dispatch \
        --input force_full_pipeline=true \
        --workflows .github/workflows/main-pipeline.yml \
        --dryrun \
        --verbose; then
        log_success "强制完整执行测试通过"
        return 0
    else
        log_error "强制完整执行测试失败"
        return 1
    fi
}

test_smart_detection() {
    log_header "7. 智能检测测试"
    ((TOTAL_TESTS++))
    
    log_info "测试智能变更检测..."
    
    # 模拟push事件
    if act push \
        --workflows .github/workflows/main-pipeline.yml \
        --dryrun; then
        log_success "智能检测测试通过"
        return 0
    else
        log_error "智能检测测试失败"
        return 1
    fi
}

create_test_data() {
    log_header "🗂️ 创建测试数据"
    
    log_info "创建测试数据目录..."
    mkdir -p /tmp/test-data
    mkdir -p /tmp/artifacts
    
    # 创建示例测试文件
    echo "Test PDF content" > /tmp/test-data/sample.pdf
    echo "Test requirements" > /tmp/test-data/requirements.txt
    echo "Test package.json" > /tmp/test-data/package.json
    
    log_success "测试数据创建完成"
}

cleanup_test_data() {
    log_header "🧹 清理测试数据"
    
    log_info "清理测试数据..."
    rm -rf /tmp/test-data
    rm -rf /tmp/artifacts
    
    log_success "测试数据清理完成"
}

show_summary() {
    log_header "📊 测试结果汇总"
    
    echo -e "${CYAN}总测试数量:${NC} $TOTAL_TESTS"
    echo -e "${GREEN}通过测试:${NC} $PASSED_TESTS"
    echo -e "${RED}失败测试:${NC} $FAILED_TESTS"
    
    local success_rate=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    echo -e "${PURPLE}成功率:${NC} ${success_rate}%"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}🎉 所有测试通过！CI/CD流水线就绪！${NC}"
        return 0
    else
        echo -e "\n${RED}❌ 部分测试失败，请检查输出并修复问题${NC}"
        return 1
    fi
}

# 🚀 主执行流程
main() {
    log_header "🚀 开始AI Enhanced PDF Scholar CI/CD完整测试"
    
    # 创建测试数据
    create_test_data
    
    # 执行测试
    test_act_installation
    test_docker_status
    test_workflow_syntax
    test_main_pipeline_dryrun
    test_individual_workflows
    test_force_full_execution
    test_smart_detection
    
    # 清理和汇总
    cleanup_test_data
    show_summary
    
    if [ $FAILED_TESTS -eq 0 ]; then
        log_success "🎊 完整测试成功！现在可以运行实际的CI/CD流水线了！"
        echo -e "\n${CYAN}💡 下一步建议：${NC}"
        echo -e "1. 运行完整测试: ${YELLOW}act workflow_dispatch --input force_full_pipeline=true${NC}"
        echo -e "2. 测试智能检测: ${YELLOW}act push${NC}"
        echo -e "3. 部署到GitHub: ${YELLOW}git push origin main${NC}"
        exit 0
    else
        log_error "❌ 测试失败，请修复问题后重试"
        exit 1
    fi
}

# 🏁 脚本入口
if [ "$#" -eq 0 ]; then
    main
else
    case "$1" in
        "quick")
            test_act_installation
            test_docker_status
            test_workflow_syntax
            ;;
        "syntax")
            test_workflow_syntax
            ;;
        "dryrun")
            test_main_pipeline_dryrun
            ;;
        "full")
            test_force_full_execution
            ;;
        "smart")
            test_smart_detection
            ;;
        *)
            echo "使用方法: $0 [quick|syntax|dryrun|full|smart]"
            echo "  quick  - 快速检查"
            echo "  syntax - 语法检查"
            echo "  dryrun - 干跑测试"
            echo "  full   - 强制完整测试"
            echo "  smart  - 智能检测测试"
            exit 1
            ;;
    esac
fi