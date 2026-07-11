"""
这是一个专用于Obsidian库的库热度地图脚本
全库通用版
不依赖Agent
节约Token
"""

import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =========================================================
# 配置区（请根据你的实际情况修改）
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"   # 你的库绝对路径

# 需要排除的文件夹名称（这些不参与统计，也不作为引用源）
# 必须依据库的实际情况设置！
EXCLUDED_DIRS = {
    "00 主面板",        # 门户界面，高度功能化
    "01 索引",          # 索引专区
    "02 帮助",          # 帮助文档与编写规范
    "07 资料收藏",      # 存放文献，通常放入就再也无需更新
    "96 事务管理",      # 存放日志、基线等
    "97 旧资料存档",    # 归档文献
    "98 附件",          # 附件文件，通常为图片
    "99 模板",          # 模板文件
    "指令集",           # 存放Agent指令
    "附件",             # 图片、PDF等
    "Obsidian_AI_Sandbox"  #AI 插件调试区域
    "Excalidraw",     # 画板文件
    ".obsidian",      # 插件配置
    ".trash",         # 回收站
}

# 排除文件名包含这些关键词的文件（过滤索引页/目录页，避免虚假热度）
EXCLUDE_NAME_PATTERNS = ["MOC", "索引", "目录", "TOC", "Home","主页","消歧义","重定向"]

# ----- 固定热度分层阈值（根据你的库结构调整）-----
# 被引用 >= 10次：视为核心枢纽（战略要地）
HEAT_TIER_HUB = 10
# 被引用 >= 3次 且 < 10次：视为重要节点
HEAT_TIER_IMPORTANT = 3
# 低于 3 次：普通/边缘节点
# -------------------------------------------------

# 是否按【父文件夹】去重引用源（True=同一文件夹下的多篇文章引用只算1次）
DEDUP_BY_PARENT_FOLDER = True

# 输出报告路径（相对于库根目录）
OUTPUT_PATH = "96 事务管理/库热度地图.md"
# =========================================================

vault_root = Path(VAULT_PATH)
all_md_files = list(vault_root.rglob("*.md"))

# 1. 过滤掉被排除的文件夹 + 文件名关键词
target_files = []
for f in all_md_files:
    parts = f.parts
    if any(excl in parts for excl in EXCLUDED_DIRS):
        continue
    if any(keyword in f.stem for keyword in EXCLUDE_NAME_PATTERNS):
        continue
    target_files.append(f)

# 2. 提取所有有效笔记名称及路径映射
note_names = set()
note_path_map = {}
for f in target_files:
    name = f.stem
    note_names.add(name)
    note_path_map[name] = f

# 3. 统计引用热度（全库互相引用，按父文件夹去重）
ref_map = defaultdict(set)
link_pattern = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')

for file_path in target_files:
    try:
        text = file_path.read_text(encoding="utf-8")
    except:
        continue
    
    matches = link_pattern.findall(text)
    for matched_name in matches:
        if matched_name in note_names:
            if DEDUP_BY_PARENT_FOLDER:
                # 去重维度：引用源所在的【父文件夹名称】
                ref_map[matched_name].add(file_path.parent.name)
            else:
                ref_map[matched_name].add(str(file_path))

# 4. 计算每个笔记的热度值
heat_dict = {}
for name in note_names:
    heat_dict[name] = len(ref_map.get(name, set()))

# 5. 计算“距上次修改的天数”（取代二元的活跃/沉寂）
now = datetime.now()
days_dict = {}
for name, path in note_path_map.items():
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    days_dict[name] = (now - mtime).days

# 6. 对所有笔记按热度降序 + 按天数升序排序（热度优先）
sorted_notes = sorted(heat_dict.items(), key=lambda x: (-x[1], days_dict.get(x[0], 999)))

# 7. 按完整文件夹路径分组（保留层级）
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

# 8. 写入报告
output_full_path = vault_root / OUTPUT_PATH
output_full_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_full_path, "w", encoding="utf-8") as f:
    f.write(f"# 📊 全库热度地图（最终版）\n\n")
    f.write(f"> **统计时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"> **扫描笔记总数**：{len(note_names)}\n")
    f.write(f"> **热度分层**：🔗核心枢纽(≥{HEAT_TIER_HUB}次) | 📌重要节点(≥{HEAT_TIER_IMPORTANT}次) | 📄普通节点\n")
    f.write(f"> **温度标记**：🔥滚烫(≤3天) | ☀️温热(≤7天) | 🌤️微凉(≤30天) | ❄️冻结(>30天)\n")
    f.write(f"> **去重规则**：{'按父文件夹去重' if DEDUP_BY_PARENT_FOLDER else '按文件去重'}\n")
    f.write(f"> **已排除目录**：{', '.join(EXCLUDED_DIRS)}\n\n")
    
    # 按文件夹逐个输出（保留完整层级）
    for folder, items in sorted(grouped_by_folder.items()):
        # 文件夹路径作为二级标题
        f.write(f"## 📁 {folder}\n\n")
        f.write("| 笔记名称 | 引用热度 | 最后修改(天前) | 温度状态 | 节点分类 | 建议行动 |\n")
        f.write("|:---|:---|:---|:---|:---|:---|\n")
        
        for name, heat in items:
            days = days_dict.get(name, 999)
            
            # ---- 温度状态（基于具体天数） ----
            if days <= 3:
                temp_tag = "🔥 滚烫"
            elif days <= 7:
                temp_tag = "☀️ 温热"
            elif days <= 30:
                temp_tag = "🌤️ 微凉"
            else:
                temp_tag = "❄️ 冻结"
            
            # ---- 节点分类（固定阈值） ----
            if heat >= HEAT_TIER_HUB:
                level_tag = "🔗 核心枢纽"
            elif heat >= HEAT_TIER_IMPORTANT:
                level_tag = "📌 重要节点"
            else:
                level_tag = "📄 普通节点"
            
            # ---- 建议行动（根据组合逻辑） ----
            if heat >= HEAT_TIER_HUB and days > 30:
                suggestion = "⚠️ 核心冻结！立即审视"
            elif heat >= HEAT_TIER_HUB and days <= 7:
                suggestion = "⭐ 高优审阅，保持同步"
            elif heat >= HEAT_TIER_IMPORTANT and days <= 3:
                suggestion = "📈 内容活跃，关注关联"
            elif heat < HEAT_TIER_IMPORTANT and days <= 3:
                suggestion = "🌱 新芽待哺，可丰富链接"
            else:
                suggestion = "🗂️ 按需维护"
            
            # 显示天数，如果是当天修改的显示为"<1"
            days_display = "<1" if days == 0 else str(days)
            f.write(f"| {name} | {heat} | {days_display} | {temp_tag} | {level_tag} | {suggestion} |\n")
        
        f.write("\n")  # 文件夹间空一行

print(f"✅ 全库热度地图已生成：{output_full_path}")
print(f"📝 共统计 {len(note_names)} 篇笔记，分布在 {len(grouped_by_folder)} 个文件夹中。")
print(f"💡 提示：重点关注「核心冻结」(🔗+❄️) 条目，这是高价值但可能过时的知识。")
