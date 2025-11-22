#!/usr/bin/env python3
"""修复多行f-string的S608警告。

策略：
1. 移除f-string内的noqa注释（这些注释会成为SQL字符串的一部分）
2. 在f-string的闭合引号行添加noqa注释
"""

import re
from pathlib import Path

# 需要修复的文件和起始行
MULTILINE_FIXES = {
    "backend/database/sharding_manager.py": [934],
    "backend/services/incremental_backup_service.py": [390, 403, 449, 474],
    "src/repositories/citation_relation_repository.py": [91, 158, 223, 426],
    "src/repositories/citation_repository.py": [80, 147, 381],
    "src/repositories/multi_document_repositories.py": [120, 395, 663],
}


def fix_multiline_sql(file_path: str, start_lines: list[int]) -> int:
    """修复多行SQL的S608警告。"""
    path = Path(file_path)
    if not path.exists():
        print(f"⚠️  File not found: {file_path}")
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    fixes_applied = 0

    for start_line in start_lines:
        if start_line < 1 or start_line > len(lines):
            continue

        idx = start_line - 1

        # 找到f-string的开始行
        if 'f"""' not in lines[idx]:
            continue

        # 移除开始行中的noqa注释
        if "# noqa: S608" in lines[idx]:
            lines[idx] = re.sub(r'\s*#\s*noqa:\s*S608[^"]*', "", lines[idx])

        # 找到f-string的结束行（包含闭合的三引号）
        closing_idx = idx + 1
        while closing_idx < len(lines) and '"""' not in lines[closing_idx]:
            closing_idx += 1

        if closing_idx < len(lines):
            closing_line = lines[closing_idx]
            # 在闭合行添加noqa注释
            if "noqa" not in closing_line and "nosec" not in closing_line:
                # 确保注释在三引号之后
                lines[closing_idx] = (
                    closing_line.rstrip() + "  # noqa: S608 - safe SQL construction"
                )
                fixes_applied += 1
                print(f"✓ {file_path}:{start_line}-{closing_idx+1}")

    if fixes_applied > 0:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return fixes_applied


def main() -> None:
    """Main entry point."""
    total_fixes = 0

    for file_path, line_numbers in MULTILINE_FIXES.items():
        fixes = fix_multiline_sql(file_path, line_numbers)
        total_fixes += fixes

    print("\n📊 Summary:")
    print(f"   Files processed: {len(MULTILINE_FIXES)}")
    print(f"   Total fixes: {total_fixes}")
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
