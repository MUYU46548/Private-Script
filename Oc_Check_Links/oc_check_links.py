#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian OC作品双向链接校验脚本（增强版）
适用：角色文档与作品文档的映射关系检查。
功能：检查含有 "## 官作出场记录" 章节的角色文档，
      验证其作品链接在目标作品的 "## 登场角色" 中是否有正确的反向链接。
      所有详细结果输出为 Markdown 报告文件。
      支持指定多个角色文件夹和多个作品文件夹。
限制：若模板发生调整或页面结构变动，可能影响本脚本工作准确性。
用法：修改下方用户配置后直接运行。
"""

import re
from pathlib import Path
from datetime import datetime

# ============== 用户配置 ==============
VAULT_PATH = "E:/图书馆/ROSA"          # 修改为你的 Obsidian 仓库根目录
ROLE_FOLDERS =  ["03 设定/01 人物/02 新作人物", "03 设定/01 人物/01 旧作人物"]  # 存放角色文档的文件夹名（相对 VAULT_PATH）
WORK_FOLDERS = ["04 官方作品/01 旧作专区", "04 官方作品/02 书籍"]  # 作品文档所在的多个文件夹（相对 VAULT_PATH）
REPORT_PATH = "E:/图书馆/ROSA/96 事务管理/OC校验报告.md"           # 报告输出路径
# ======================================



def extract_wikilinks(text):
    """提取所有 [[链接]] 中的链接名（忽略别名）"""
    return re.findall(r'\[\[([^|\]]+)(?:\|[^\]]+)?\]\]', text)


def extract_section(text, section_title):
    """提取 Markdown 中指定二级标题下的内容"""
    pattern = rf'(?m)^##\s*{re.escape(section_title)}\s*\n(.*?)(?=\n##\s|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def find_work_file(vault_path, work_name, work_folders):
    """
    在指定的作品文件夹列表中查找 work_name.md
    返回：Path 对象（如果找到），否则 None
    """
    for folder in work_folders:
        candidate = Path(vault_path) / folder / f"{work_name}.md"
        if candidate.exists():
            return candidate
    # 如果没找到，再尝试根目录（兼容旧习惯）
    root_candidate = Path(vault_path) / f"{work_name}.md"
    if root_candidate.exists():
        return root_candidate
    return None


def check_single_role(vault_path, role_file_path, work_folders, report):
    """
    检查单个角色，所有输出追加到 report 列表
    返回：是否有错误（True/False）
    """
    role_full = Path(vault_path) / role_file_path
    if not role_full.exists():
        report.append(f"- ❌ **角色文档不存在**: `{role_file_path}`")
        return True

    with open(role_full, 'r', encoding='utf-8') as f:
        role_content = f.read()

    role_name = role_full.stem
    report.append(f"## 📖 角色: {role_name}")

    # 检查是否有 "官作出场记录" 章节
    records_section = extract_section(role_content, "官作出场记录")
    if not records_section:
        report.append("  ⏭️ 跳过（无 `## 官作出场记录` 章节，轻量模板）\n")
        return False

    # 提取作品链接
    work_links = extract_wikilinks(records_section)
    if not work_links:
        report.append("  ⚠️ 该章节中未找到任何作品链接\n")
        return False

    report.append(f"  共发现 {len(work_links)} 个作品链接：")
    has_error = False

    for work in work_links:
        # 使用新函数查找作品文件
        work_file = find_work_file(vault_path, work, work_folders)
        if work_file is None:
            report.append(f"    - ⚠️ 作品文档不存在: `{work}.md`（在指定作品文件夹中未找到）")
            has_error = True
            continue

        # 读取作品文档
        with open(work_file, 'r', encoding='utf-8') as f:
            work_content = f.read()

        # 检查 "## 登场角色" 区域的反向链接
        section_text = extract_section(work_content, "登场角色")
        if not section_text:
            report.append(f"    - ⚠️ 作品 `{work}` 无 `## 登场角色` 章节，跳过反向检查")
            continue

        backlink = f"[[{role_name}]]"
        if backlink not in section_text:
            report.append(f"    - ❌ 作品 `{work}` 的【登场角色】区域缺少指向 `{role_name}` 的反向链接")
            has_error = True
        else:
            report.append(f"    - ✅ 作品 `{work}` 的反向链接正确")

    report.append("")
    return has_error


def generate_report(vault_path, role_folders, work_folders, report_path):
    """遍历所有角色文件夹，生成报告"""
    # 收集所有角色文档
    all_role_files = set()
    for folder in role_folders:
        role_dir = Path(vault_path) / folder
        if not role_dir.exists():
            print(f"⚠️ 跳过不存在的角色文件夹: {folder}")
            continue
        for file in role_dir.glob("*.md"):
            rel_path = str(file.relative_to(vault_path))
            all_role_files.add(rel_path)

    if not all_role_files:
        print("❌ 未在任何指定角色文件夹中找到角色文档")
        return

    role_files = sorted(all_role_files)
    print(f"📂 共找到 {len(role_files)} 个角色文档（来自文件夹：{', '.join(role_folders)}）")
    if work_folders:
        print(f"📂 作品文档将在以下文件夹中查找：{', '.join(work_folders)}")
    else:
        print("📂 作品文档仅在根目录中查找")

    # 初始化报告
    report_lines = [
        f"# Obsidian 链接校验报告",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"仓库路径：`{vault_path}`",
        f"角色文件夹：{', '.join(f'`{f}`' for f in role_folders)}",
        f"作品文件夹：{', '.join(f'`{f}`' for f in work_folders) if work_folders else '根目录'}",
        "",
        f"共检查 **{len(role_files)}** 个角色文档。",
        "---",
        ""
    ]

    error_count = 0
    for rel_path in role_files:
        if check_single_role(vault_path, rel_path, work_folders, report_lines):
            error_count += 1

    # 总结
    report_lines.append("---")
    report_lines.append(f"## 总结")
    report_lines.append(f"- 检查角色总数：{len(role_files)}")
    report_lines.append(f"- 发现问题（含缺失反向链接、文档不存在等）的角色数：{error_count}")

    # 写入报告
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))

    print(f"\n✅ 报告已生成：{report_path.absolute()}")


if __name__ == "__main__":
    generate_report(VAULT_PATH, ROLE_FOLDERS, WORK_FOLDERS, REPORT_PATH)