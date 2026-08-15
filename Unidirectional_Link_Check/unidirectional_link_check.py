#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian 单向链接检测脚本
适用：全库 Markdown 链接健康度维护。
功能：
  1. 检测单向链接：A 链向 B，但 B 未链回 A → 提示补充反向链接
  2. 检测断链（待创建页）：A 链向 B，但 B 页面不存在 → 提示创建对应页面
  3. 支持筛选：默认排除模板目录/沙盒草稿/索引导航页，可 CLI 覆盖
安全：只读检测，不修改任何文件；输出 Markdown 报告到 96 事务管理/。
用法：python unidirectional_link_check.py [--vault ...] [--output ...] [--min-links N]
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
REPORT_PATH = "96 事务管理/单向链接检测报告.md"
# 逗号陷阱警告：集合元素间必须有逗号！
EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "10_Inbox", "99 模板", ".sitian", "98 附件", "96 事务管理", ".agent_context", "Obsidian_AI_Sandbox"}
# 索引/导航类文件名（作为链接发起方时豁免；作为目标时也不要求反向链接）
INDEX_NAME_MARKERS = ("索引", "目录", "Index", "index", "README", "帮助", "导航", "主页", "Home")


# =========================================================
# 编码回退链（ROSA 实测：UTF-8 为主，部分源文件为 UTF-16-LE）
# =========================================================
def read_text_safe(path: Path) -> str:
    """按编码回退链读取文本文件，全部失败则返回空串。"""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16-le", "gbk", "gb18030"):
        try:
            text = raw.decode(enc)
            # utf-16-le 对 ASCII 也能解码（含 NUL），需校验中文含量
            if enc == "utf-16-le" and not re.search(r"[\u4e00-\u9fff]", text):
                continue
            return text
        except (UnicodeDecodeError, ValueError):
            continue
    return ""


# =========================================================
# Wikilink 提取与规范化
# =========================================================
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

def extract_wikilinks(text: str) -> list:
    """提取所有 [[...]] 原始内容（含嵌入 ![[...]]，忽略别名/锚点/块引用）"""
    out = []
    for m in WIKILINK_RE.finditer(text):
        raw = m.group(1).strip()
        if not raw:
            continue
        # 去掉别名部分 [[目标|显示名]]
        target = raw.split("|", 1)[0].strip()
        # 去掉标题锚点 [[目标#锚点]] 与块引用 [[目标^块]]
        target = re.split(r"[#^]", target, 1)[0].strip()
        # 去掉路径前缀（取最后一段文件名）
        target = target.replace("\\", "/").split("/")[-1].strip()
        if target:
            out.append(target)
    return out


def is_index_page(path: Path) -> bool:
    """判断是否为索引/导航类页面（不需要被反向链接）"""
    return any(marker in path.stem for marker in INDEX_NAME_MARKERS)


# =========================================================
# 链接图构建
# =========================================================
def collect_md_files(vault: Path, excluded_dirs: set) -> list:
    """遍历库收集 .md 文件（os.walk 以支持动态排除目录）"""
    import os
    files = []
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
        for fn in filenames:
            if fn.lower().endswith(".md"):
                files.append(Path(dirpath) / fn)
    return files


def build_link_graph(md_files: list) -> dict:
    """
    构建链接图。
    返回 {node_stem: {"path": Path, "out": set(stems), "in": set(stems)}}
    node_stem 为文件名（不含扩展名），重名文件以最后一个为准并记录到 warnings。
    """
    graph = {}
    dup_warnings = defaultdict(list)
    for f in md_files:
        stem = f.stem
        if stem in graph:
            dup_warnings[stem].append(str(graph[stem]["path"]))
            dup_warnings[stem].append(str(f))
        graph.setdefault(stem, {"path": f, "out": set(), "in": set()})
    for f in md_files:
        text = read_text_safe(f)
        targets = extract_wikilinks(text)
        stem = f.stem
        for t in targets:
            if t == stem:
                continue  # 自链接忽略
            graph[stem]["out"].add(t)
            if t in graph:
                graph[t]["in"].add(stem)
    return graph, dup_warnings


