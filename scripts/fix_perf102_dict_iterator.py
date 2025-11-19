#!/usr/bin/env python3
"""修复PERF102 dict迭代器优化（改用.values()或.keys()）。"""

from pathlib import Path


# PERF102错误位置（从ruff输出获取）
PERF102_FIXES = {
    "backend/api/middleware/rate_limiting.py": [(296, "values")],
    "backend/api/routes/metrics_websocket.py": [(451, "values"), (461, "values")],
    "backend/api/websocket_manager.py": [(122, "values")],
    "backend/core/secrets.py": [(1046, "values")],
    "backend/services/async_error_handling.py": [(405, "values")],
    "backend/services/cache_coherency_manager.py": [(454, "values")],
    "backend/services/cache_optimization_service.py": [(440, "values")],
    "backend/services/cache_telemetry_service.py": [(585, "values")],
    "backend/services/cache_warming_service.py": [(570, "keys")],
    "backend/services/performance_dashboard_service.py": [(165, "values")],
    "backend/services/redis_cluster_manager.py": [(307, "values")],
    "backend/services/secrets_validation_service.py": [
        (379, "values"),
        (1072, "values"),
    ],
    "backend/services/simple_alerting_service.py": [(295, "values")],
    "src/services/rag/performance_monitor.py": [(222, "values")],
}


def fix_dict_iterator(file_path: str, fixes: list[tuple[int, str]]) -> int:
    """将.items()改为.values()或.keys()。"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    fixes_applied = 0

    for line_num, method in fixes:
        if line_num < 1 or line_num > len(lines):
            continue

        idx = line_num - 1
        line = lines[idx]

        # 将.items()替换为.values()或.keys()
        if ".items()" in line:
            if method == "values":
                lines[idx] = line.replace(".items()", ".values()")
            elif method == "keys":
                lines[idx] = line.replace(".items()", ".keys()")
            fixes_applied += 1
            print(f"✓ {file_path}:{line_num} (.items() → .{method}())")

    if fixes_applied > 0:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes_applied


def main() -> None:
    """Main entry point."""
    total_fixes = 0

    print("=== Fixing PERF102 Dict Iterator Issues ===\n")

    for file_path, fixes in PERF102_FIXES.items():
        fixed = fix_dict_iterator(file_path, fixes)
        total_fixes += fixed

    print(f"\n📊 Summary:")
    print(f"   Files processed: {len(PERF102_FIXES)}")
    print(f"   Total fixes: {total_fixes}")
    print("\n✅ Done! All PERF102 dict iterator issues fixed.")


if __name__ == "__main__":
    main()
