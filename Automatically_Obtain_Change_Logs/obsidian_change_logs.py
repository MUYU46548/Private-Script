# 自动获取Obsidian变更日志（基线快照对比）

import json
import re
from pathlib import Path
from datetime import datetime

# =========================================================
# 配置区（请根据你的实际情况修改）
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"   # 你的库绝对路径

# 基线文件存储路径
BASELINE_PATH = "96 事务管理/结构基线.json"
LOG_PATH = "96 事务管理/变更日志.md"

# 排除的文件夹（这些文件夹内的文件不纳入变更追踪）
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

# 检测的标题级别（1=#, 2=##, 3=###）
# 建议设为 1，与你模板检测的级别保持一致
HEADER_LEVEL = 1
# =========================================================

vault_root = Path(VAULT_PATH)
baseline_file = vault_root / BASELINE_PATH
log_file = vault_root / LOG_PATH

def extract_headers(file_path):
    """提取指定级别的标题集合"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except:
        return set()
    pattern = r'^' + '#' * HEADER_LEVEL + r'\s+(.+)$'
    headers = re.findall(pattern, text, re.MULTILINE)
    return set(headers)

def scan_vault():
    """扫描全库，返回 {相对路径: (mtime, 标题集合)}"""
    all_files = {}
    for md_file in vault_root.rglob("*.md"):
        # 检查是否在排除目录中
        parts = md_file.parts
        if any(excl in parts for excl in EXCLUDED_DIRS):
            continue
        rel_path = md_file.relative_to(vault_root).as_posix()
        mtime = md_file.stat().st_mtime
        headers = extract_headers(md_file)
        all_files[rel_path] = (mtime, headers)
    return all_files

def load_baseline():
    """加载基线JSON，如果不存在则返回None"""
    if not baseline_file.exists():
        return None
    with open(baseline_file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_baseline(data):
    """保存基线JSON"""
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def append_log(entry):
    """追加变更记录到日志文件"""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n\n")

# ---------------------------------------------------------
# 主流程
# ---------------------------------------------------------
print("🔍 正在扫描当前全库状态...")
current_snapshot = scan_vault()
print(f"📄 共扫描到 {len(current_snapshot)} 个文件")

old_baseline = load_baseline()

if old_baseline is None:
    # ---- 首次运行：建立基线 ----
    # 基线存储格式：{ "路径": {"mtime": 数值, "headers": [列表]} }
    baseline_data = {}
    for rel_path, (mtime, headers) in current_snapshot.items():
        baseline_data[rel_path] = {
            "mtime": mtime,
            "headers": list(headers)
        }
    save_baseline(baseline_data)
    
    # 写入初始日志标记
    init_log = f"# 📋 变更日志\n\n> **基线建立时间**：{datetime.now().strftime('%Y-%Y-%m-%d %H:%M:%S')}\n"
    init_log += f"> **基线文件数**：{len(baseline_data)} 个\n"
    init_log += f"> **追踪标题级别**：{'#' * HEADER_LEVEL}\n"
    append_log(init_log)
    print("✅ 首次运行，基线已建立。变更日志已初始化。")
    
else:
    # ---- 非首次运行：对比变更 ----
    changes = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 检查当前文件与基线的差异
    for rel_path, (cur_mtime, cur_headers) in current_snapshot.items():
        old_entry = old_baseline.get(rel_path)
        if old_entry is None:
            # 新增文件
            changes.append(f"- ➕ **新增**：`{rel_path}`（标题：{', '.join(sorted(cur_headers)) if cur_headers else '无'}）")
            continue
        
        old_mtime = old_entry["mtime"]
        old_headers = set(old_entry["headers"])
        
        # 结构对比（标题变化）
        added = cur_headers - old_headers
        removed = old_headers - cur_headers
        
        if added or removed:
            detail = []
            if added:
                detail.append(f"新增标题「{'」、「'.join(sorted(added))}」")
            if removed:
                detail.append(f"删除标题「{'」、「'.join(sorted(removed))}」")
            changes.append(f"- 🔄 **结构变更**：`{rel_path}`（{', '.join(detail)}）")
        elif cur_mtime != old_mtime:
            # 内容变化但结构未变
            changes.append(f"- ✏️ **内容微调**：`{rel_path}`（结构无变化，仅正文修改）")
    
    # 检查被删除的文件
    for rel_path in old_baseline.keys():
        if rel_path not in current_snapshot:
            changes.append(f"- ❌ **删除**：`{rel_path}`")
    
    # 如果有变更，写入日志并更新基线
    if changes:
        log_entry = f"## 📅 {now_str}\n"
        log_entry += "\n".join(changes)
        append_log(log_entry)
        print(f"📝 检测到 {len(changes)} 项变更，已追加到日志。")
    else:
        # 无变化也记录一条简短状态（便于确认脚本正常运行）
        log_entry = f"## 📅 {now_str}\n- ✅ 无变更（全库结构稳定）"
        append_log(log_entry)
        print("✅ 无变更，已记录状态到日志。")
    
    # 更新基线（覆盖为当前快照）
    baseline_data = {}
    for rel_path, (mtime, headers) in current_snapshot.items():
        baseline_data[rel_path] = {
            "mtime": mtime,
            "headers": list(headers)
        }
    save_baseline(baseline_data)
    print("🔄 基线已更新。")
