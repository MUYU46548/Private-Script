#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian 断链批量修复脚本
适用：断链因笔记重命名/移动产生时，批量更新引用。
流程：
  1. 扫描全库断链目标（链接指向不存在的 .md）
  2. 自动建议映射：断链目标名与现有文件名相似度 ≥ 阈值且唯一候选 → 高置信
  3. 默认 --dry-run：只输出建议与影响清单（只读）
  4. --apply：实际执行替换（仅处理唯一高置信候选；其余仅列出）
替换规则：[[旧名]] / [[旧名|别名]] / [[旧名#锚点]] / [[路径/旧名]] → 对应新名。
编码：写回时保留原文件编码（UTF-8 / UTF-16-LE / GBK）。
安全：--apply 为危险操作，默认只报告；建议先 --dry-run 审阅。
用法：python link_refactor.py [--vault ...] [--output ...] [--apply] [--similarity 0.8]
"""

import re
import difflib
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =========================================================
# 默认配置
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"
REPORT_PATH = "96 事务管理/断链修复建议报告.md"
EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "10_Inbox", "99 模板", ".sitian", "98 附件", "96 事务管理", ".agent_context", "Obsidian_AI_Sandbox"}
LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")


# =========================================================
# 编码回退链（带编码返回，写回时保留）
# =========================================================
def read_with_encoding(path: Path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16-le", "gbk", "gb18030"):
        try:
            text = raw.decode(enc)
            if enc == "utf-16-le" and not re.search(r"[\u4e00-\u9fff]", text):
                continue
            return text, enc
        except (UnicodeDecodeError, ValueError):
            continue
    return "", "utf-8"


def normalize_target(raw: str) -> str:
    """[[目标|别名]] / [[目标#锚点]] / [[路径/目标]] → 目标 basename"""
    t = raw.split("|", 1)[0].strip()
    t = re.split(r"[#^]", t, 1)[0].strip()
    t = t.replace("\\", "/").split("/")[-1].strip()
    return t


def is_attachment(name: str) -> bool:
    return Path(name).suffix.lower() in {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico",
        ".pdf", ".mp3", ".mp4", ".wav", ".ogg", ".m4a", ".flac", ".mov", ".avi",
        ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    }


# =========================================================
# 替换
# =========================================================
def replace_in_text(text: str, mapping: dict) -> tuple:
    """返回 (new_text, replace_count)。mapping: {old_basename: new_basename}"""
    count = 0

    def repl(m):
        nonlocal count
        raw = m.group(1)
        target = raw.split("|", 1)[0]
        suffix = raw[len(target):]
        base = normalize_target(target)
        if base in mapping:
            new_target = target.replace(base, mapping[base], 1)
            count += 1
            return "[[" + new_target + suffix + "]]"
        return m.group(0)

    return LINK_RE.sub(repl, text), count


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian 断链批量修复（默认只读建议，--apply 执行替换）")
    parser.add_argument("--vault", default=VAULT_PATH, help="知识库根目录")
    parser.add_argument("--output", default=None, help="建议报告输出路径（默认 96 事务管理/断链修复建议报告.md）")
    parser.add_argument("--apply", action="store_true", help="危险操作：实际执行替换（仅唯一高置信候选）")
    parser.add_argument("--similarity", type=float, default=0.8, help="建议相似度阈值（默认 0.8）")
    parser.add_argument("--min-references", type=int, default=1, help="断链目标被引用至少 N 次才考虑（默认 1）")
    parser.add_argument("--include-inbox", action="store_true", help="包含 10_Inbox 沙盒草稿")
    parser.add_argument("--include-templates", action="store_true", help="包含 99 模板目录")
    parser.add_argument("--quiet", action="store_true", help="精简控制台输出")
    return parser.parse_args()


def main():
    args = parse_args()
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"执行失败。脚本：link_refactor.py；错误类型：目录不存在；建议操作：检查 --vault 路径")
        return 1

    excluded = set(EXCLUDED_DIRS)
    if args.include_inbox:
        excluded.discard("10_Inbox")
    if args.include_templates:
        excluded.discard("99 模板")

    import os
    md_files = []
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for fn in filenames:
            if fn.lower().endswith(".md"):
                md_files.append(Path(dirpath) / fn)

    existing_stems = {f.stem for f in md_files}

    # 1. 断链检测：目标不存在且非附件
    broken_refs = defaultdict(list)  # 断链目标 -> [来源文件]
    for f in md_files:
        text, _ = read_with_encoding(f)
        for m in LINK_RE.finditer(text):
            t = normalize_target(m.group(1))
            if not t or t in existing_stems or is_attachment(t):
                continue
            broken_refs[t].append(f)

    # 2+3. 相似度建议 + 唯一高置信候选（一遍扫描）
    suggestions = {}  # broken -> (score, candidate)
    high_conf = {}
    for broken, sources in broken_refs.items():
        if len(sources) < args.min_references:
            continue
        cands = []
        for stem in existing_stems:
            if stem == broken:
                continue
            r = difflib.SequenceMatcher(None, broken, stem).ratio()
            if r >= args.similarity:
                cands.append((r, stem))
        if not cands:
            continue
        cands.sort(reverse=True)
        suggestions[broken] = cands[0]
        if len(cands) == 1:
            high_conf[broken] = cands[0][1]

    # 4. 生成报告
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# 🔧 Obsidian 断链修复建议报告\n")
    lines.append(f"> **生成时间**：{now}")
    lines.append(f"> **模式**：{'已执行替换（--apply）' if args.apply else '只读（未修改任何文件）'}")
    lines.append(f"> **库路径**：`{vault}`")
    lines.append("")
    lines.append("## 1️⃣ 总览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|---:|")
    lines.append(f"| 扫描笔记数 | {len(md_files)} |")
    lines.append(f"| 断链目标总数 | {len(broken_refs)} |")
    lines.append(f"| 有相似建议的断链 | {len(suggestions)} |")
    lines.append(f"| 唯一高置信候选（可执行） | {len(high_conf)} |")
    lines.append("")

    # 建议映射
    lines.append("## 2️⃣ 建议映射（相似度 ≥ {:.2f}）\n".format(args.similarity))
    if suggestions:
        lines.append("| 断链目标 | 建议映射 | 相似度 | 引用次数 | 可执行 |")
        lines.append("|:---|:---|:---:|:---:|:---:|")
        for b in sorted(suggestions, key=lambda x: (-len(broken_refs[x]), -suggestions[x][0])):
            score, cand = suggestions[b]
            ok = "✅" if b in high_conf else "⚠️ 多候选"
            lines.append(f"| `{b}` | `{cand}` | {score:.2f} | {len(broken_refs[b])} | {ok} |")
        lines.append("")
    else:
        lines.append("✅ 无建议映射。\n")
    # 无建议断链
    no_sug = [b for b in broken_refs if b not in suggestions]
    if no_sug:
        lines.append(f"### 无相似建议的断链（{len(no_sug)} 个，需人工处理）\n")
        lines.append("| 断链目标 | 引用次数 | 来源（前3） |")
        lines.append("|:---|:---:|:---|")
        for b in sorted(no_sug, key=lambda x: -len(broken_refs[x])):
            srcs = "、".join(f"`{f.name}`" for f in broken_refs[b][:3])
            lines.append(f"| `{b}` | {len(broken_refs[b])} | {srcs} |")
        lines.append("")

    # 5. 执行或预览
    lines.append("## 3️⃣ 影响文件预览\n")
    affected = defaultdict(list)  # 文件 -> [(旧, 新)]
    if high_conf:
        for f in md_files:
            text, enc = read_with_encoding(f)
            new_text, n = replace_in_text(text, high_conf)
            if n:
                affected[str(f)].append(n)
        if not args.apply:
            n_files = len(affected)
            n_links = sum(sum(v) for v in affected.values())
            lines.append(f"（--dry-run）将修改 **{n_files}** 个文件、**{n_links}** 处链接：\n")
            lines.append("| 文件 | 替换处数 |")
            lines.append("|:---|:---:|")
            for fp in sorted(affected)[:50]:
                lines.append(f"| `{Path(fp).name}` | {sum(affected[fp])} |")
            if len(affected) > 50:
                lines.append(f"| ... 共 {len(affected)} 个 | |")
            lines.append("")
    else:
        lines.append("✅ 无唯一高置信候选可执行。\n")

    lines.append("## 4️⃣ 汇总行动建议\n")
    lines.append("| 级别 | 行动 | 数量 |")
    lines.append("|:---|:---|:---:|")
    lines.append(f"| 🔴 高 | 审阅建议映射，确认后 `--apply` 执行 | {len(high_conf)} |")
    lines.append(f"| 🟡 中 | 人工处理无建议断链（可能是待创建页面，参考单向链接检测报告） | {len(no_sug)} |")
    lines.append(f"| 🟢 低 | 低于引用阈值的断链 | {sum(1 for b in broken_refs if len(broken_refs[b]) < args.min_references)} |")
    lines.append("")

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = vault / REPORT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    # --apply 执行
    applied = 0
    if args.apply and high_conf:
        for f in md_files:
            text, enc = read_with_encoding(f)
            new_text, n = replace_in_text(text, high_conf)
            if n:
                f.write_bytes(new_text.encode(enc))
                applied += 1
                if not args.quiet:
                    print(f"  修改 {f.name}: {n} 处")

    print(f"检测完成：{len(md_files)} 个笔记，断链 {len(broken_refs)}，建议 {len(suggestions)}，可执行 {len(high_conf)}")
    if args.apply:
        print(f"  --apply 已修改 {applied} 个文件")
    else:
        print(f"  未执行修改（--dry-run）；确认后加 --apply")
    print(f"报告已输出：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
