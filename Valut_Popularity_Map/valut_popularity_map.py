# Obsidian 全库热度地图（增强版 v2）
# 改进：修复逗号遗漏bug、可配置阈值、汇总统计、CLI参数、文件排除增强

import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =========================================================
# 默认配置
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"

# 需要排除的文件夹名称
EXCLUDED_DIRS = {
    "00 主面板",
    "01 索引",
    "02 帮助",
    "07 资料收藏",
    "96 事务管理",
    "97 旧资料存档",
    "98 附件",
    "99 模板",
    "指令集",
    "附件",
    "Obsidian_AI_Sandbox",
    "Excalidraw",
    ".obsidian",
    ".trash",
}

# 排除文件名包含这些关键词的文件
EXCLUDE_NAME_PATTERNS = ["MOC", "索引", "目录", "TOC", "Home", "主页", "消歧义", "重定向"]

# 热度分层阈值（可通过CLI覆盖）
HEAT_TIER_HUB = 10
HEAT_TIER_IMPORTANT = 3

# 去重规则
DEDUP_BY_PARENT_FOLDER = True

# 输出报告路径
OUTPUT_PATH = "96 事务管理/库热度地图.md"

# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian全库热度地图")
    parser.add_argument("--vault", default=VAULT_PATH, help="Obsidian库路径")
    parser.add_argument("--output", default=OUTPUT_PATH, help="报告输出相对路径")
    parser.add_argument("--hub-threshold", type=int, default=HEAT_TIER_HUB, help="核心枢纽阈值")
    parser.add_argument("--important-threshold", type=int, default=HEAT_TIER_IMPORTANT, help="重要节点阈值")
    parser.add_argument("--no-dedup", action="store_true", help="关闭按父文件夹去重")
    parser.add_argument("--exclude-dir", action="append", default=[], help="额外排除的文件夹名")
    parser.add_argument("--hot-days", type=int, default=3, help="滚烫天数阈值")
    parser.add_argument("--warm-days", type=int, default=7, help="温热天数阈值")
    parser.add_argument("--cool-days", type=int, default=30, help="微凉天数阈值")
    return parser.parse_args()

def get_temp_tag(days, args):
    """根据天数返回温度标记"""
    if days <= args.hot_days:
        return "🔥 滚烫"
    elif days <= args.warm_days:
        return "☀️ 温热"
    elif days <= args.cool_days:
        return "🌤️ 微凉"
    else:
        return "❄️ 冻结"

def get_level_tag(heat, args):
    """根据热度返回节点标记"""
    if heat >= args.hub_threshold:
        return "🔗 核心枢纽"
    elif heat >= args.important_threshold:
        return "📌 重要节点"
    else:
        return "📄 普通节点"

def get_suggestion(heat, days, args):
    """根据组合逻辑返回建议"""
    if heat >= args.hub_threshold and days > args.cool_days:
        return "⚠️ 核心冻结！立即审视"
    elif heat >= args.hub_threshold and days <= args.warm_days:
        return "⭐ 高优审阅，保持同步"
    elif heat >= args.important_threshold and days <= args.hot_days:
        return "📈 内容活跃，关注关联"
    elif heat < args.important_threshold and days <= args.hot_days:
        return "🌱 新芽待哺，可丰富链接"
    else:
        return "🗂️ 按需维护"

# ---------------------------------------------------------
# 主流程
# ---------------------------------------------------------
args = parse_args()

vault_root = Path(args.vault)
excluded_dirs = set(EXCLUDED_DIRS) | set(args.exclude_dir)
dedup_by_parent = not args.no_dedup

print("📊 正在扫描全库...")
all_md_files = list(vault_root.rglob("*.md"))
print(f"   原始文件数: {len(all_md_files)}")

# 1. 过滤
target_files = []
for f in all_md_files:
    parts = f.parts
    if any(excl in parts for excl in excluded_dirs):
        continue
    if any(keyword in f.stem for keyword in EXCLUDE_NAME_PATTERNS):
        continue
    target_files.append(f)

print(f"   过滤后文件数: {len(target_files)}")

# 2. 提取有效笔记
note_names = set()
note_path_map = {}
for f in target_files:
    name = f.stem
    note_names.add(name)
    note_path_map[name] = f

# 3. 统计引用热度
ref_map = defaultdict(set)
link_pattern = re.compile(r'\[\[([^|\]]+)(?:\|[^\]]+)?\]\]')

for file_path in target_files:
    try:
        text = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, OSError) as e:
        print(f"  ⚠️ 跳过（读取失败）: {file_path.name} — {e}")
        continue

    matches = link_pattern.findall(text)
    for matched_name in matches:
        if matched_name in note_names:
            if dedup_by_parent:
                ref_map[matched_name].add(file_path.parent.name)
            else:
                ref_map[matched_name].add(str(file_path))

# 4. 计算热度
heat_dict = {name: len(ref_map.get(name, set())) for name in note_names}

# 5. 计算修改天数
now = datetime.now()
days_dict = {}
for name, path in note_path_map.items():
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    days_dict[name] = (now - mtime).days

# 6. 排序
sorted_notes = sorted(heat_dict.items(), key=lambda x: (-x[1], days_dict.get(x[0], 999)))

# 7. 按文件夹分组
grouped_by_folder = defaultdict(list)
for name, heat in sorted_notes:
    parent_path = note_path_map[name].parent
    try:
        folder = str(parent_path.relative_to(vault_root))
    except ValueError:
        folder = "根目录"
    if not folder or folder == ".":
        folder = "根目录"
    grouped_by_folder[folder].append((name, heat))