# =========================================================
# 单向链接 / 断链检测
# =========================================================
def analyze(graph: dict, min_links: int, index_markers: tuple):
    """
    返回 (unidirectional, broken)
    unidirectional: list of (source, target) —— source 链向 target 但 target 未链回
    broken: dict target -> set(source) —— 目标页不存在
    筛选规则：
      - 索引/导航页发起的链接豁免（导航不算内容引用）
      - 索引/导航页作为目标时豁免（不需要反向链接）
      - 目标页不存在的链接单独归入 broken（需创建页面）
    """
    unidirectional = []
    broken = defaultdict(set)
    for src, info in graph.items():
        if is_index_page(info["path"]):
            continue  # 索引页发出的导航链接豁免
        for tgt in info["out"]:
            if tgt not in graph:
                broken[tgt].add(src)
                continue
            tgt_info = graph[tgt]
            if is_index_page(tgt_info["path"]):
                continue  # 目标为索引页，不要求反向链接
            if src not in tgt_info["out"]:
                unidirectional.append((src, tgt))
    return unidirectional, broken


# =========================================================
# 报告生成
# =========================================================
def severity(uni_count: int, in_count: int) -> str:
    """分级：🔴 高（目标页入链多却缺反向链接）/ 🟡 中 / 🟢 低"""
    if in_count >= 5 and uni_count >= 1:
        return "🔴"
    if uni_count >= 3:
        return "🟡"
    return "🟢"


