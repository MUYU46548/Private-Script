#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian 提及未链接检测脚本
适用：全库互链密度维护，落实"首次提及必链"规范。
检测：
  1. 首次提及未链接：正文出现实体名 ≥1 次但整个页面从未链接该实体
  2. 互提及未链接（强关联）：A 页提到 B、B 页也提到 A，但互不链接
规则（用户确认的链接规范）：
  - 首次提及 + 强关联必链；后续提及不强制 → 已有链接的实体一律豁免
  - 极高频词在代码中手动指定（COMMON_TERMS），默认不报
安全：只读检测，不修改任何文件；输出 Markdown 报告到 96 事务管理/。
用法：python mention_link_check.py [--vault ...] [--output ...] [--include-common]
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
REPORT_PATH = "96 事务管理/提及未链接检测报告.md"
# 逗号陷阱警告：集合元素间必须有逗号！
EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "10_Inbox", "99 模板", ".sitian", "98 附件", "96 事务管理", ".agent_context", "Obsidian_AI_Sandbox"}
INDEX_NAME_MARKERS = ("索引", "目录", "Index", "index", "README", "帮助", "导航", "主页", "Home")
# 极高频词（手动指定，通常稳定）：这些词出现在大量页面中，链接意义不大，默认不报
# 如需调整，直接在此增删；--include-common 可强制显示
COMMON_TERMS = {"人类", "世界", "魔法", "科技"}
# 最小提及次数过滤（同一页面重复提及不重复计数，此参数为文件维度下限）
MIN_MENTIONS = 1


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


def is_index_page(path: Path) -> bool:
    return any(marker in path.stem for marker in INDEX_NAME_MARKERS)


# =========================================================
# 正文预处理
# =========================================================
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

def normalize_target(raw: str) -> str:
    """[[目标|别名]] / [[目标#锚点]] / [[路径/目标]] → 目标 stem"""
    t = raw.split("|", 1)[0].strip()
    t = re.split(r"[#^]", t, 1)[0].strip()
    t = t.replace("\\", "/").split("/")[-1].strip()
    return t


def mask_and_extract(body: str):
    """
    返回 (masked, targets)
    masked：把 [[...]] 整段替换为等长空白（链接内文本不计入提及）
    targets：该页面已有的链接目标集合
    """
    targets = set()
    def repl(m):
        t = normalize_target(m.group(1))
        if t:
            targets.add(t)
        return " " * len(m.group(0))
    masked = WIKILINK_RE.sub(repl, body)
    return masked, targets


# =========================================================
# 最长匹配优先的实体提及扫描
# =========================================================
def scan_mentions(body: str, entities: list, page_self: str):
    """
    扫描正文中的实体提及（最长匹配优先、去重叠）。
    entities: 实体名列表（建议按长度降序）
    返回 Counter: entity -> 提及次数（排除页面自身标题）
    """
    counts = defaultdict(int)
    matches = []
    for ent in entities:
        if ent == page_self or not ent:
            continue
        if ent not in body:
            continue
        for m in re.finditer(re.escape(ent), body):
            matches.append((m.start(), m.end(), ent))
    # 去重叠：同一 start 保留最长；重叠处保留先出现的（已按 start 排序）
    matches.sort(key=lambda x: (x[0], -x[1]))
    last_end = -1
    for s, e, ent in matches:
        if s < last_end:
            continue
        counts[ent] += 1
        last_end = e
    return counts


def get_context_line(body: str, entity: str, start: int = 0) -> str:
    """返回实体首次出现的所在行片段（截断 40 字符）"""
    idx = body.find(entity, start)
    if idx == -1:
        return ""
    line_start = body.rfind("\n", 0, idx) + 1
    line_end = body.find("\n", idx)
    if line_end == -1:
        line_end = len(body)
    snip = body[line_start:line_end].strip()
    if len(snip) > 40:
        snip = snip[:40] + "…"
    return snip


