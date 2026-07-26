#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian 库统计仪表板（只读版）
功能：全库统计汇总 + 可操作的优化建议
保证：除报告文件外，不修改、不删除、不移动任何文件
"""

import os
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# =========================================================
# 默认配置
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"
REPORT_PATH = "96 事务管理/库统计仪表板.md"

# 排除的系统目录
EXCLUDED_DIRS = {
    ".obsidian", ".git", ".trash", "Obsidian_AI_Sandbox",
    ".agent_context",
}

# 支持的附件扩展名
ATTACHMENT_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.svg', '.ico',
    '.tiff', '.heic', '.heif',
    '.mp3', '.mp4', '.mov', '.avi', '.mkv',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.ppt', '.pptx', '.zip', '.rar', '.7z'
}

# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian库统计仪表板（只读）")
    parser.add_argument("--vault", default=VAULT_PATH, help="Obsidian库路径")
    parser.add_argument("--output", default=REPORT_PATH, help="报告输出相对路径")
    return parser.parse_args()


class VaultStats:
    """收集所有统计数据"""

    def __init__(self, vault_path):
        self.vault_path = Path(vault_path)
        self.now = datetime.now()

        # 基础数据
        self.all_files = []
        self.md_files = []
        self.att_files = []
        self.folder_set = set()

        # 内容统计
        self.total_lines = 0
        self.total_words = 0
        self.total_chars = 0
        self.file_sizes = []

        # 标签
        self.tag_count = Counter()
        self.tag_files = defaultdict(set)  # tag -> set of filenames

        # 链接
        self.link_count = Counter()  # target -> count
        self.file_links = defaultdict(list)  # source -> [(target, alias)]
        self.total_links = 0

        # 健康检查
        self.no_frontmatter = []
        self.empty_files = []
        self.tiny_files = []
        self.large_files = []

        # 附件
        self.orphan_attachments = set()

        # 修改时间
        self.modification_timeline = {
            "<7天": 0, "7-30天": 0, "30-90天": 0, "90-365天": 0, ">365天": 0
        }

    def scan(self):
        """扫描全库收集所有数据"""
        print("🔍 正在扫描全库...")

        for f in self.vault_path.rglob("*"):
            if not f.is_file():
                continue

            # 检查排除目录
            parts = f.parts
            if any(excl in parts for excl in EXCLUDED_DIRS):
                continue

            self.all_files.append(f)
            rel = f.relative_to(self.vault_path)
            self.folder_set.add(str(rel.parent))

            # 分类
            if f.suffix.lower() == ".md":
                self.md_files.append(f)
                self._analyze_md(f)
            elif f.suffix.lower() in ATTACHMENT_EXTENSIONS:
                self.att_files.append(f)

        print(f"  ✅ 扫描完成: {len(self.all_files)} 个文件，{len(self.md_files)} 个Markdown")

    def _analyze_md(self, f: Path):
        """分析单个Markdown文件"""
        stat = f.stat()
        size = stat.st_size
        self.file_sizes.append(size)

        # 行数统计
        try:
            content = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError, OSError):
            return

        lines = content.splitlines()
        self.total_lines += len(lines)
        self.total_words += len(content.split())
        self.total_chars += len(content)

        # 修改时间分布
        days = (self.now - datetime.fromtimestamp(stat.st_mtime)).days
        if days <= 7:
            self.modification_timeline["<7天"] += 1
        elif days <= 30:
            self.modification_timeline["7-30天"] += 1
        elif days <= 90:
            self.modification_timeline["30-90天"] += 1
        elif days <= 365:
            self.modification_timeline["90-365天"] += 1
        else:
            self.modification_timeline[">365天"] += 1

        # 健康检查
        if size == 0:
            self.empty_files.append(f)
        elif size < 100:
            self.tiny_files.append(f)

        if len(lines) > 1000:
            self.large_files.append((f, len(lines)))

        # Frontmatter检查
        if not content.startswith("---"):
            self.no_frontmatter.append(f)

        # 标签提取（正文和YAML中的tags字段）
        yaml_tags = self._extract_yaml_tags(content)
        body_tags = re.findall(r'(?<!\w)#([\w\u4e00-\u9fa5][\w\u4e00-\u9fa5/\-\.\+]*)', content)
        all_tags = set(yaml_tags) | {t for t in body_tags if len(t) > 1}

        for tag in all_tags:
            self.tag_count[tag] += 1
            self.tag_files[tag].add(f.stem)

        # 链接提取
        links = re.findall(r'\[\[([^|\]]+)(?:\|([^\]]+))?\]\]', content)
        for target, alias in links:
            target = target.strip()
            self.link_count[target] += 1
            self.total_links += 1
            self.file_links[f.stem].append((target, alias))

    def _extract_yaml_tags(self, content: str) -> list:
        """从YAML frontmatter提取tags"""
        if not content.startswith("---"):
            return []
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not match:
            return []
        yaml_str = match.group(1)
        tags = []
        for line in yaml_str.splitlines():
            if line.startswith("tags:"):
                # tags: [tag1, tag2] 或 tags:\n  - tag1
                tag_str = line[5:].strip()
                if tag_str.startswith("["):
                    tags.extend(t.strip() for t in tag_str[1:-1].split(",") if t.strip())
                elif tag_str:
                    tags.append(tag_str)
            elif line.strip().startswith("- "):
                tag = line.strip()[2:].strip()
                if tag:
                    tags.append(tag)
        return tags

    def get_linked_names(self) -> set:
        """获取所有被链接引用的文件名"""
        names = set()
        for target in self.link_count:
            if (self.vault_path / f"{target}.md").exists():
                names.add(target)
            elif (self.vault_path / target).exists():
                names.add(Path(target).stem)
        return names

    def get_orphaned_notes(self) -> list:
        """获取孤立笔记（无入链且非索引文件）"""
        linked = self.get_linked_names()
        index_names = {"索引", "目录", "TOC", "Home", "主页", "MOC", "index"}
        orphaned = []
        for f in self.md_files:
            stem = f.stem
            if stem not in linked and stem not in index_names:
                # 进一步排除帮助/模板类文件
                rel = str(f.relative_to(self.vault_path))
                if not any(x in rel for x in ["02 帮助", "99 模板", "96 事务"]):
                    orphaned.append(f)
        return orphaned

    def get_broken_links(self) -> dict:
        """获取断链（链接目标不存在）"""
        broken = {}
        for source, links in self.file_links.items():
            for target, alias in links:
                if not (self.vault_path / f"{target}.md").exists() and \
                   not (self.vault_path / target).exists():
                    if source not in broken:
                        broken[source] = []
                    broken[source].append(target)
        return broken


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def bar(value: int, max_value: int, width: int = 20) -> str:
    """生成ASCII进度条"""
    if max_value == 0:
        return "□" * width
    filled = int(value / max_value * width)
    return "█" * filled + "░" * (width - filled)


def generate_report(stats: VaultStats) -> str:
    """生成完整的Markdown报告"""
    vault_path = stats.vault_path
    now = stats.now
    total_files = len(stats.all_files)
    total_md = len(stats.md_files)
    total_att = len(stats.att_files)
    total_size = sum(f.stat().st_size for f in stats.all_files)
    md_size = sum(f.stat().st_size for f in stats.md_files)
    att_size = sum(f.stat().st_size for f in stats.att_files)

    orphaned_notes = stats.get_orphaned_notes()
    broken_links = stats.get_broken_links()
    orphan_att_names = {f.name for f in stats.att_files} - {
        Path(t).name for t in stats.link_count
        if Path(t).name in {f.name for f in stats.att_files}
    }

    lines = []

    # ==================== 头部 ====================
    lines.extend([
        f"# 📊 Obsidian 库统计仪表板",
        f"",
        f"> **生成时间**：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> **库路径**：`{vault_path}`",
        f"> **模式**：只读（未修改任何文件）",
        f"",
        f"---",
        f"",
    ])

    # ==================== 1. 总览 ====================
    lines.extend([
        f"## 1️⃣ 总览",
        f"",
        f"| 指标 | 数值 |",
        f"|:---|:---|",
        f"| 文件总数 | **{total_files:,}** 个 |",
        f"| Markdown 文件 | **{total_md:,}** 个 |",
        f"| 附件文件 | **{total_att:,}** 个 |",
        f"| 文件夹数 | **{len(stats.folder_set):,}** 个 |",
        f"| 总占用空间 | **{format_size(total_size)}** |",
        f"| ├── Markdown | {format_size(md_size)} |",
        f"| └── 附件 | {format_size(att_size)} |",
        f"| 总行数 | **{stats.total_lines:,}** 行 |",
        f"| 总词数 | **{stats.total_words:,}** 词 |",
        f"| 总字符 | **{stats.total_chars:,}** 字符 |",
        f"| 平均每文件行数 | **{stats.total_lines // total_md if total_md else 0}** 行 |",
        f"| 总链接数 | **{stats.total_links:,}** 个 |",
        f"| 唯一链接目标 | **{len(stats.link_count):,}** 个 |",
        f"| 唯一标签 | **{len(stats.tag_count)}** 个 |",
        f"",
    ])

    # ==================== 2. 文件健康度 ====================
    lines.extend([
        f"---",
        f"",
        f"## 2️⃣ 文件健康度",
        f"",
        f"| 检查项 | 数量 | 状态 |",
        f"|:---|:---|:---|",
    ])

    health_items = [
        ("空文件 (0 字节)", len(stats.empty_files), "🔴" if stats.empty_files else "✅"),
        ("极小文件 (<100 字节)", len(stats.tiny_files), "🟡" if stats.tiny_files else "✅"),
        ("缺少 Frontmatter", len(stats.no_frontmatter), "🟡" if stats.no_frontmatter else "✅"),
        ("孤立笔记 (无入链)", len(orphaned_notes), "🟡" if len(orphaned_notes) > total_md * 0.3 else "✅"),
        ("断链", sum(len(v) for v in broken_links.values()), "🔴" if broken_links else "✅"),
        ("大文件 (>1000行)", len(stats.large_files), "🟡" if stats.large_files else "✅"),
    ]

    for name, count, status in health_items:
        lines.append(f"| {name} | {count} | {status} |")

    lines.append("")

    # 孤立笔记详情（仅展示前10个）
    if orphaned_notes:
        lines.extend([
            f"### 孤立笔记示例 (前 10 个)",
            f"",
            f"共发现 **{len(orphaned_notes)}** 个无入链笔记：",
            f"",
        ])
        for f in sorted(orphaned_notes, key=lambda x: x.stat().st_size, reverse=True)[:10]:
            rel = f.relative_to(vault_path)
            lines.append(f"- `{rel}` ({f.stat().st_size} 字节)")
        if len(orphaned_notes) > 10:
            lines.append(f"- ... 共 {len(orphaned_notes)} 个")
        lines.append("")

    # 断链详情
    if broken_links:
        lines.extend([
            f"### 断链详情",
            f"",
            f"共发现 **{len(broken_links)}** 个文件存在断链：",
            f"",
        ])
        for source, targets in sorted(broken_links.items())[:10]:
            lines.append(f"- **{source}** → 缺失: {', '.join(f'`{t}`' for t in targets[:5])}")
        if len(broken_links) > 10:
            lines.append(f"- ... 共 {len(broken_links)} 个文件")
        lines.append("")

    # 大文件详情
    if stats.large_files:
        lines.extend([
            f"### 大文件 (>1000行)",
            f"",
        ])
        for f, line_count in sorted(stats.large_files, key=lambda x: -x[1])[:10]:
            rel = f.relative_to(vault_path)
            lines.append(f"- `{rel}` — {line_count:,} 行, {format_size(f.stat().st_size)}")
        lines.append("")

    # ==================== 3. 标签分析 ====================
    lines.extend([
        f"---",
        f"",
        f"## 3️⃣ 标签分析",
        f"",
        f"唯一标签数：**{len(stats.tag_count)}**",
        f"",
        f"### 使用频率 TOP 20",
        f"",
        f"| 排名 | 标签 | 使用次数 | 使用文件数 | 分布 |",
        f"|:---|:---|:---|:---|:---|",
    ])

    for i, (tag, count) in enumerate(stats.tag_count.most_common(20), 1):
        file_count = len(stats.tag_files[tag])
        distribution = bar(count, stats.tag_count.most_common(1)[0][1] if stats.tag_count else 0, 15)
        lines.append(f"| {i} | `#{tag}` | {count} | {file_count} | {distribution} |")

    lines.append("")

    # ==================== 4. 链接分析 ====================
    lines.extend([
        f"---",
        f"",
        f"## 4️⃣ 链接网络分析",
        f"",
        f"### 被引用最多 TOP 15",
        f"",
        f"| 排名 | 笔记 | 入链数 | 分布 |",
        f"|:---|:---|:---|:---|",
    ])

    for i, (name, count) in enumerate(stats.link_count.most_common(15), 1):
        distribution = bar(count, stats.link_count.most_common(1)[0][1] if stats.link_count else 0, 15)
        exists = "✅" if (vault_path / f"{name}.md").exists() else "❌"
        lines.append(f"| {i} | {exists} `{name}` | {count} | {distribution} |")

    lines.extend(["", "---", "", "---", ""])

    # ==================== 5. 附件分析 ====================
    lines.extend([
        f"---",
        f"",
        f"## 5️⃣ 附件分析",
        f"",
        f"| 指标 | 数值 |",
        f"|:---|:---|",
        f"| 附件总数 | {total_att} |",
        f"| 附件占用空间 | {format_size(att_size)} |",
        f"| 孤立附件 | {len(orphan_att_names)} |",
        f"| 被引用附件 | {total_att - len(orphan_att_names)} |",
        f"",
    ])

    if orphan_att_names:
        lines.extend([
            f"### 孤立附件列表",
            f"",
        ])
        for name in sorted(orphan_att_names)[:20]:
            f_path = vault_path / "98 附件" / name
            size = f_path.stat().st_size if f_path.exists() else 0
            lines.append(f"- `{name}` ({format_size(size)})")
        if len(orphan_att_names) > 20:
            lines.append(f"- ... 共 {len(orphan_att_names)} 个")
        lines.append("")

    # 附件类型分布
    ext_count = Counter()
    for f in stats.att_files:
        ext_count[f.suffix.lower()] += 1

    lines.extend([
        f"### 附件类型分布",
        f"",
        f"| 类型 | 数量 | 占比 |",
        f"|:---|:---|:---|",
    ])
    for ext, count in ext_count.most_common():
        pct = count * 100 // total_att if total_att else 0
        lines.append(f"| `{ext}` | {count} | {pct}% |")
    lines.append("")

    # ==================== 6. 文件夹结构 ====================
    folder_file_count = defaultdict(int)
    folder_size = defaultdict(int)
    for f in stats.all_files:
        rel = f.relative_to(vault_path)
        parent = str(rel.parts[0]) if len(rel.parts) > 1 else "根目录"
        folder_file_count[parent] += 1
        folder_size[parent] += f.stat().st_size

    lines.extend([
        f"---",
        f"",
        f"## 6️⃣ 文件夹结构",
        f"",
        f"### TOP 15 文件夹（按文件数）",
        f"",
        f"| 文件夹 | 文件数 | 占用空间 |",
        f"|:---|:---|:---|",
    ])
    for folder, count in sorted(folder_file_count.items(), key=lambda x: -x[1])[:15]:
        lines.append(f"| `{folder}` | {count} | {format_size(folder_size[folder])} |")
    lines.append("")

    # ==================== 7. 修改时间线 ====================
    lines.extend([
        f"---",
        f"",
        f"## 7️⃣ 修改时间分布",
        f"",
        f"| 时间段 | 文件数 | 分布 |",
        f"|:---|:---|:---|",
    ])
    max_mod = max(stats.modification_timeline.values()) if stats.modification_timeline else 1
    for period, count in stats.modification_timeline.items():
        distribution = bar(count, max_mod, 20)
        lines.append(f"| {period} | {count} | {distribution} |")
    lines.append("")

    # ==================== 8. 优化建议 ====================
    lines.extend([
        f"---",
        f"",
        f"## 8️⃣ 优化建议",
        f"",
        f"基于以上分析，以下是可操作的优化建议，按优先级排序：",
        f"",
    ])

    suggestion_id = 0

    # 🔴 高优先级
    high_priority = []
    if stats.empty_files:
        suggestion_id += 1
        high_priority.append(
            f"**[{suggestion_id}] 清理空文件**：{len(stats.empty_files)} 个文件内容为空，"
            f"建议删除或填充内容。"
        )
    if broken_links:
        suggestion_id += 1
        high_priority.append(
            f"**[{suggestion_id}] 修复断链**：{len(broken_links)} 个文件包含 {sum(len(v) for v in broken_links.values())} 个断链，"
            f"建议手动确认后修复或移除。"
        )
    if orphan_att_names:
        suggestion_id += 1
        high_priority.append(
            f"**[{suggestion_id}] 清理孤立附件**：{len(orphan_att_names)} 个附件未被任何笔记引用，"
            f"可考虑移动到回收站。"
        )

    if high_priority:
        lines.append(f"### 🔴 高优先级")
        lines.append("")
        for s in high_priority:
            lines.append(f"- {s}")
        lines.append("")

    # 🟡 中优先级
    mid_priority = []
    if stats.no_frontmatter:
        suggestion_id += 1
        mid_priority.append(
            f"**[{suggestion_id}] 补充 Frontmatter**：{len(stats.no_frontmatter)} 个文件缺少 YAML frontmatter，"
            f"建议补充 `tags`、`publish` 等字段。"
        )
    if len(orphaned_notes) > total_md * 0.3:
        suggestion_id += 1
        mid_priority.append(
            f"**[{suggestion_id}] 优化链接结构**：{len(orphaned_notes)} 个笔记无任何入链（占总数 {len(orphaned_notes)*100//total_md}%），"
            f"建议为关键笔记添加相关链接或使用 MOC 组织。"
        )
    if stats.tiny_files:
        suggestion_id += 1
        mid_priority.append(
            f"**[{suggestion_id}] 检查极小文件**：{len(stats.tiny_files)} 个文件小于 100 字节，"
            f"可能是占位符或草稿，建议确认是否需要保留。"
        )

    if mid_priority:
        lines.append(f"### 🟡 中优先级")
        lines.append("")
        for s in mid_priority:
            lines.append(f"- {s}")
        lines.append("")

    # 🟢 低优先级
    low_priority = []
    if stats.large_files:
        suggestion_id += 1
        low_priority.append(
            f"**[{suggestion_id}] 拆分大文件**：{len(stats.large_files)} 个文件超过 1000 行，"
            f"最大为 {stats.large_files[0][1]:,} 行，建议拆分为多个笔记并配合 MOC 管理。"
        )

    if len(stats.tag_count) > 50:
        # 检查是否有低使用频率标签
        low_freq_tags = [t for t, c in stats.tag_count.items() if c == 1]
        if low_freq_tags:
            suggestion_id += 1
            low_priority.append(
                f"**[{suggestion_id}] 清理低频标签**：{len(low_freq_tags)} 个标签仅使用 1 次，"
                f"建议合并或删除。"
            )

    if low_priority:
        lines.append(f"### 🟢 低优先级")
        lines.append("")
        for s in low_priority:
            lines.append(f"- {s}")
        lines.append("")

    # 通用建议
    lines.extend([
        f"### 💡 通用建议",
        f"",
        f"- **建立 MOC 体系**：为每个主题领域创建 Map of Content 索引页，提升笔记可发现性",
        f"- **规范标签体系**：建立同义词映射，避免 `#角色` / `#人物` 等重复标签",
        f"- **定期巡检**：建议每周运行一次仪表板，监控库健康状态变化",
        f"- **链接优先**：新建笔记时至少添加 3 个相关链接，防止产生新的孤立笔记",
        f"",
    ])

    # ==================== 尾部 ====================
    lines.extend([
        f"---",
        f"",
        f"*报告由 Obsidian 库统计仪表板自动生成*",
        f"*生成耗时: {(datetime.now() - now).total_seconds():.2f} 秒*",
    ])

    return "\n".join(lines)


def main():
    args = parse_args()
    vault_path = Path(args.vault)

    if not vault_path.exists():
        print(f"❌ 库路径不存在: {vault_path}")
        return

    print("=" * 60)
    print("  📊 Obsidian 库统计仪表板")
    print("  🔒 只读模式（不会修改任何文件）")
    print("=" * 60)

    # 收集数据
    stats = VaultStats(vault_path)
    stats.scan()

    # 生成报告
    print("\n📝 正在生成报告...")
    report_content = generate_report(stats)

    # 写入报告
    output_path = vault_path / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content, encoding="utf-8")

    print(f"\n✅ 报告已保存: {output_path}")
    print(f"📊 共分析 {len(stats.all_files)} 个文件，耗时 {((datetime.now() - stats.now).total_seconds()):.2f} 秒")

    # 简要摘要
    orphaned = stats.get_orphaned_notes()
    broken = stats.get_broken_links()
    print(f"\n快速摘要:")
    print(f"  文件总数: {len(stats.all_files)}")
    print(f"  孤立笔记: {len(orphaned)}")
    print(f"  断链: {sum(len(v) for v in broken.values())}")
    print(f"  空文件: {len(stats.empty_files)}")
    print(f"  缺少Frontmatter: {len(stats.no_frontmatter)}")


if __name__ == "__main__":
    main()
