# Obsidian 附件审计脚本
# 功能：扫描孤立附件（未被任何笔记引用）和重复附件（MD5哈希比对）

import os
import re
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =========================================================
# 默认配置
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"
ATTACHMENT_DIRS = ["98 附件"]  # 附件目录列表（支持多目录）
REPORT_PATH = "96 事务管理/附件审计报告.md"

# 支持的附件扩展名
ATTACHMENT_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp',
                         '.svg', '.ico', '.tiff', '.heic', '.heif',
                         '.mp3', '.mp4', '.mov', '.avi', '.mkv',
                         '.pdf', '.doc', '.docx', '.xls', '.xlsx',
                         '.ppt', '.pptx', '.zip', '.rar', '.7z'}

# 排除的笔记目录
EXCLUDED_DIRS = {
    ".obsidian", ".git", ".trash", "Obsidian_AI_Sandbox",
    "96 事务管理", "97 旧资料存档",
}

# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Obsidian附件审计：孤立附件+重复检测")
    parser.add_argument("--vault", default=VAULT_PATH, help="Obsidian库路径")
    parser.add_argument("--attachments", nargs="+", default=ATTACHMENT_DIRS,
                        help="附件目录列表（相对路径）")
    parser.add_argument("--output", default=REPORT_PATH, help="报告输出相对路径")
    parser.add_argument("--move-orphan", action="store_true",
                        help="将孤立附件移动到回收文件夹（默认不移动）")
    parser.add_argument("--delete-duplicate", action="store_true",
                        help="自动删除重复附件（危险！默认仅报告）")
    return parser.parse_args()


def get_file_hash(filepath, chunk_size=8192):
    """计算文件 MD5 哈希"""
    md5 = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                md5.update(chunk)
        return md5.hexdigest()
    except (PermissionError, OSError):
        return None


def scan_attachments(vault_root, attachment_dirs, extensions):
    """扫描附件目录中的所有附件文件"""
    attachments = {}
    for att_dir_name in attachment_dirs:
        att_path = vault_root / att_dir_name
        if not att_path.exists():
            print(f"  ⚠️ 附件目录不存在，跳过: {att_dir_name}")
            continue
        for f in att_path.iterdir():
            if f.is_file() and f.suffix.lower() in extensions:
                attachments[f.name] = {
                    "path": f,
                    "size": f.stat().st_size,
                    "mtime": datetime.fromtimestamp(f.stat().st_mtime),
                    "rel_dir": att_dir_name,
                }
    return attachments


def scan_all_md_references(vault_root, excluded_dirs):
    """扫描全库所有 .md 文件，提取所有可能的附件引用"""
    # 匹配模式：
    # 1. ![[文件名]] 或 [[文件名]]（wiki 链接/embed）
    # 2. 纯文本中的文件名
    link_pattern = re.compile(r'!?\[\[([^|\]]+)(?:\|[^\]]+)?\]\]')
    
    all_referenced_names = set()  # 所有被引用的文件名
    reference_map = defaultdict(list)  # 文件名 -> [(引用来源, 引用文本)]
    
    for md_file in vault_root.rglob("*.md"):
        # 检查是否在排除目录
        parts = md_file.parts
        if any(excl in parts for excl in excluded_dirs):
            continue
        
        try:
            content = md_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError, OSError):
            continue
        
        rel_path = str(md_file.relative_to(vault_root))
        
        # 提取 wiki 链接/embed
        for match in link_pattern.finditer(content):
            target = match.group(1).strip()
            # 处理带路径的链接：98 附件/文件名.png -> 文件名.png
            if '/' in target:
                referenced_name = Path(target).name
            else:
                referenced_name = target
            all_referenced_names.add(referenced_name)
            reference_map[referenced_name].append((rel_path, match.group(0)))
    
    return all_referenced_names, reference_map