# =========================================================
# 报告生成
# =========================================================
def generate_report(vault: Path, results: dict, total_files: int, entities_total: int,
                    excluded_dirs: set, include_common: bool) -> str:
    """
    results: {path_str: {"mentions": {ent: count}, "linked": set, "is_index": bool}}
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 计算违规：提及 ≥1 且无链接且非高频（或 include_common）
    violations = {}   # path_str -> {ent: count}
    mutual = []       # (fileA, fileB) 互提及未链接
    for p, r in results.items():
        viol = {}
        for ent, cnt in r["mentions"].items():
            if ent in r["linked"]:
                continue
            if ent in COMMON_TERMS and not include_common:
                continue
            if cnt >= MIN_MENTIONS:
                viol[ent] = cnt
        if viol:
            violations[p] = viol
    # 互提及：A 提及 B 且 B 提及 A（均未链接）
    for p1, r1 in results.items():
        for ent in r1["mentions"]:
            if ent in r1["linked"] or (ent in COMMON_TERMS and not include_common):
                continue
            if ent in results and ent != p1:
                r2 = results[ent]
                if p1 in r2["mentions"] and p1 not in r2["linked"]:
                    if p1 not in COMMON_TERMS or include_common:
                        pair = tuple(sorted((p1, ent)))
                        if pair not in mutual:
                            mutual.append(pair)

    lines = []
    lines.append("# 🔗 Obsidian 提及未链接检测报告\n")
    lines.append(f"> **生成时间**：{now}")
    lines.append(f"> **模式**：只读（未修改任何文件）")
    lines.append(f"> **库路径**：`{vault}`")
    lines.append("")

    # ---- 1. 总览 ----
    n_viol_files = len(violations)
    n_viol_ents = sum(len(v) for v in violations.values())
    lines.append("## 1️⃣ 总览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|---:|")
    lines.append(f"| 扫描笔记数 | {total_files} |")
    lines.append(f"| 实体词表数（页面标题） | {entities_total} |")
    lines.append(f"| 首次提及未链接的文件 | {n_viol_files} |")
    lines.append(f"| 首次提及未链接的实体条目 | {n_viol_ents} |")
    lines.append(f"| 互提及未链接（强关联） | {len(mutual)} |")
    lines.append("")

    # ---- 2. 互提及未链接（强关联） ----
    lines.append("## 2️⃣ 互提及未链接（强关联，建议优先补链）\n")
    if not mutual:
        lines.append("✅ 未发现。\n")
    else:
        lines.append(f"共 **{len(mutual)}** 对页面互相提及但互不链接：\n")
        lines.append("| 页面 A | 页面 B | 说明 |")
        lines.append("|:---|:---|:---|")
        for a, b in sorted(mutual):
            lines.append(f"| `{a}` | `{b}` | 双向提及，建议至少一方补链 |")
        lines.append("")
    # ---- 3. 按文件明细 ----
    lines.append("## 3️⃣ 首次提及未链接明细（按实体数排序）\n")
    if not violations:
        lines.append("✅ 未发现。\n")
    else:
        lines.append(f"共 **{n_viol_files}** 个文件存在首次提及未链接（每条：实体 → 首次出现片段）。\n")
        for p in sorted(violations, key=lambda x: (-len(violations[x]), x)):
            rel = p
            lines.append(f"### `{rel}`\n")
            body = results[p]["_body"]
            for ent in sorted(violations[p], key=lambda e: (-violations[p][e], e)):
                snip = get_context_line(body, ent)
                lines.append(f"- 🟡 **{ent}**（提及 {violations[p][ent]} 次）：`{snip}`")
            lines.append("")
    # 高频词提示
    skipped = 0
    if not include_common:
        for p, r in results.items():
            for ent in r["mentions"]:
                if ent in COMMON_TERMS and ent not in r["linked"]:
                    skipped += 1
        if skipped:
            lines.append(f"> 注：{skipped} 处极高频词（`{'`、`'.join(sorted(COMMON_TERMS))}`）提及已按配置跳过；用 `--include-common` 强制显示。\n")

    # ---- 4. 筛选说明 ----
    lines.append("## 4️⃣ 筛选说明\n")
    lines.append(f"- 排除目录：`{'`、`'.join(sorted(excluded_dirs))}`")
    lines.append(f"- 已有链接的实体：后续提及不报（首次已满足）")
    lines.append(f"- 极高频词（硬编码 `COMMON_TERMS`）：`{'`、`'.join(sorted(COMMON_TERMS))}`，需调整请修改脚本配置")
    lines.append(f"- 索引/导航页不参与")
    lines.append(f"- 匹配跳过 frontmatter、代码块、`[[链接]]` 内部文本")
    lines.append("")

    # ---- 5. 汇总行动建议 ----
    lines.append("## 5️⃣ 汇总行动建议\n")
    lines.append("| 级别 | 行动 | 数量 |")
    lines.append("|:---|:---|:---:|")
    lines.append(f"| 🔴 高 | 互提及未链接页面对（双向强关联）补链 | {len(mutual)} |")
    lines.append(f"| 🟡 中 | 首次提及未链接补 `[[链接]]` | {n_viol_ents} |")
    lines.append(f"| 🟢 低 | 高频词（默认跳过）按需处理 | {skipped} |")
    lines.append("")
    return "\n".join(lines)


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian 提及未链接检测（只读，输出报告）")
    parser.add_argument("--vault", default=VAULT_PATH, help="知识库根目录")
    parser.add_argument("--output", default=None, help="报告输出路径（默认 96 事务管理/提及未链接检测报告.md）")
    parser.add_argument("--include-common", action="store_true", help="强制显示极高频词")
    parser.add_argument("--include-inbox", action="store_true", help="包含 10_Inbox 沙盒草稿")
    parser.add_argument("--include-templates", action="store_true", help="包含 99 模板目录")
    parser.add_argument("--quiet", action="store_true", help="精简控制台输出")
    return parser.parse_args()


def main():
    args = parse_args()
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"执行失败。脚本：mention_link_check.py；错误类型：目录不存在；建议操作：检查 --vault 路径")
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

    # 实体词表：全部页面标题（不含扩展名）
    # 过滤：纯数字（章节编号如 "1"/"12"）与单字符实体（正文中匹配会大量误报）
    raw_entities = {f.stem for f in md_files}
    entities = sorted(
        (e for e in raw_entities if len(e) >= 2 and not re.fullmatch(r"\d+", e)),
        key=len, reverse=True)
    entities_total = len(entities)

    results = {}
    dup_seen = set()
    for f in md_files:
        text = read_text_safe(f)
        # 剥离 frontmatter
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                text = text[end + 5:]
        if is_index_page(f):
            continue  # 索引/导航页不参与
        body = FENCE_RE.sub(" ", text)
        # 标题行（# 开头）不计提及（标题常含其他实体子串，如 "# 月兔之城" 含 "月兔"）
        body = re.sub(r"(?m)^#{1,6}\s.*$", "", body)
        masked, targets = mask_and_extract(body)
        mentions = scan_mentions(masked, entities, f.stem)
        results[f.stem] = {
            "path": str(f),
            "mentions": mentions,
            "linked": targets,
            "_body": body,
        }
    # 重名提示（12 组重名文件的提及统计合并到同一 stem）
    if len(results) < len([f for f in md_files if not is_index_page(f)]) and not args.quiet:
        print(f"  ⚠️ 存在重名文件，实体词表按文件名去重（链接歧义）")

    report = generate_report(vault, results, len(md_files), entities_total, excluded, args.include_common)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = vault / REPORT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    n_viol = sum(1 for r in results.values() if any(e not in r["linked"] and (e not in COMMON_TERMS or args.include_common) for e in r["mentions"]))
    print(f"检测完成：{len(md_files)} 个笔记，实体词表 {entities_total} 个")
    print(f"  首次提及未链接文件: {n_viol}")
    print(f"报告已输出：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
