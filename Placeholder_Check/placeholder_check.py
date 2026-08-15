#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian 占位符检测脚本
适用：全库 Markdown 未完成信号扫描。
检测：
  - 英文占位：XXX / xxxx / TODO / TBD / FIXME / WIP
  - 中文占位：待补充 / 待完善 / 待更新 / 待填写 / 建设中 / 占位 / 未完待续 等
  - 结构占位：空链接 [[]] / 空图片 ![]( ) / 模板变量残留 {{...}} / 空 frontmatter 字段
  - 注释待办：HTML 注释中残留的 TODO/待/补
安全：只读检测，不修改任何文件；输出 Markdown 报告到 96 事务管理/。
用法：python placeholder_check.py [--vault ...] [--output ...] [--include-templates]
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
REPORT_PATH = "96 事务管理/占位符检测报告.md"
# 逗号陷阱警告：集合元素间必须有逗号！
EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "10_Inbox", "99 模板", ".sitian", "98 附件", "96 事务管理", ".agent_context", "Obsidian_AI_Sandbox"}

# =========================================================
# 占位符模式定义
# =========================================================
# (类型, 正则, 级别) —— 级别：🔴 核心占位 / 🟡 提示类
# XXX 模式：前后紧邻中文字符视为敏感词打码（如"XX了"），不报；仅在独立记号位置（标点/空白/行首尾）报
PATTERNS = [
    ("XXX占位", re.compile(r"(?<![A-Za-z\u4e00-\u9fff])[xX]{3,}(?![A-Za-z\u4e00-\u9fff])"), "🔴"),
    ("TODO待办", re.compile(r"\b(?:TODO|TBD|FIXME|WIP)\b"), "🔴"),
    ("中文占位", re.compile(r"(?:待补充|待完善|待更新|待填写|待添加|待写|补充中|建设中|占位符|占位|未完待续|待续|此处待补)"), "🔴"),
    ("空链接", re.compile(r"\[\[\s*\]\]"), "🔴"),
    ("空图片", re.compile(r"!\[\]\(\s*\)"), "🔴"),
    ("模板变量", re.compile(r"\{\{[^{}]*\}\}"), "🔴"),
    ("注释待办", re.compile(r"<!--[^>]*(?:TODO|FIXME|待|补)[^>]*-->", re.IGNORECASE), "🟡"),
]

# 中文键名（用于空 frontmatter 字段检测）
FM_KEY_RE = re.compile(r"^\s*([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff\-]*):\s*(?:#.*)?$")


# =========================================================
# 编码回退链（ROSA 实测：UTF-8 为主，部分源文件为 UTF-16-LE）
# =========================================================
def read_text_safe(path: Path) -> str:
    """按编码回退链读取文本文件，全部失败则返回空串。"""
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