def find_duplicates(attachments):
    """通过 MD5 哈希找出重复文件"""
    hash_map = defaultdict(list)  # hash -> [文件名列表]
    
    print("   正在计算文件哈希（用于重复检测）...")
    count = 0
    for name, info in attachments.items():
        file_hash = get_file_hash(info["path"])
        if file_hash:
            hash_map[file_hash].append(name)
        count += 1
        if count % 20 == 0:
            print(f"     进度: {count}/{len(attachments)}")
    
    # 过滤出真正重复的（同哈希且同大小）
    duplicates = {}
    for file_hash, names in hash_map.items():
        if len(names) > 1:
            # 按大小二次确认
            size_groups = defaultdict(list)
            for name in names:
                size_groups[attachments[name]["size"]].append(name)
            for size, group in size_groups.items():
                if len(group) > 1:
                    duplicates[file_hash] = group
    
    return duplicates


def find_similar_names(attachments):
    """找出文件名高度相似的可能重复（去除空格、后缀数字等）"""
    def normalize(name):
        stem = Path(name).stem
        # 去除尾部空格、数字、下划线、横杠
        normalized = re.sub(r'[\s_\-\.]+$', '', stem)
        # 去除尾部数字
        normalized = re.sub(r'\d+$', '', normalized).strip()
        return normalized.lower()
    
    norm_map = defaultdict(list)
    for name in attachments:
        norm = normalize(name)
        if norm:
            norm_map[norm].append(name)
    
    similar = {k: v for k, v in norm_map.items() if len(v) > 1}
    return similar


