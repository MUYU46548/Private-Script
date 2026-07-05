"""
文件核对脚本 (升级版)
功能：智能模糊匹配、多格式展示、穿透子文件夹搜索
"""

import os
import csv
import sys
from pathlib import Path

# ========================
# ⚙️ 在这里修改您的配置
# ========================

# 表格文件路径（支持 .xlsx / .csv）
TABLE_FILE = r"E:/图书馆/编辑室/710/已完成/修订计划表.xlsx"

# 要检查的目标文件夹路径
TARGET_FOLDER = r"E:/图书馆/编辑室/710/已完成"

# 表格中「文件名」所在的列（从1开始数，A列=1，B列=2）
FILENAME_COLUMN = 2

# 表格数据从第几行开始（跳过表头，通常从2开始）
DATA_START_ROW = 2

# ========================
# 🚀 核心逻辑
# ========================

def read_filenames_from_excel(filepath):
    """从 Excel 表格读取文件名列表"""
    try:
        import openpyxl
    except ImportError:
        print("❌ 缺少 openpyxl 库，请在终端运行: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    filenames = []
    for row in ws.iter_rows(min_row=DATA_START_ROW, values_only=True):
        name = row[FILENAME_COLUMN - 1]
        if name and str(name).strip():
            # 清理掉Excel中可能带有的换行符或多余空格
            filenames.append(str(name).strip().replace('\n', ' '))
    wb.close()
    return filenames

def read_filenames_from_csv(filepath):
    """从 CSV 文件读取文件名列表"""
    filenames = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i < DATA_START_ROW - 1: continue
            if len(row) >= FILENAME_COLUMN:
                name = row[FILENAME_COLUMN - 1].strip()
                if name: filenames.append(name)
    return filenames

def get_all_files_in_folder(folder):
    """获取文件夹及所有子文件夹中的文件 (穿透搜索)"""
    folder = Path(folder)
    # rglob("*") 会自动穿透所有层级的子文件夹
    return [f for f in folder.rglob("*") if f.is_file()]

def find_matching_files(target_name, all_files):
    """
    智能查找匹配的文件
    1. 精确匹配 (忽略大小写)
    2. 模糊匹配 (处理 name -> name_20260101 的情况)
    """
    target_path = Path(target_name)
    target_stem = target_path.stem.lower()  # 表格中的名字 (小写)
    target_suffix = target_path.suffix.lower() # 表格中的后缀 (如果有)
    has_ext = bool(target_suffix)

    matches = []
    for f in all_files:
        f_stem = f.stem.lower()
        f_name = f.name.lower()

        # 1. 精确匹配 (带后缀或不带后缀)
        if has_ext and f_name == target_name.lower():
            matches.append(f)
            continue
        if not has_ext and f_stem == target_stem:
            matches.append(f)
            continue

        # 2. 智能模糊匹配 (仅当表格没写后缀时触发)
        # 解决：表格写 "报告"，实际文件是 "报告_20260101" 或 "报告-最终版"
        if not has_ext and f_stem.startswith(target_stem):
            if len(f_stem) > len(target_stem):
                # 获取紧跟着的下一个字符
                next_char = f_stem[len(target_stem)]
                # 如果下一个字符不是字母 (允许数字、下划线、横杠、空格等)，则认为是匹配的后缀
                if not next_char.isalpha():
                    matches.append(f)
                    continue

    return matches

def format_size(size_bytes):
    if size_bytes < 1024: return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024: return f"{size_bytes / 1024:.1f} KB"
    else: return f"{size_bytes / (1024 * 1024):.1f} MB"

def main():
    print("=" * 65)
    print("  📂 文件核对工具 (智能模糊匹配 & 多格式识别版)")
    print("=" * 65)

    table_file = Path(TABLE_FILE)
    target_folder = Path(TARGET_FOLDER)

    if not table_file.exists():
        print(f"❌ 找不到表格文件: {table_file.resolve()}")
        return
    if not target_folder.exists():
        print(f"❌ 找不到目标文件夹: {target_folder.resolve()}")
        return

    print(f"📄 表格文件: {table_file.resolve()}")
    print(f"📁 目标文件夹: {target_folder.resolve()} (包含所有子文件夹)")
    print("-" * 65)

    # 读取与扫描
    print("\n⏳ 正在读取表格并扫描文件夹...")
    if table_file.suffix.lower() in (".xlsx", ".xls"):
        filenames = read_filenames_from_excel(table_file)
    elif table_file.suffix.lower() == ".csv":
        filenames = read_filenames_from_csv(table_file)
    else:
        print(f"❌ 不支持的表格格式: {table_file.suffix}")
        return

    all_files = get_all_files_in_folder(target_folder)
    print(f"✅ 读取到 {len(filenames)} 个目标文件，扫描到 {len(all_files)} 个实际文件")
    print("-" * 65)

    # 核对逻辑
    found_list = []
    missing_list = []

    for name in filenames:
        matches = find_matching_files(name, all_files)
        if not matches:
            missing_list.append(name)
        else:
            # 提取所有找到的格式 (后缀)
            exts = sorted(list(set(m.suffix.lower() if m.suffix else '(无后缀)' for m in matches)))
            found_list.append({
                'name': name,
                'matches': matches,
                'exts': exts
            })

    # ========================
    # 📊 输出结果
    # ========================
    print(f"\n{'='*65}")
    print(f"  📊 核对结果汇总")
    print(f"{'='*65}")
    print(f"  ✅ 找到: {len(found_list)} 个")
    print(f"  ❌ 缺失: {len(missing_list)} 个")

    # 1. 详细 - 找到的文件 (展示多格式和子文件夹路径)
    if found_list:
        print(f"\n{'─'*65}")
        print(f"✅ 已找到的文件详情:")
        print(f"{'─'*65}")
        for item in found_list:
            name = item['name']
            exts = item['exts']
            matches = item['matches']
            
            # 格式化格式提示
            if len(exts) > 1:
                ext_tip = f"⚠️ 发现多种格式: {', '.join(exts)}"
            else:
                ext_tip = f"格式: {exts[0]}"

            print(f"  🟢 {name}")
            print(f"     [{ext_tip}] (共 {len(matches)} 个文件)")
            
            for f in matches:
                # 显示相对路径，这样能清楚看到是在哪个子文件夹
                rel_path = f.relative_to(target_folder)
                size = format_size(f.stat().st_size)
                print(f"     📄 {rel_path}  ({size})")

    # 2. 详细 - 缺失的文件
    if missing_list:
        print(f"\n{'─'*65}")
        print(f"❌ 缺失的文件 (文件夹及子文件夹中均未找到):")
        print(f"{'─'*65}")
        for name in missing_list:
            print(f"  🔴 {name}")

    # 3. 生成 TXT 报告
    report_path = target_folder / "文件核对报告.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("📂 文件核对报告\n")
        f.write(f"总计检查: {len(filenames)} 个 | 找到: {len(found_list)} 个 | 缺失: {len(missing_list)} 个\n")
        f.write("=" * 60 + "\n\n")
        
        if missing_list:
            f.write("【❌ 缺失文件】\n")
            for name in missing_list:
                f.write(f"  - {name}\n")
            f.write("\n")
            
        if found_list:
            f.write("【✅ 已找到文件】\n")
            for item in found_list:
                f.write(f"  [{item['name']}] 格式: {', '.join(item['exts'])}\n")
                for m in item['matches']:
                    f.write(f"    -> {m.relative_to(target_folder)}\n")
            f.write("\n")

    print(f"\n💾 详细报告已保存至: {report_path.resolve()}")
    print("=" * 65)

if __name__ == "__main__":
    main()
