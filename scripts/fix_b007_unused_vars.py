#!/usr/bin/env python3
"""修复B007未使用的循环变量（添加下划线前缀）。"""

import re
from pathlib import Path


# B007错误位置和变量名
B007_FIXES = {
    "backend/api/middleware/rate_limiting.py": [(296, "endpoint")],
    "backend/api/routes/metrics_websocket.py": [(451, "client_id"), (461, "client_id")],
    "backend/api/websocket_manager.py": [(122, "room_name")],
    "backend/core/secrets.py": [(1046, "provider_type")],
    "backend/core/secrets_migration.py": [(102, "secret_type"), (325, "value")],
    "backend/services/async_error_handling.py": [(405, "operation_key")],
    "backend/services/cache_coherency_manager.py": [(454, "level_name")],
    "backend/services/cache_optimization_service.py": [(440, "pattern_id")],
    "backend/services/cache_telemetry_service.py": [(585, "layer")],
    "backend/services/cache_warming_service.py": [(514, "profile"), (570, "profile")],
    "backend/services/connection_pool_manager.py": [(220, "i")],
    "backend/services/l1_memory_cache.py": [(505, "score"), (548, "score")],
    "backend/services/performance_dashboard_service.py": [(165, "op_name")],
    "backend/services/redis_cluster_manager.py": [(307, "master_name")],
    "backend/services/secrets_validation_service.py": [
        (379, "rule_name"),
        (1072, "secret_name"),
    ],
    "backend/services/simple_alerting_service.py": [(295, "category_name")],
    "backend/services/streaming_validation_service.py": [(353, "i")],
    "src/database/migrations.py": [(1028, "ref_table")],
    "src/services/rag/chunking_strategies.py": [(223, "para_idx")],
    "src/services/rag/performance_monitor.py": [(222, "op_type")],
}


def fix_unused_variable(file_path: str, fixes: list[tuple[int, str]]) -> int:
    """在循环变量前添加下划线前缀。"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return 0

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    fixes_applied = 0

    for line_num, var_name in fixes:
        if line_num < 1 or line_num > len(lines):
            continue

        idx = line_num - 1
        line = lines[idx]

        # 在for循环中将变量名替换为_前缀版本
        # 匹配模式: for var_name, ... 或 for ..., var_name, ...

        # 方案1: for var_name in ...
        pattern1 = rf"\bfor\s+{re.escape(var_name)}\s+in\s+"
        if re.search(pattern1, line):
            lines[idx] = re.sub(pattern1, f"for _{var_name} in ", line)
            fixes_applied += 1
            print(f"✓ {file_path}:{line_num} ({var_name} -> _{var_name})")
            continue

        # 方案2: for (var1, var_name) in ... 或 for var1, var_name in ...
        pattern2 = rf"\bfor\s+\(?([^)]+)\)?\s+in\s+"
        match = re.search(pattern2, line)
        if match:
            vars_part = match.group(1)
            # 将var_name替换为_var_name
            vars_list = [v.strip() for v in vars_part.split(",")]
            new_vars = []
            for v in vars_list:
                if v == var_name:
                    new_vars.append(f"_{var_name}")
                else:
                    new_vars.append(v)

            new_vars_part = ", ".join(new_vars)
            lines[idx] = re.sub(
                rf"\bfor\s+\(?{re.escape(vars_part)}\)?\s+in\s+",
                f"for {new_vars_part} in ",
                line,
            )
            fixes_applied += 1
            print(f"✓ {file_path}:{line_num} ({var_name} -> _{var_name})")

    if fixes_applied > 0:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes_applied


def main() -> None:
    """Main entry point."""
    total_fixes = 0

    print("=== Fixing B007 Unused Loop Variables ===\n")

    for file_path, fixes in B007_FIXES.items():
        fixed = fix_unused_variable(file_path, fixes)
        total_fixes += fixed

    print(f"\n📊 Summary:")
    print(f"   Files processed: {len(B007_FIXES)}")
    print(f"   Total fixes: {total_fixes}")
    print("\n✅ Done! All unused loop variables renamed with _ prefix.")


if __name__ == "__main__":
    main()