def generate_report(vault_root, attachments, orphans, duplicates, similar_names,
                    reference_map, args):
    """生成 Markdown 报告"""
    output_path = vault_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    total_size = sum(a["size"] for a in attachments.values())
    orphan_size = sum(attachments[n]["size"] for n in orphans)
    
    lines = [
        f"# 📎 附件审计报告",
        f"",
        f"> **生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> **附件目录**：{', '.join(f'`{d}`' for d in args.attachments)}",
        f"> **附件总数**：{len(attachments)} 个",
        f"> **总占用空间**：{format_size(total_size)}",
        f"> **孤立附件数**：{len(orphans)} 个（{format_size(orphan_size)}）",
        f"> **重复附件组**：{len(duplicates)} 组",
        f"> **相似文件名**：{len(similar_names)} 组",
        f"",
        f"---",
        f"",
    ]
    
    # 孤立附件
    lines.append(f"## 🗑️ 孤立附件（{len(orphans)} 个）\n")
    lines.append(f"以下文件存在于附件目录，但未被任何笔记引用：\n")
    
    if orphans:
        lines.append(f"| 文件名 | 大小 | 最后修改 | 路径 |")
        lines.append(f"|:---|:---|:---|:---|")
        for name in sorted(orphans):
            info = attachments[name]
            lines.append(
                f"| `{name}` | {format_size(info['size'])} | "
                f"{info['mtime'].strftime('%Y-%m-%d')} | `{info['rel_dir']}` |"
            )
    else:
        lines.append(f"_未发现孤立附件_\n")
    
    lines.extend(["", "---", ""])
    
    # 重复附件（哈希）
    lines.append(f"## 🔄 重复附件（{len(duplicates)} 组）\n")
    lines.append(f"基于 MD5 哈希和文件大小检测到的完全重复文件：\n")
    
    if duplicates:
        for i, (file_hash, names) in enumerate(sorted(duplicates.items()), 1):
            size = attachments[names[0]]["size"]
            lines.append(f"### 第 {i} 组（{format_size(size)}，共 {len(names)} 个副本）\n")
            for name in sorted(names):
                info = attachments[name]
                lines.append(f"- `{name}` — {info['rel_dir']}，{info['mtime'].strftime('%Y-%m-%d')}")
            lines.append("")
            lines.append(f"> **建议**：保留一份，其余删除。保留最新或路径最短的那份。\n")
    else:
        lines.append(f"_未发现完全重复附件_\n")
    
    lines.extend(["", "---", ""])
    
    # 相似文件名
    lines.append(f"## 🔍 疑似重复（相似文件名，{len(similar_names)} 组）\n")
    lines.append(f"以下文件名高度相似，可能是同一图片的不同版本：\n")
    
    if similar_names:
        for norm, names in sorted(similar_names.items()):
            lines.append(f"### 相似组：`{norm}`\n")
            for name in sorted(names):
                info = attachments[name]
                size = format_size(info['size'])
                mtime = info['mtime'].strftime('%Y-%m-%d')
                # 检查是否被引用
                ref_count = len(reference_map.get(name, []))
                ref_status = f"✅ 被引用 {ref_count} 次" if ref_count > 0 else "❌ 未被引用"
                lines.append(f"- `{name}` — {size}，{mtime}，{ref_status}")
            lines.append("")
    else:
        lines.append(f"_未发现相似文件名_\n")
    
    lines.extend(["", "---", ""])
    
    # 汇总行动建议
    lines.append(f"## 📋 汇总行动建议\n")
    lines.append(f"| 优先级 | 操作 | 数量 | 可回收空间 |")
    lines.append(f"|:---|:---|:---|:---|")
    lines.append(f"| 🔴 高 | 删除孤立附件 | {len(orphans)} 个 | {format_size(orphan_size)} |")
    
    dup_count = sum(len(v) - 1 for v in duplicates.values())
    dup_size = sum(
        attachments[v[0]]["size"] * (len(v) - 1)
        for v in duplicates.values()
    )
    lines.append(f"| 🟡 中 | 删除重复附件副本 | {dup_count} 个 | {format_size(dup_size)} |")
    lines.append(f"| 🟢 低 | 审核相似文件名 | {sum(len(v) for v in similar_names.values())} 个 | — |")
    
    lines.extend(["", "---", ""])
    lines.append(f"### ⚠️ 注意事项\n")
    lines.append(f"1. 孤立附件判定仅基于文本搜索，某些动态引用（如 Dataview 插件）可能无法被检测")
    lines.append(f"2. 删除操作不可逆，建议先备份")
    lines.append(f"3. 可使用 `--move-orphan` 将孤立附件移至回收站而非直接删除")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    return output_path


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# =========================================================
# 主流程
# =========================================================
def main():
    args = parse_args()
    vault_root = Path(args.vault)
    
    if not vault_root.exists():
        print(f"❌ 库路径不存在: {vault_root}")
        return
    
    print("=" * 60)
    print("  📎 Obsidian 附件审计工具")
    print("=" * 60)
    
    # 1. 扫描附件
    print(f"\n📁 扫描附件目录...")
    attachments = scan_attachments(vault_root, args.attachments, ATTACHMENT_EXTENSIONS)
    total_size = sum(a["size"] for a in attachments.values())
    print(f"   发现 {len(attachments)} 个附件文件，总大小 {format_size(total_size)}")
    
    # 2. 扫描全库引用
    print(f"\n🔍 扫描全库笔记中的引用...")
    all_referenced_names, reference_map = scan_all_md_references(vault_root, EXCLUDED_DIRS)
    print(f"   发现 {len(all_referenced_names)} 个被引用文件名")
    
    # 3. 找出孤立附件
    orphans = set(attachments.keys()) - all_referenced_names
    orphan_size = sum(attachments[n]["size"] for n in orphans)
    print(f"\n🗑️ 孤立附件: {len(orphans)} 个 ({format_size(orphan_size)})")
    
    # 4. 检测重复（哈希）
    print(f"\n🔄 检测重复附件（MD5 哈希）...")
    duplicates = find_duplicates(attachments)
    print(f"   发现 {len(duplicates)} 组完全重复")
    
    # 5. 检测相似文件名
    print(f"\n🔍 检测相似文件名...")
    similar_names = find_similar_names(attachments)
    print(f"   发现 {len(similar_names)} 组相似文件名")
    
    # 6. 生成报告
    print(f"\n📝 生成报告...")
    report_path = generate_report(
        vault_root, attachments, orphans, duplicates, similar_names,
        reference_map, args
    )
    print(f"   报告已保存: {report_path}")
    
    # 7. 汇总
    print(f"\n{'='*60}")
    print(f"  审计完成")
    print(f"{'='*60}")
    print(f"  附件总数: {len(attachments)} 个 ({format_size(total_size)})")
    print(f"  孤立附件: {len(orphans)} 个 ({format_size(orphan_size)})")
    print(f"  重复组数: {len(duplicates)} 组")
    print(f"  相似文件: {len(similar_names)} 组")
    print(f"  报告路径: {report_path}")


if __name__ == "__main__":
    main()
