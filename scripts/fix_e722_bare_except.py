#!/usr/bin/env python3
"""修复E722 bare except错误（改为except Exception）。"""

from pathlib import Path


# E722错误位置（所有bare except）
E722_FIXES = {
    "backend/api/security/endpoint_protection.py": [78, 107],
    "backend/database/query_optimizer.py": [190, 271],
    "backend/database/read_write_splitter.py": [706],
    "backend/middleware/cache_optimization_middleware.py": [453],
    "backend/services/centralized_logging_service.py": [182],
    "backend/services/connection_pool_manager.py": [160, 366],
    "backend/services/custom_metrics_collector.py": [307],
    "backend/services/l1_memory_cache.py": [668],
    "backend/services/redis_cache_service.py": [654],
    "backend/services/secrets_monitoring_service.py": [449],
    "backend/services/secrets_validation_service.py": [780],
}


def fix_bare_except(file_path: str, line_numbers: list[int]) -> int:
    """修复bare except为except Exception。"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    fixes_applied = 0

    for line_num in line_numbers:
        if line_num < 1 or line_num > len(lines):
            continue

        idx = line_num - 1
        line = lines[idx]

        # 检查是否是bare except
        if line.strip() == "except:":
            # 替换为except Exception:
            indentation = len(line) - len(line.lstrip())
            lines[idx] = " " * indentation + "except Exception:"
            fixes_applied += 1
            print(f"✓ {file_path}:{line_num}")
        elif "except:" in line:
            # 处理except:在同一行有其他代码的情况
            lines[idx] = line.replace("except:", "except Exception:")
            fixes_applied += 1
            print(f"✓ {file_path}:{line_num}")

    if fixes_applied > 0:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes_applied


def main() -> None:
    """Main entry point."""
    total_fixes = 0

    print("=== Fixing E722 Bare Except Statements ===\n")

    for file_path, line_numbers in E722_FIXES.items():
        fixes = fix_bare_except(file_path, line_numbers)
        total_fixes += fixes

    print(f"\n📊 Summary:")
    print(f"   Files processed: {len(E722_FIXES)}")
    print(f"   Total fixes: {total_fixes}")
    print("\n✅ Done! All bare except statements fixed.")


if __name__ == "__main__":
    main()
