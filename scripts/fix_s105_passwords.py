#!/usr/bin/env python3
"""修复S105 hardcoded password误报（全部是常量定义，非真实密码）。"""

import re
from pathlib import Path

# S105错误位置（所有都是常量/枚举定义）
S105_FIXES = {
    "backend/api/auth/constants.py": [14, 19],
    "backend/core/secrets.py": [36, 38, 39],
    "backend/services/audit_logging_service.py": [52, 53],
    "backend/services/secrets_monitoring_service.py": [59, 60, 61],
}


def fix_s105_line(line: str, file_path: str) -> str:
    """为S105添加或替换noqa注释。"""
    # 跳过已有正确noqa的行
    if "# noqa: S105" in line:
        return line

    # 替换# nosec为# noqa: S105
    if "# nosec" in line:
        return line.replace("# nosec", "# noqa: S105 - constant name, not password")

    # 添加新的noqa注释
    # 判断注释类型
    if "constants.py" in file_path or "audit_logging" in file_path:
        comment = "  # noqa: S105 - event type constant, not password"
    elif "secrets_monitoring" in file_path:
        comment = "  # noqa: S105 - metric key constant, not password"
    else:
        comment = "  # noqa: S105 - config key, not password"

    # 在行尾添加注释
    return line.rstrip() + comment


def fix_file(file_path: str, line_numbers: list[int]) -> int:
    """修复文件中的S105警告。"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    fixes_applied = 0

    for line_num in line_numbers:
        if 1 <= line_num <= len(lines):
            original = lines[line_num - 1]
            modified = fix_s105_line(original, file_path)
            if modified != original:
                lines[line_num - 1] = modified
                fixes_applied += 1
                print(f"✓ {file_path}:{line_num}")

    if fixes_applied > 0:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes_applied


def main() -> None:
    """Main entry point."""
    total_fixes = 0

    for file_path, line_numbers in S105_FIXES.items():
        fixes = fix_file(file_path, line_numbers)
        total_fixes += fixes

    print("\n📊 Summary:")
    print(f"   Files processed: {len(S105_FIXES)}")
    print(f"   Total fixes: {total_fixes}")
    print("\n✅ Done! All S105 false positives suppressed.")


if __name__ == "__main__":
    main()