# =========================================================
# frontmatter 解析
# =========================================================
def parse_frontmatter(text: str):
    """
    返回 (frontmatter_dict, empty_fields)
    empty_fields: [(key, line_no)] 键后无值（且非缩进列表/子键）
    """
    fm = {}
    empty_fields = []
    if not text.startswith("---"):
        return fm, empty_fields
    end = text.find("\n---", 3)
    if end == -1:
        return fm, empty_fields
    fm_block = text[3:end]
    lines = fm_block.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^([\w\u4e00-\u9fff\-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2).strip()
        if val:
            fm[key] = val
            continue
        # 键后无值：检查后续行是否有缩进内容（列表项 / 子键）
        j = i + 1
        has_child = False
        while j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t")):
            stripped = lines[j].strip()
            if stripped.startswith("- ") or re.match(r"^[\w\u4e00-\u9fff\-]+:", stripped):
                has_child = True
                break
            j += 1
        if not has_child:
            empty_fields.append((key, i + 2))  # 第 1 行为 ---，所以 +2
            fm[key] = ""
    return fm, empty_fields


# =========================================================
# 占位符检测
# =========================================================
def detect_in_text(text: str, fm: dict, downgrade_xxx: bool = False):
    """
    返回 [(类型, 行号, 片段, 级别)]
    行号为原文（含 frontmatter）中的行号。
    downgrade_xxx=True：资料原文（07 资料收藏/97 旧资料存档）中的 X 串多为敏感词打码，降为 🟢 提示。
    """
    hits = []
    body = text
    body_start_line = 0  # body 首行在原文中的 0-indexed 行号
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body_start = end + 5  # 跳过第二个 --- 行
            body = text[body_start:]
            body_start_line = text[:body_start].count("\n")

    for ptype, pat, lv in PATTERNS:
        for m in pat.finditer(body):
            lv_eff = "🟢" if (ptype == "XXX占位" and downgrade_xxx) else lv
            line_no = body[: m.start()].count("\n") + 1 + body_start_line
            snippet = body.split("\n")[line_no - 1 - body_start_line].strip()
            if len(snippet) > 40:
                snippet = snippet[:40] + "…"
            hits.append((ptype, line_no, snippet, lv_eff))
    return hits


# =========================================================
# 报告生成
# =========================================================
def generate_report(vault: Path, results: dict, excluded_dirs: set, total_files: int) -> str:
    """
    results: {str(path): {"hits": [(type, line, snippet, lv)], "publish": bool|None,
                          "empty_fm": [(key, line_no)], "is_draft": bool}}
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# 🏷️ Obsidian 占位符检测报告\n")
    lines.append(f"> **生成时间**：{now}")
    lines.append(f"> **模式**：只读（未修改任何文件）")
    lines.append(f"> **库路径**：`{vault}`")
    lines.append("")

    # ---- 1. 总览 ----
    files_with_hits = [p for p, r in results.items() if r["hits"] or r["empty_fm"]]
    type_counter = defaultdict(int)
    for p, r in results.items():
        for t, _, _, lv in r["hits"]:
            type_counter[(t, lv)] += 1
        for key, _ in r["empty_fm"]:
            type_counter[("空frontmatter字段", "🟡")] += 1
    total_hits = sum(v for _, v in type_counter.items())

    lines.append("## 1️⃣ 总览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|---:|")
    lines.append(f"| 扫描笔记数 | {total_files} |")
    lines.append(f"| 检出占位符的笔记数 | {len(files_with_hits)} |")
    lines.append(f"| 占位符总条数 | {total_hits} |")
    lines.append("")

    # ---- 2. 按类型聚合 ----
    lines.append("## 2️⃣ 占位符类型分布\n")
    if not type_counter:
        lines.append("✅ 未检出任何占位符。\n")
    else:
        lines.append("| 类型 | 级别 | 数量 |")
        lines.append("|:---|:---:|---:|")
        for (t, lv), c in sorted(type_counter.items(), key=lambda x: -x[1]):
            lines.append(f"| {t} | {lv} | {c} |")
        lines.append("")

    # ---- 3. 按文件明细 ----
    lines.append("## 3️⃣ 按文件明细\n")
    if not files_with_hits:
        lines.append("✅ 无。\n")
    else:
        lines.append(f"共 **{len(files_with_hits)}** 个文件存在占位符，按严重度排序：\n")
        for path_str in sorted(files_with_hits, key=lambda p: (-(len(results[p]["hits"]) + len(results[p]["empty_fm"])), p)):
            r = results[path_str]
            rel = path_str.replace(str(vault), "").lstrip("/\\")
            status = "草稿" if r["is_draft"] else ("已发布" if r["publish"] is not False else "未发布")
            lines.append(f"### `{rel}`（{status}）\n")
            if r["empty_fm"]:
                for key, ln in r["empty_fm"]:
                    lines.append(f"- 🟡 frontmatter 空字段 `{key}`（第 {ln} 行）")
            for t, ln, snip, lv in r["hits"]:
                lines.append(f"- {lv} **{t}**（第 {ln} 行）：`{snip}`")
            lines.append("")

    # ---- 4. 检测规则说明 ----
    lines.append("## 4️⃣ 检测规则说明\n")
    lines.append("| 规则 | 说明 |")
    lines.append("|:---|:---|")
    lines.append("| XXX 串 | 前后紧邻中文字符视为敏感词打码（如 `XX了`），不报；仅在标点/空白/行首尾处的独立 X 串才报；`07 资料收藏`/`97 旧资料存档` 中的 X 串视为原文打码，降为 🟢 提示 |")
    lines.append("| 空 frontmatter 字段 | `key:` 后无值且非缩进列表/子键时报告；预留字段（如 `aliases:`）也属待填写 |")
    lines.append("| 排除目录 | `.obsidian`、`.git`、`.trash`、`10_Inbox`（草稿）、`99 模板`（模板含占位符属设计）、`98 附件`、`96 事务管理`（报告自身） |")
    lines.append("| 模板变量 | 正文残留 `{{...}}` 说明模板未渲染 |")
    lines.append("")
    return "\n".join(lines)


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian 占位符检测（只读，输出报告）")
    parser.add_argument("--vault", default=VAULT_PATH, help="知识库根目录")
    parser.add_argument("--output", default=None, help="报告输出路径（默认 96 事务管理/占位符检测报告.md）")
    parser.add_argument("--include-inbox", action="store_true", help="包含 10_Inbox 沙盒草稿")
    parser.add_argument("--include-templates", action="store_true", help="包含 99 模板目录")
    parser.add_argument("--quiet", action="store_true", help="精简控制台输出")
    return parser.parse_args()


def main():
    args = parse_args()
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"执行失败。脚本：placeholder_check.py；错误类型：目录不存在；建议操作：检查 --vault 路径")
        return 1

    excluded = set(EXCLUDED_DIRS)
    if args.include_inbox:
        excluded.discard("10_Inbox")
    if args.include_templates:
        excluded.discard("99 模板")

    import os
    results = {}
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for fn in filenames:
            if not fn.lower().endswith(".md"):
                continue
            total_files += 1
            path = Path(dirpath) / fn
            text = read_text_safe(path)
            fm, empty_fm = parse_frontmatter(text)
            is_source = any(k in str(path) for k in ("07 资料收藏", "97 旧资料存档"))
            hits = detect_in_text(text, fm, downgrade_xxx=is_source)
            if hits or empty_fm:
                is_draft = "10_Inbox" in path.parts
                results[str(path)] = {
                    "hits": hits,
                    "empty_fm": empty_fm,
                    "publish": fm.get("publish"),
                    "is_draft": is_draft,
                }

    report = generate_report(vault, results, excluded, total_files)
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = vault / REPORT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    n_files = len(results)
    n_hits = sum(len(r["hits"]) + len(r["empty_fm"]) for r in results.values())
    print(f"检测完成：{total_files} 个笔记，{n_files} 个文件含占位符（共 {n_hits} 条）")
    print(f"报告已输出：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
