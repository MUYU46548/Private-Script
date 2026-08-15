#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian Frontmatter 发布前检查脚本
适用：Quartz 站点发布前的 frontmatter 完整性检查。
检测：
  1. 完全缺失 frontmatter（无 --- 起始）
  2. 缺失 publish 字段
  3. publish 字段非布尔值（true/false）
输出：按目录分组的 Markdown 清单报告，与 Obsidian_YAML_Fix/obsidian_yaml_fix.py 衔接（先查后修）。
安全：只读检测，不修改任何文件。
用法：python publish_check.py [--vault ...] [--output ...] [--include-inbox] [--include-templates]
"""

import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =========================================================
# 默认配置
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"
REPORT_PATH = "96 事务管理/发布前检查报告.md"
EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "10_Inbox", "99 模板", ".sitian", "98 附件", "96 事务管理", ".agent_context", "Obsidian_AI_Sandbox"}


# =========================================================
# 编码回退链
# =========================================================
def read_text_safe(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16-le", "gbk", "gb18030"):
        try:
            text = raw.decode(enc)
            if enc == "utf-16-le" and not re.search(r"[\u4e00-\u9fff]", text):
                continue
            return text
        except (UnicodeDecodeError, ValueError):
            continue
    return ""


def check_frontmatter(text: str):
    """
    返回 (kind, detail)
    kind: "ok" | "no_fm" | "no_publish" | "bad_publish"
    detail: 具体说明
    """
    if not text.startswith("---"):
        return "no_fm", "完全缺失 frontmatter（无 --- 起始）"
    end = text.find("\n---", 3)
    if end == -1:
        return "no_fm", "frontmatter 未闭合（无结束 ---）"
    fm_block = text[3:end]
    publish_found = False
    for line in fm_block.split("\n"):
        m = re.match(r"^\s*publish\s*:\s*(.*)$", line)
        if m:
            publish_found = True
            val = m.group(1).strip().lower()
            if val not in ("true", "false"):
                return "bad_publish", f"publish 值非布尔：`{val}`"
            break
    if not publish_found:
        return "no_publish", "缺少 publish 字段"
    return "ok", ""


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian Frontmatter 发布前检查（只读，输出报告）")
    parser.add_argument("--vault", default=VAULT_PATH, help="知识库根目录")
    parser.add_argument("--output", default=None, help="报告输出路径（默认 96 事务管理/发布前检查报告.md）")
    parser.add_argument("--include-inbox", action="store_true", help="包含 10_Inbox 沙盒草稿")
    parser.add_argument("--include-templates", action="store_true", help="包含 99 模板目录")
    parser.add_argument("--quiet", action="store_true", help="精简控制台输出")
    return parser.parse_args()


def main():
    args = parse_args()
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"执行失败。脚本：publish_check.py；错误类型：目录不存在；建议操作：检查 --vault 路径")
        return 1

    excluded = set(EXCLUDED_DIRS)
    if args.include_inbox:
        excluded.discard("10_Inbox")
    if args.include_templates:
        excluded.discard("99 模板")

    import os
    # kind -> 目录 -> [文件]
    issues = defaultdict(lambda: defaultdict(list))
    total_files = 0
    ok_count = 0
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for fn in filenames:
            if not fn.lower().endswith(".md"):
                continue
            total_files += 1
            path = Path(dirpath) / fn
            text = read_text_safe(path)
            kind, detail = check_frontmatter(text)
            if kind == "ok":
                ok_count += 1
                continue
            rel_dir = str(path.parent).replace(str(vault), "").lstrip("/\\") or "（根目录）"
            issues[kind][rel_dir].append((fn, detail))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kind_labels = {
        "no_fm": "🔴 缺 frontmatter",
        "no_publish": "🟡 缺 publish 字段",
        "bad_publish": "🔴 publish 非布尔",
    }
    total_issues = sum(len(files) for g in issues.values() for files in g.values())

    lines = []
    lines.append("# 📋 Obsidian Frontmatter 发布前检查报告\n")
    lines.append(f"> **生成时间**：{now}")
    lines.append(f"> **模式**：只读（未修改任何文件）")
    lines.append(f"> **库路径**：`{vault}`")
    lines.append("")
    lines.append("## 1️⃣ 总览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|---:|")
    lines.append(f"| 扫描笔记数 | {total_files} |")
    lines.append(f"| 检查通过 | {ok_count} |")
    lines.append(f"| 存在问题 | {total_issues} |")
    lines.append("")
    lines.append("## 2️⃣ 问题统计\n")
    lines.append("| 类型 | 数量 |")
    lines.append("|:---|:---:|")
    for kind in ("no_fm", "no_publish", "bad_publish"):
        n = sum(len(f) for f in issues[kind].values())
        lines.append(f"| {kind_labels[kind]} | {n} |")
    lines.append("")
    lines.append("## 3️⃣ 按目录分组明细\n")
    for kind in ("no_fm", "no_publish", "bad_publish"):
        groups = issues[kind]
        if not groups:
            continue
        lines.append(f"### {kind_labels[kind]}\n")
        for d in sorted(groups):
            lines.append(f"**`{d}`**（{len(groups[d])} 个）\n")
            lines.append("| 文件 | 说明 |")
            lines.append("|:---|:---|")
            for fn, detail in sorted(groups[d]):
                lines.append(f"| `{fn}` | {detail} |")
            lines.append("")
    lines.append("## 4️⃣ 汇总行动建议\n")
    lines.append("| 级别 | 行动 | 数量 |")
    lines.append("|:---|:---|:---:|")
    lines.append(f"| 🔴 高 | 补 frontmatter / 修复 publish 值（发布前必须） | {sum(len(f) for f in issues['no_fm'].values()) + sum(len(f) for f in issues['bad_publish'].values())} |")
    lines.append(f"| 🟡 中 | 补 publish 字段（可用 Obsidian_YAML_Fix/obsidian_yaml_fix.py 批量加 true；如草稿设 false） | {sum(len(f) for f in issues['no_publish'].values())} |")
    lines.append("")

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = vault / REPORT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"检测完成：{total_files} 个笔记，{ok_count} 通过，{total_issues} 存在问题")
    print(f"报告已输出：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
