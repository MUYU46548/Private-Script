# 自动获取Obsidian变更日志（增强版 v2）
# 改进：月度日志轮转、CLI参数、dry-run模式、错误处理、基线元数据

import json
import re
import argparse
from pathlib import Path
from datetime import datetime

# =========================================================
# 配置区（默认值，可通过CLI覆盖）
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"
BASELINE_PATH = "96 事务管理/结构基线.json"
LOG_DIR = "96 事务管理"  # 日志文件夹（按月分割存放于此）

# 排除的文件夹
EXCLUDED_DIRS = {
    "00 主面板", "01 索引", "02 帮助",
    "07 资料收藏", "96 事务管理", "97 旧资料存档",
    "98 附件", "99 模板", "指令集", "附件",
    "Obsidian_AI_Sandbox", "Excalidraw",
    ".obsidian", ".trash",
}

# 检测的标题级别
HEADER_LEVEL = 1

# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian变更日志（月度轮转版）")
    parser.add_argument("--vault", default=VAULT_PATH, help="Obsidian库路径")
    parser.add_argument("--baseline", default=BASELINE_PATH, help="基线文件相对路径")
    parser.add_argument("--log-dir", default=LOG_DIR, help="日志文件夹（按月自动分割）")
    parser.add_argument("--dry-run", action="store_true", help="仅检测不写日志/更新基线")
    parser.add_argument("--quiet", action="store_true", help="无变更时不写入日志条目")
    parser.add_argument("--header-level", type=int, default=HEADER_LEVEL, choices=[1,2,3])
    return parser.parse_args()

def extract_headers(file_path, header_level):
    """提取指定级别的标题集合"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError, OSError) as e:
        print(f"  ⚠️ 跳过（读取失败）: {file_path.name} — {e}")
        return set()
    pattern = r'^' + '#' * header_level + r'\s+(.+)$'
    headers = re.findall(pattern, text, re.MULTILINE)
    return set(headers)

def scan_vault(vault_root, header_level):
    """扫描全库，返回 {相对路径: (mtime, 标题集合)}"""
    all_files = {}
    for md_file in vault_root.rglob("*.md"):
        parts = md_file.parts
        if any(excl in parts for excl in EXCLUDED_DIRS):
            continue
        try:
            rel_path = md_file.relative_to(vault_root).as_posix()
            mtime = md_file.stat().st_mtime
            headers = extract_headers(md_file, header_level)
            all_files[rel_path] = (mtime, headers)
        except (PermissionError, OSError) as e:
            print(f"  ⚠️ 跳过（访问失败）: {md_file.name} — {e}")
    return all_files

def load_baseline(baseline_file):
    """加载基线JSON"""
    if not baseline_file.exists():
        return None
    try:
        with open(baseline_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 兼容旧格式（无metadata）
        if "_metadata" not in data:
            return {"_metadata": {"version": 1, "migrated": True}, "files": data}
        return data
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("  ❌ 基线文件损坏，将重新建立")
        return None

def save_baseline(baseline_file, file_data):
    """保存基线JSON（带元数据）"""
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    baseline = {
        "_metadata": {
            "version": 2,
            "last_updated": datetime.now().isoformat(timespec="seconds"),
            "file_count": len(file_data),
        },
        "files": file_data,
    }
    with open(baseline_file, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)

def get_log_file(log_dir, now=None):
    """获取当月日志文件路径"""
    if now is None:
        now = datetime.now()
    log_dir_path = Path(log_dir)
    monthly_name = f"变更日志_{now.strftime('%Y-%m')}.md"
    return log_dir_path / monthly_name

def append_log(log_file, entry):
    """追加变更记录到日志文件"""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n\n")

# ---------------------------------------------------------
# 主流程
# ---------------------------------------------------------
args = parse_args()

vault_root = Path(args.vault)
baseline_file = vault_root / args.baseline
log_dir_path = vault_root / args.log_dir

print("🔍 正在扫描当前全库状态...")
current_snapshot = scan_vault(vault_root, args.header_level)
print(f"📄 共扫描到 {len(current_snapshot)} 个文件")

baseline_data = load_baseline(baseline_file)

# 从新版基线中提取files字典
if baseline_data and "files" in baseline_data:
    old_baseline = baseline_data["files"]
else:
    old_baseline = baseline_data  # 旧格式兼容

if old_baseline is None:
    # ---- 首次运行：建立基线 ----
    baseline_files = {}
    for rel_path, (mtime, headers) in current_snapshot.items():
        baseline_files[rel_path] = {"mtime": mtime, "headers": list(headers)}

    if not args.dry_run:
        save_baseline(baseline_file, baseline_files)

        # 写入初始日志（当月文件）
        now = datetime.now()
        log_file = get_log_file(log_dir_path, now)
        init_log = (
            f"# 📋 变更日志\n\n"
            f"> **基线建立时间**：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"> **基线文件数**：{len(baseline_files)} 个\n"
            f"> **追踪标题级别**：{'#' * args.header_level}\n\n"
            f"---\n"
        )
        append_log(log_file, init_log)
        print("✅ 首次运行，基线已建立。变更日志已初始化。")
        print(f"   基线文件: {baseline_file}")
        print(f"   日志文件: {log_file}")
    else:
        print("🔍 [dry-run] 基线未建立，跳过写入")
else:
    # ---- 非首次运行：对比变更 ----
    changes = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for rel_path, (cur_mtime, cur_headers) in current_snapshot.items():
        old_entry = old_baseline.get(rel_path)
        if old_entry is None:
            changes.append(f"- ➕ **新增**：`{rel_path}`（标题：{', '.join(sorted(cur_headers)) if cur_headers else '无'}）")
            continue

        old_mtime = old_entry["mtime"]
        old_headers = set(old_entry["headers"])

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
            changes.append(f"- ✏️ **内容微调**：`{rel_path}`（结构无变化，仅正文修改）")

    for rel_path in old_baseline.keys():
        if rel_path not in current_snapshot:
            changes.append(f"- ❌ **删除**：`{rel_path}`")

    log_file = get_log_file(log_dir_path)

    if changes:
        log_entry = f"## 📅 {now_str}\n" + "\n".join(changes)
        if not args.dry_run:
            append_log(log_file, log_entry)
            print(f"📝 检测到 {len(changes)} 项变更，已追加到当月日志。")
            print(f"   日志文件: {log_file}")
        else:
            print(f"🔍 [dry-run] 检测到 {len(changes)} 项变更（未写入）")
            for c in changes[:10]:
                print(f"   {c}")
            if len(changes) > 10:
                print(f"   ... 等共 {len(changes)} 项")
    elif not args.quiet:
        log_entry = f"## 📅 {now_str}\n- ✅ 无变更（全库结构稳定）"
        if not args.dry_run:
            append_log(log_file, log_entry)
            print("✅ 无变更，已记录状态到日志。")
        else:
            print("🔍 [dry-run] 无变更")

    # 更新基线
    new_baseline_files = {}
    for rel_path, (mtime, headers) in current_snapshot.items():
        new_baseline_files[rel_path] = {"mtime": mtime, "headers": list(headers)}

    if not args.dry_run:
        save_baseline(baseline_file, new_baseline_files)
        print("🔄 基线已更新。")
    else:
        print("🔍 [dry-run] 基线未更新")