def generate_report(vault: Path, graph: dict, unidirectional: list, broken: dict,
                    min_links: int, excluded_dirs: set) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 按目标聚合单向链接
    by_target = defaultdict(list)
    for src, tgt in unidirectional:
        by_target[tgt].append(src)

    lines = []
    lines.append("# 📎 Obsidian 单向链接检测报告\n")
    lines.append(f"> **生成时间**：{now}")
    lines.append(f"> **模式**：只读（未修改任何文件）")
    lines.append(f"> **库路径**：`{vault}`")
    lines.append("")

    # ---- 1. 总览 ----
    lines.append("## 1️⃣ 总览\n")
    total_links = sum(len(g["out"]) for g in graph.values())
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|---:|")
    lines.append(f"| 参与检测的笔记数 | {len(graph)} |")
    lines.append(f"| 出链总数 | {total_links} |")
    lines.append(f"| 单向链接对（需补反向链接） | {len(unidirectional)} |")
    lines.append(f"| 断链目标（页面不存在，需创建） | {len(broken)} |")
    lines.append("")

    # ---- 2. 单向链接明细 ----
    lines.append("## 2️⃣ 单向链接明细（需补充反向链接）\n")
    if not by_target:
        lines.append("✅ 未发现单向链接。\n")
    else:
        lines.append(f"共 **{len(by_target)}** 个目标页面缺少反向链接（每条记录：目标页 → 应链回它的来源页）。\n")
        lines.append("| 目标页 | 单向链接数 | 总入链数 | 缺失反向链接来源（前5） | 级别 |")
        lines.append("|:---|:---:|:---:|:---|:---:|")
        for tgt in sorted(by_target, key=lambda t: (-len(by_target[t]), t)):
            srcs = sorted(by_target[tgt])
            in_total = len(graph[tgt]["in"]) if tgt in graph else 0
            lv = severity(len(srcs), in_total)
            shown = "、".join(f"`{s}`" for s in srcs[:5])
            if len(srcs) > 5:
                shown += f" 等 {len(srcs)} 个"
            lines.append(f"| `{tgt}` | {len(srcs)} | {in_total} | {shown} | {lv} |")
        lines.append("")

    # ---- 3. 断链清单（需创建页面） ----
    lines.append("## 3️⃣ 断链清单（页面不存在，需创建）\n")
    if not broken:
        lines.append("✅ 未发现断链。\n")
    else:
        lines.append("以下链接目标在库中不存在，被引用 **≥ 2 次** 的建议优先创建对应页面。\n")
        lines.append("| 待创建页面 | 被引用次数 | 引用来源（前3） |")
        lines.append("|:---|:---:|:---|")
        for tgt in sorted(broken, key=lambda t: (-len(broken[t]), t)):
            if len(broken[tgt]) < 2:
                continue
            srcs = sorted(broken[tgt])[:3]
            shown = "、".join(f"`{s}`" for s in srcs)
            if len(broken[tgt]) > 3:
                shown += f" 等 {len(broken[tgt])} 个"
            lines.append(f"| `{tgt}` | {len(broken[tgt])} | {shown} |")
        lines.append("")
        single = {t: s for t, s in broken.items() if len(s) < 2}
        if single:
            lines.append(f"另有 **{len(single)}** 个仅被引用 1 次的待创建页（见附录A）。\n")

    # ---- 4. 排除说明 ----
    lines.append("## 4️⃣ 筛选说明\n")
    lines.append(f"- 排除目录：`{'`、`'.join(sorted(excluded_dirs))}`")
    lines.append(f"- 索引/导航类页面（文件名含 `{'`、`'.join(INDEX_NAME_MARKERS)}`）发起的链接豁免；作为目标时不要求反向链接")
    lines.append(f"- 自链接、指向附件的链接不计入")
    lines.append("")

    # ---- 5. 汇总行动建议 ----
    lines.append("## 5️⃣ 汇总行动建议\n")
    lines.append("| 级别 | 行动 | 数量 |")
    lines.append("|:---|:---|:---:|")
    red = sum(1 for t in by_target if severity(len(by_target[t]), len(graph[t]["in"]) if t in graph else 0) == "🔴")
    yellow = sum(1 for t in by_target if severity(len(by_target[t]), len(graph[t]["in"]) if t in graph else 0) == "🟡")
    high_broken = sum(1 for t in broken if len(broken[t]) >= 2)
    lines.append(f"| 🔴 高 | 优先补充反向链接（目标页入链多却单向） | {red} |")
    lines.append(f"| 🟡 中 | 补充反向链接或双向化 | {yellow} |")
    lines.append(f"| 🔴 高 | 创建缺失页面（被引用≥2次） | {high_broken} |")
    lines.append(f"| 🟢 低 | 其余单向链接按需处理 | {max(len(by_target) - red - yellow, 0)} |")
    lines.append("")

    # ---- 附录A：单次引用断链 ----
    if single:
        lines.append("## 附录A：仅引用 1 次的待创建页\n")
        lines.append("| 待创建页面 | 引用来源 |")
        lines.append("|:---|:---|")
        for tgt in sorted(single):
            lines.append(f"| `{tgt}` | `{sorted(single[tgt])[0]}` |")
        lines.append("")
    return "\n".join(lines)


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian 单向链接检测（只读，输出报告）")
    parser.add_argument("--vault", default=VAULT_PATH, help="知识库根目录")
    parser.add_argument("--output", default=None, help="报告输出路径（默认 96 事务管理/单向链接检测报告.md）")
    parser.add_argument("--min-links", type=int, default=1, help="文件最小单向链接数（预留，当前聚合维度为目标页）")
    parser.add_argument("--include-inbox", action="store_true", help="包含 10_Inbox 沙盒草稿")
    parser.add_argument("--include-templates", action="store_true", help="包含 99 模板目录")
    parser.add_argument("--quiet", action="store_true", help="无问题时精简控制台输出")
    return parser.parse_args()


def main():
    args = parse_args()
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"执行失败。脚本：unidirectional_link_check.py；错误类型：目录不存在；建议操作：检查 --vault 路径")
        return 1

    excluded = set(EXCLUDED_DIRS)
    if args.include_inbox:
        excluded.discard("10_Inbox")
    if args.include_templates:
        excluded.discard("99 模板")

    md_files = collect_md_files(vault, excluded)
    graph, dup_warnings = build_link_graph(md_files)
    unidirectional, broken = analyze(graph, args.min_links, INDEX_NAME_MARKERS)

    report = generate_report(vault, graph, unidirectional, broken, args.min_links, excluded)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = vault / REPORT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    # 控制台摘要
    total_links = sum(len(g["out"]) for g in graph.values())
    print(f"检测完成：{len(md_files)} 个笔记，{total_links} 条出链")
    print(f"  单向链接对: {len(unidirectional)}（{len({t for _, t in unidirectional})} 个目标页缺反向链接）")
    print(f"  断链(需创建): {len(broken)}")
    if dup_warnings and not args.quiet:
        print(f"  ⚠️ 重名文件 {len(dup_warnings)} 组：{', '.join(list(dup_warnings)[:5])}")
    print(f"报告已输出：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