# 8. 汇总统计
total_notes = len(note_names)
hub_count = sum(1 for _, h in sorted_notes if h >= args.hub_threshold)
important_count = sum(1 for _, h in sorted_notes if args.important_threshold <= h < args.hub_threshold)
normal_count = sum(1 for _, h in sorted_notes if h < args.important_threshold)
hot_count = sum(1 for d in days_dict.values() if d <= args.hot_days)
frozen_count = sum(1 for d in days_dict.values() if d > args.cool_days)
core_frozen_count = sum(1 for name, h in sorted_notes if h >= args.hub_threshold and days_dict.get(name, 999) > args.cool_days)

# 9. 写入报告
output_full_path = vault_root / args.output
output_full_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_full_path, "w", encoding="utf-8") as f:
    # 头部
    f.write(f"# 📊 全库热度地图\n\n")
    f.write(f"> **统计时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"> **扫描笔记总数**：{total_notes} 篇\n")
    f.write(f"> **热度分层**：🔗核心枢纽(≥{args.hub_threshold}次) | 📌重要节点(≥{args.important_threshold}次) | 📄普通节点\n")
    f.write(f"> **温度标记**：🔥滚烫(≤{args.hot_days}天) | ☀️温热(≤{args.warm_days}天) | 🌤️微凉(≤{args.cool_days}天) | ❄️冻结(>{args.cool_days}天)\n")
    f.write(f"> **去重规则**：{'按父文件夹去重' if dedup_by_parent else '按文件去重'}\n")
    f.write(f"> **已排除目录**：{', '.join(sorted(excluded_dirs))}\n\n")

    # 汇总统计面板
    f.write(f"---\n\n## 📈 全局汇总统计\n\n")
    f.write(f"| 指标 | 数值 | 占比 |\n")
    f.write(f"|:---|:---|:---|\n")
    f.write(f"| 🔗 核心枢纽 | {hub_count} 篇 | {hub_count*100//total_notes if total_notes else 0}% |\n")
    f.write(f"| 📌 重要节点 | {important_count} 篇 | {important_count*100//total_notes if total_notes else 0}% |\n")
    f.write(f"| 📄 普通节点 | {normal_count} 篇 | {normal_count*100//total_notes if total_notes else 0}% |\n")
    f.write(f"| 🔥 近期活跃（≤{args.hot_days}天） | {hot_count} 篇 | {hot_count*100//total_notes if total_notes else 0}% |\n")
    f.write(f"| ❄️ 长期冻结（>{args.cool_days}天） | {frozen_count} 篇 | {frozen_count*100//total_notes if total_notes else 0}% |\n")
    f.write(f"| ⚠️ 核心冻结（核心+冻结） | {core_frozen_count} 篇 | — |\n\n")

    # 优先关注区（核心冻结 + 高活跃）
    f.write(f"---\n\n## 🎯 优先关注区\n\n")
    f.write(f"### ⚠️ 核心冻结（需立即审视）\n\n")
    frozen_hubs = [(n, h) for n, h in sorted_notes if h >= args.hub_threshold and days_dict.get(n, 999) > args.cool_days]
    if frozen_hubs:
        for name, heat in frozen_hubs:
            days = days_dict.get(name, 999)
            folder = note_path_map[name].parent
            try:
                rel = str(folder.relative_to(vault_root))
            except ValueError:
                rel = "根目录"
            f.write(f"- **{name}** — 热度 {heat}，{days} 天前修改（`{rel}`）\n")
    else:
        f.write("_暂无_\n")
    f.write(f"\n### 📈 近期活跃（≤{args.hot_days}天）\n\n")
    hot_notes = [(n, h) for n, h in sorted_notes if days_dict.get(n, 999) <= args.hot_days]
    if hot_notes:
        for name, heat in hot_notes:
            days = days_dict.get(name, 999)
            days_display = "<1" if days == 0 else str(days)
            f.write(f"- **{name}** — 热度 {heat}，{days_display} 天前修改\n")
    else:
        f.write("_暂无_\n")

    f.write(f"\n---\n\n")

    # 按文件夹逐个输出
    for folder, items in sorted(grouped_by_folder.items()):
        f.write(f"## 📁 {folder}\n\n")
        f.write("| 笔记名称 | 引用热度 | 最后修改(天前) | 温度状态 | 节点分类 | 建议行动 |\n")
        f.write("|:---|:---|:---|:---|:---|:---|\n")

        for name, heat in items:
            days = days_dict.get(name, 999)
            days_display = "<1" if days == 0 else str(days)
            temp_tag = get_temp_tag(days, args)
            level_tag = get_level_tag(heat, args)
            suggestion = get_suggestion(heat, days, args)
            f.write(f"| {name} | {heat} | {days_display} | {temp_tag} | {level_tag} | {suggestion} |\n")

        f.write("\n")

print(f"\n✅ 全库热度地图已生成: {output_full_path}")
print(f"📝 共统计 {total_notes} 篇笔记，分布在 {len(grouped_by_folder)} 个文件夹")
print(f"   🔗核心枢纽: {hub_count} | 📌重要节点: {important_count} | 📄普通: {normal_count}")
print(f"   🔥活跃: {hot_count} | ❄️冻结: {frozen_count} | ⚠️核心冻结: {core_frozen_count}")
