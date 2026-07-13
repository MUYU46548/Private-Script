# Obsidian模板兼容性检测

import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =========================================================
# 配置区（请根据你的实际情况修改）
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"   # 你的库绝对路径

# 指定要检测的标题级别（1=#，2=##，3=###）
HEADER_LEVEL = 1   # 如果大部分是一级标题，这里改为 1

# ----- 核心映射配置（多模板 ↔ 多文件夹）-----
# 格式： "模板文件的相对路径" : ["目标文件夹1", "目标文件夹2", ...]
# 脚本会依次用每个模板去检查其对应的文件夹列表
TEMPLATE_TARGET_MAP = {
    "99 模板/官方角色介绍模板.md": [
        "03 设定/01 人物/02 新作人物",
        "03 设定/01 人物/01 旧作人物",
    ],
    "99 模板/官方角色介绍模板_轻量化.md": [
        "03 设定/01 人物/03 次要人物"
    ],
    "99 模板/场景地点模板.md": [
        "03 设定/02 场景地点",
    ],
    "99 模板/历史事件模板.md": [
        "03 设定/03 历史事件",
    ],
    "99 模板/计划模板.md": [
        "03 设定/04 计划",
    ],
    "99 模板/组织阵营模板.md": [
        "03 设定/06 组织势力/02 阵营",
        "03 设定/06 组织势力/03 组织机构",
    ],
    "99 模板/政权势力模板.md": [
        "03 设定/06 组织势力/04 国家",
    ],
    "99 模板/种族模板.md": [
        "03 设定/08 种族",
    ],
    "99 模板/生物模板.md": [
        "03 设定/09 生物",
    ],
    "99 模板/怪物模板.md": [
        "03 设定/10 怪物",
    ],
    "99 模板/星域模板.md": [
        "03 设定/11 地理系统/星域",
    ],
    "99 模板/星系模板.md": [
        "03 设定/11 地理系统/星系",
    ],
    "99 模板/行星模板.md": [
        "03 设定/11 地理系统/行星",
    ],
    "99 模板/物品装备模板.md": [
        "03 设定/13 物品装备",
    ],
    "99 模板/秩序与规则模板.md": [
        "03 设定/14 秩序与规则",
    ],
    "99 模板/官方书籍模板.md": [
        "04 官方作品/02 书籍",
    ],
    "99 模板/图片模板.md": [
        "04 官方作品/03 图片",
        "05 同人作品/01 捏捏",
        "05 同人作品/02 约稿",
        "05 同人作品/03 AI绘画",
    ],
    "99 模板/官方音乐专辑模板.md": [
        "04 官方作品/04 音乐",
    ],
    "99 模板/秩序与规则模板.md": [
        "03 设定/14 秩序与规则",
    ],
    "99 模板/秩序与规则模板.md": [
        "03 设定/14 秩序与规则",
        "05 同人作品/04 AI音乐",
    ],
    "99 模板/资料收藏模板.md": [
        "07 资料收藏",
    ],
    "99 模板/文明模板.md": [
        "03 设定/06 组织势力/01 文明纪事",
    ],
    # 你可以无限添加新条目
    # "99 模板/物品模板.md": ["40 道具"],
}

# 全局排除文件夹（所有检测任务都跳过这些目录）
EXCLUDED_DIRS = {
    "00 主面板",
    "01 索引",
    "02 帮助",
    "96 事务管理",
    "97 旧资料存档",
    "98 附件",
    "99 模板",
    "附件",
    "Excalidraw",
    ".obsidian",
    ".trash",
}

# 输出报告路径（自动覆盖旧报告）
OUTPUT_PATH = "96 事务管理/模板兼容性报告.md"
# =========================================================

vault_root = Path(VAULT_PATH)

