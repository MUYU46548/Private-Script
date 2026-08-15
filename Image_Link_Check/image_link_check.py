#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian 图片引用断链检测脚本
适用：检测笔记引用了不存在的图片/附件文件。
与 Attachment_Audit 互补：它查"文件存在但没被引用"（孤立），本脚本查"引用但文件不存在"（断链）。
检测：
  1. Wikilink 嵌入：![[xxx.png]]
  2. Markdown 图片：![](路径)
安全：只读检测，不修改任何文件。
用法：python image_link_check.py [--vault ...] [--output ...] [--include-inbox] [--include-templates]
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
REPORT_PATH = "96 事务管理/图片引用断链报告.md"
EXCLUDED_DIRS = {".obsidian", ".git", ".trash", "10_Inbox", "99 模板", ".sitian", "96 事务管理", ".agent_context", "Obsidian_AI_Sandbox"}
# 附件扩展名（判断一个链接目标是否为文件引用）
ATTACHMENT_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico",
    ".pdf", ".mp3", ".mp4", ".wav", ".ogg", ".m4a", ".flac", ".mov", ".avi",
    ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}
WIKI_EMBED_RE = re.compile(r"!\[\[([^\[\]]+)\]\]")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


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


def is_attachment(name: str) -> bool:
    return Path(name).suffix.lower() in ATTACHMENT_EXTS


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian 图片引用断链检测（只读，输出报告）")
    parser.add_argument("--vault", default=VAULT_PATH, help="知识库根目录")
    parser.add_argument("--output", default=None, help="报告输出路径（默认 96 事务管理/图片引用断链报告.md）")
    parser.add_argument("--include-inbox", action="store_true", help="包含 10_Inbox 沙盒草稿")
    parser.add_argument("--include-templates", action="store_true", help="包含 99 模板目录")
    parser.add_argument("--quiet", action="store_true", help="精简控制台输出")
    return parser.parse_args()


def main():
    args = parse_args()
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"执行失败。脚本：image_link_check.py；错误类型：目录不存在；建议操作：检查 --vault 路径")
        return 1

    excluded = set(EXCLUDED_DIRS)
    if args.include_inbox:
        excluded.discard("10_Inbox")
    if args.include_templates:
        excluded.discard("99 模板")

    import os
    # 1. 收集全库附件文件（name -> set(路径)）
    attachments = defaultdict(set)
    md_files = []
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        for fn in filenames:
            p = Path(dirpath) / fn
            if fn.lower().endswith(".md"):
                md_files.append(p)
            elif is_attachment(fn):
                attachments[fn].add(str(p))

    # 2. 提取图片引用并校验
    missing = defaultdict(lambda: {"count": 0, "sources": []})  # 图片名 -> {count, sources}
    for f in md_files:
        text = read_text_safe(f)
        refs = []
        for m in WIKI_EMBED_RE.finditer(text):
            refs.append(m.group(1).strip())
        for m in MD_IMAGE_RE.finditer(text):
            refs.append(m.group(1).strip())
        for ref in refs:
            if not ref or ref.startswith(("http://", "https://")):
                continue
            # 去掉 wikilink 的别名/锚点部分
            base = ref.split("|", 1)[0].split("#", 1)[0].strip()
            if not is_attachment(base):
                continue
            fname = Path(base.replace("\\", "/")).name
            # 判断存在：库中同名文件存在即视为 OK（Obsidian 最短路径解析）
            if fname in attachments:
                continue
            # markdown 相对路径：相对笔记所在目录解析
            if not ref.startswith("[["):
                cand = f.parent / base
                if cand.exists():
                    continue
                cand2 = vault / base
                if cand2.exists():
                    continue
            missing[fname]["count"] += 1
            if len(missing[fname]["sources"]) < 5:
                missing[fname]["sources"].append(f.name)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# 🖼️ Obsidian 图片引用断链报告\n")
    lines.append(f"> **生成时间**：{now}")
    lines.append(f"> **模式**：只读（未修改任何文件）")
    lines.append(f"> **库路径**：`{vault}`")
    lines.append("")
    lines.append("## 1️⃣ 总览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:---|---:|")
    lines.append(f"| 扫描笔记数 | {len(md_files)} |")
    lines.append(f"| 附件文件数（库内） | {len(attachments)} |")
    lines.append(f"| 缺失附件数（引用但不存在） | {len(missing)} |")
    lines.append("")
    lines.append("## 2️⃣ 缺失附件清单（按引用次数排序）\n")
    if not missing:
        lines.append("✅ 未发现缺失附件。\n")
    else:
        lines.append(f"共 **{len(missing)}** 个附件被引用但库中不存在：\n")
        lines.append("| 缺失文件 | 引用次数 | 引用来源（前5） | 级别 |")
        lines.append("|:---|:---:|:---|:---:|")
        for name in sorted(missing, key=lambda n: (-missing[n]["count"], n)):
            lv = "🔴" if missing[name]["count"] >= 2 else "🟢"
            srcs = "、".join(f"`{s}`" for s in missing[name]["sources"])
            lines.append(f"| `{name}` | {missing[name]['count']} | {srcs} | {lv} |")
        lines.append("")
    lines.append("## 3️⃣ 汇总行动建议\n")
    lines.append("| 级别 | 行动 | 数量 |")
    lines.append("|:---|:---|:---:|")
    n_high = sum(1 for n in missing if missing[n]["count"] >= 2)
    lines.append(f"| 🔴 高 | 找回/补放附件（被引用≥2次） | {n_high} |")
    lines.append(f"| 🟢 低 | 核对单次引用 | {len(missing) - n_high} |")
    lines.append("")
    lines.append("> 注：wikilink 嵌入按文件名匹配（Obsidian 最短路径解析）；同名文件存在即视为 OK。\n")

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = vault / REPORT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"检测完成：{len(md_files)} 个笔记，附件 {len(attachments)} 个，缺失 {len(missing)} 个")
    print(f"报告已输出：{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
