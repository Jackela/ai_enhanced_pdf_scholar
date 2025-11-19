#!/usr/bin/env python3
"""为TOP3复杂函数添加noqa注释（带合理性说明）。

这些函数复杂度高但结构合理，重构风险大于收益：
1. get_database_health (21) - 多指标聚合检查，顺序逻辑清晰
2. analyze_index_effectiveness (17) - 索引分析算法，多分支决策
3. process_rag_query (16) - RAG流程编排，状态机逻辑
"""

from pathlib import Path

# TOP3最复杂函数（带合理性说明）
TOP3_COMPLEX_FUNCTIONS = {
    "backend/services/db_performance_monitor.py": {
        "line": 959,
        "function": "get_database_health",
        "complexity": 21,
        "justification": "Multi-metric health aggregation with clear sequential logic",
    },
    "src/database/migrations.py": {
        "line": 1637,
        "function": "analyze_index_effectiveness",
        "complexity": 17,
        "justification": "Index analysis algorithm with multi-branch decision tree",
    },
    "backend/api/routes/async_rag.py": {
        "line": 76,
        "function": "process_rag_query",
        "complexity": 16,
        "justification": "RAG workflow orchestration with state machine logic",
    },
}


def add_noqa_to_function(file_path: str, config: dict) -> bool:
    """在函数定义行添加noqa注释。"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return False

    lines = path.read_text(encoding="utf-8").splitlines()
    line_num = config["line"]

    if line_num < 1 or line_num > len(lines):
        print(f"⚠️  Invalid line number: {file_path}:{line_num}")
        return False

    idx = line_num - 1
    line = lines[idx]

    # 跳过已有noqa的行
    if "noqa: C901" in line:
        print(f"⏭️  Already suppressed: {file_path}:{line_num}")
        return False

    # 验证这是函数定义行
    if "def " not in line or config["function"] not in line:
        print(f"⚠️  Not a function definition: {file_path}:{line_num}")
        print(f"   Expected: {config['function']}, Found: {line.strip()}")
        return False

    # 在行尾添加noqa注释
    comment = f"  # noqa: C901 - {config['justification']}"
    lines[idx] = line.rstrip() + comment

    # 写回文件
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"✓ {file_path}:{line_num}")
    print(f"  Function: {config['function']} (complexity {config['complexity']})")
    print(f"  Reason: {config['justification']}")
    return True


def main() -> None:
    """Main entry point."""
    total_fixes = 0

    print("=== Suppressing TOP3 Complex Functions (C901) ===\n")

    for file_path, config in TOP3_COMPLEX_FUNCTIONS.items():
        if add_noqa_to_function(file_path, config):
            total_fixes += 1
        print()

    print("📊 Summary:")
    print(f"   Files processed: {len(TOP3_COMPLEX_FUNCTIONS)}")
    print(f"   Functions suppressed: {total_fixes}")
    print("\n✅ Done! TOP3 complex functions documented and suppressed.")


if __name__ == "__main__":
    main()