def extract_headers(file_path):
    """提取文件中指定级别的标题（由 HEADER_LEVEL 控制）"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except:
        return set()
    
    # ⬇️ 修改点 3：动态生成正则表达式（# 的数量由 HEADER_LEVEL 决定）
    # 例如 HEADER_LEVEL=1 时，正则变为 r'^#\s+(.+)$'
    # HEADER_LEVEL=2 时，变为 r'^##\s+(.+)$'
    pattern = r'^' + '#' * HEADER_LEVEL + r'\s+(.+)$'
    headers = re.findall(pattern, text, re.MULTILINE)
    return set(headers)

def scan_folder_for_files(folder_path):
    """扫描单个文件夹，返回该文件夹下所有 .md 文件路径列表（排除全局排除目录）"""
    full_path = vault_root / folder_path
    if not full_path.exists():
        return []
    files = []
    for md_file in full_path.rglob("*.md"):
        parts = md_file.parts
        if any(excl in parts for excl in EXCLUDED_DIRS):
            continue
        files.append(md_file)
    return files

# ---------------------------------------------------------
# 1. 初始化结果容器
# ---------------------------------------------------------
all_results = {}

# ---------------------------------------------------------
# 2. 遍历映射，执行检测
# ---------------------------------------------------------
for template_rel_path, target_folders in TEMPLATE_TARGET_MAP.items():
    template_file = vault_root / template_rel_path
    if not template_file.exists():
        print(f"⚠️ 警告：模板文件不存在，已跳过：{template_file}")
        continue
    
    standard_headers = extract_headers(template_file)
    if not standard_headers:
        print(f"⚠️ 警告：模板中未检测到 {HEADER_LEVEL} 级标题，已跳过：{template_rel_path}")
        continue
    
    print(f"📋 检测模板：{template_rel_path}（标准 {HEADER_LEVEL} 级标题数：{len(standard_headers)}）")
    
    all_target_files = []
    seen_paths = set()
    for folder in target_folders:
        files = scan_folder_for_files(folder)
        for f in files:
            if str(f) not in seen_paths:
                seen_paths.add(str(f))
                all_target_files.append(f)
    
    print(f"   → 匹配到 {len(all_target_files)} 个目标文件")
    
    file_results = []
    for file_path in sorted(all_target_files):
        actual_headers = extract_headers(file_path)
        missing = standard_headers - actual_headers
        extra = actual_headers - standard_headers
        
        if missing or extra:
            file_results.append({
                "file": file_path.stem,
                "folder": file_path.parent.relative_to(vault_root).as_posix(),
                "missing": sorted(missing),
                "extra": sorted(extra),
                "has_missing": bool(missing),
                "has_extra": bool(extra),
            })
    
    template_name = template_file.stem
    all_results[template_name] = {
        "template_path": template_rel_path,
        "standard_headers": standard_headers,
        "results": file_results,
        "total_checked": len(all_target_files),
        "total_diff": len(file_results),
    }

# ---------------------------------------------------------
# 3. 写入总报告（固定路径，自动覆盖，但内嵌时间戳）
# ---------------------------------------------------------
output_file = vault_root / OUTPUT_PATH
output_file.parent.mkdir(parents=True, exist_ok=True)

with open(output_file, "w", encoding="utf-8") as f:
    # 报告顶部写入精确时间戳，方便追溯
    f.write(f"# 📋 全模板兼容性检测报告\n\n")
    f.write(f"> **生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"> **检测标题级别**：{'#' * HEADER_LEVEL}（{'一级' if HEADER_LEVEL == 1 else '二级' if HEADER_LEVEL == 2 else '三级'}标题）\n")
    f.write(f"> **检测模板数**：{len(all_results)} 个\n\n")
    
    if not all_results:
        f.write("⚠️ 未检测到任何有效模板，请检查配置。\n")
    else:
        for template_name, data in all_results.items():
            f.write(f"## 📄 模板：{template_name}\n")
            f.write(f"- **模板路径**：`{data['template_path']}`\n")
            f.write(f"- **标准标题数**：{len(data['standard_headers'])} 个\n")
            f.write(f"- **扫描文件数**：{data['total_checked']} 个\n")
            f.write(f"- **存在差异文件数**：{data['total_diff']} 个\n\n")
            
            if not data["results"]:
                f.write("> ✅ 所有文件均完美兼容该模板！\n\n")
                continue
            
            f.write("| 文件 | 所属目录 | 缺少的标题 | 多余的标题 | 优先级 |\n")
            f.write("|:---|:---|:---|:---|:---|\n")
            
            sorted_results = sorted(data["results"], key=lambda x: (-x["has_missing"], x["file"]))
            for row in sorted_results:
                missing_str = "、".join(row["missing"]) if row["missing"] else "（无）"
                extra_str = "、".join(row["extra"]) if row["extra"] else "（无）"
                
                if row["has_missing"] and row["has_extra"]:
                    priority = "🔴 紧急"
                elif row["has_missing"]:
                    priority = "🔴 高"
                else:
                    priority = "🟡 低"
                
                f.write(f"| {row['file']} | {row['folder']} | {missing_str} | {extra_str} | {priority} |\n")
            
            f.write("\n---\n\n")
    
    # 尾部汇总建议
    f.write("### 🗺️ 全局行动建议\n")
    f.write("1. **优先处理「🔴 紧急」项**：既缺标准章节、又有冗余旧标题，建议直接对照模板重构。\n")
    f.write("2. **其次处理「🔴 高」项**：对照模板将缺失标题补全。\n")
    f.write("3. **「🟡 低」项可暂缓**：仅含多余标题，按需清理。\n")
    f.write("4. **结合热度地图**：优先处理位于「❄️ 核心冻结」状态的文件。\n")

print(f"\n✅ 全模板检测完成！报告已覆盖更新：{output_file}")
print(f"📊 共检测 {len(all_results)} 个模板，标题级别：{'#' * HEADER_LEVEL}")
