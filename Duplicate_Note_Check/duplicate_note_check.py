#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian 近似重复笔记检测脚本
适用：发现同一实体/同一内容建了两页的情况。
方法：
  1. 文本归一化（去 frontmatter/空白/标点，小写）
  2. 5-gram 倒排预筛（共享 gram 的文件对）
  3. 精确相似度（difflib.SequenceMatcher ratio）≥ 阈值 → 报告
安全：只读检测，不修改任何文件。
用法：python duplicate_note_check.py [--vault ...] [--output ...] [--threshold 0.85] [--min-len 100]
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
REPORT_PATH = "96 事务管理/近似重复笔记报告.md"
EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "10_Inbox", "99 模板", ".sitian", "98 附件", "96 事务管理", ".agent_context", "Obsidian_AI_Sandbox"}
THRESHOLD = 0.85       # 相似度阈值
MIN_LEN = 100          # 归一化后最小文本长度（低于此不参与，避免短页误判）
MIN_SHARED_GRAMS = 8   # 5-gram 共享数量下限（预筛，越高候选越少）
GRAM_N = 5
JACCARD_PRE = 0.70     # 字符集合 Jaccard 预筛阈值（SequenceMatcher 前的快速过滤）


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


def normalize(text: str) -> str:
    """去除 frontmatter/空白/标点，小写"""
    text = re.sub(r"^---.*?---", "", text, flags=re.DOTALL)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
    return text.lower()


def get_grams(t: str, n: int = GRAM_N):
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian 近似重复笔记检测（只读，输出报告）")
    parser.add_argument("--vault", default=VAULT_PATH, help="知识库根目录")
    parser.add_argument("--output", default=None, help="报告输出路径（默认 96 事务管理/近似重复笔记报告.md）")
    parser.add_argument("--threshold", type=float, default=THRESHOLD, help="相似度阈值（默认 0.85）")
    parser.add_argument("--min-len", type=int, default=MIN_LEN, help="参与检测的最小归一化文本长度（默认 100）")
    parser.add_argument("--include-inbox", action="store_true", help="包含 10_Inbox 沙盒草稿")
    parser.add_argument("--include-templates", action="store_true", help="包含 99 模板目录")
    parser.add_argument("--quiet", action="store_true", help="精简控制台输出")
    return parser.parse_args()


def main():
    args = parse_args()
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"执行失败。脚本：duplicate_note_check.py；错误类型：目录不存在；建议操作：检查 --vault 路径")
        return 1

    excluded = set(EXCLUDED_DIRS)
    if args.include_inbox:
        excluded.discard("10_Inbox")
    if args.include_templates:
        excluded.discard("99 模板")

    import os
    items = []  # (path_str, norm_text)
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for fn in filenames:
            if not fn.lower().endswith(".md"):
                continue
            total_files += 1
            path = Path(dirpath) / fn
            text = read_text_safe(path)
            norm = normalize(text)
            if len(norm) >= args.min_len:
                items.append((str(path), norm))

    n = len(items)
    if n < 2:
        print(f"参与对比的笔记不足 2 个（{n}），跳过")
        return 0

    # 5-gram 倒排预筛
    gram_index = defaultdict(set)
    for idx, (_, t) in enumerate(items):
        for g in get_grams(t):
            gram_index[g].add(idx)

    # 过滤高频 gram（出现在 >20% 文件的 gram 无区分度，跳过避免候选爆炸）
    gram_limit = max(20, n // 10)
    gram_index = {g: s for g, s in gram_index.items() if len(s) <= gram_limit}

    # 统计共享 gram 数：仅共享 ≥ MIN_SHARED_GRAMS 的文件对进入精确比较
    shared = defaultdict(int)
    for g, idxs in gram_index.items():
        if len(idxs) < 2:
            continue
        lst = sorted(idxs)
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                shared[(lst[i], lst[j])] += 1

    cand_pairs = [(i, j) for (i, j), c in shared.items() if c >= MIN_SHARED_GRAMS]

    # 精确相似度：Jaccard 快速预筛 → SequenceMatcher
    pairs = []
    for i, j in cand_pairs:
        p1, t1 = items[i]
        p2, t2 = items[j]
        # 长度差过滤：ratio 上界 ≤ min/max，阈值 0.85 要求长度比 ≥ 0.85
        if min(len(t1), len(t2)) / max(len(t1), len(t2)) < args.threshold:
            continue
        # Jaccard 预筛（字符集合，O(len) 快速过滤）
        s1, s2 = set(t1), set(t2)
        inter = len(s1 & s2)
        if inter / len(s1 | s2) < JACCARD_PRE:
            continue
        r = difflib.SequenceMatcher(None, t1, t2).ratio()
        if r >= args.threshold:
            pairs.append((r, p1, p2, len(t1), len(t2)))

    pairs.sort(key=lambda x: -x[0])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# 👯 Obsidian 近似重复笔记报告\n")
    lines.append(f"> **生成时间**：{now}")
    lines.append(f"> **模式**：只读（未修改任何文件）")
    lines.append(f"> **库路径**：`{vault}`")
    lines.append(f"> **阈值**：相似度 ≥ {args.threshold}（归一化文本，忽略空白/标点/frontmatter）")
    lines.append("")
    lines.append("## 1️⃣ 总览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|---:|")
    lines.append(f"| 扫描笔记数 | {total_files} |")
    lines.append(f"| 参与对比（长度≥{args.min_len}） | {n} |")
    lines.append(f"| 近似重复对 | {len(pairs)} |")
    lines.append("")
    lines.append("## 2️⃣ 近似重复对（按相似度排序）\n")
    if not pairs:
        lines.append("✅ 未发现近似重复笔记。\n")
    else:
        lines.append("| 相似度 | 笔记 A | 笔记 B | A 字数 | B 字数 |")
        lines.append("|:---:|:---|:---|:---:|:---:|")
        for r, p1, p2, l1, l2 in pairs:
            lines.append(f"| {r:.2f} | `{Path(p1).name}` | `{Path(p2).name}` | {l1} | {l2} |")
        lines.append("")
    lines.append("## 3️⃣ 汇总行动建议\n")
    lines.append("| 级别 | 行动 | 数量 |")
    lines.append("|:---|:---|:---:|")
    lines.append(f"| 🔴 高 | 相似度 ≥ 0.95（高度重复，建议合并） | {sum(1 for r, *_ in pairs if r >= 0.95)} |")
    lines.append(f"| 🟡 中 | 0.85~0.95（核对是否同一实体两页） | {sum(1 for r, *_ in pairs if r < 0.95)} |")
    lines.append("")
    lines.append("> 注：列表页/索引页可能因结构相似被误报；报告为只读建议，合并需人工确认。\n")

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = vault / REPORT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"检测完成：{total_files} 个笔记，参与对比 {n}，近似重复对 {len(pairs)}")
    print(f"报告已输出：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
