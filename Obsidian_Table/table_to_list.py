import os
import re

VAULT_PATH = r'E:\图书馆\ROSA'  # 你的库路径

def convert_table_to_list(content):
    lines = content.split('\n')
    new_lines = []
    table_buffer = []
    
    def flush_table():
        nonlocal table_buffer
        if not table_buffer:
            return
        
        try:
            # 单列
            if len(table_buffer[0]) == 1:
                for row in table_buffer:
                    # 【修复】即使内容为空，也生成列表项，保留占位
                    new_lines.append(f"- {row[0].strip()}")
            
            # 两列（忽略表头）
            elif len(table_buffer[0]) == 2:
                start = 1 if len(table_buffer) > 1 else 0
                for row in table_buffer[start:]:
                    if len(row) == 2:
                        k = row[0].strip()
                        v = row[1].strip()
                        # 【修复】去掉了 'if k and v' 条件，强制生成列表项
                        # 即使键或值为空，也会生成 "- ：" 或 "- 名称："
                        new_lines.append(f"- {k}：{v}")
            
            # 多列（忽略表头）
            else:
                start = 1 if len(table_buffer) > 1 else 0
                for row in table_buffer[start:]:
                    # 【修复】保留所有单元格，包括空字符串
                    # 将空单元格原样保留为空白，并用 '/' 连接
                    clean_row = [c.strip() for c in row]  # 不再过滤空值
                    if len(clean_row) > 0:  # 只要行存在就输出
                        new_lines.append(f"- {' / '.join(clean_row)}")
        except Exception:
            # 转换异常则保留原始表格（安全兜底）
            for row in table_buffer:
                if isinstance(row, list):
                    new_lines.append('| ' + ' | '.join(row) + ' |')
                else:
                    new_lines.append(row)
        table_buffer = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            # 跳过分隔行 (|---|---|)
            if re.fullmatch(r'^[\|\s\-:]+$', stripped) and '---' in stripped:
                continue
            # 提取单元格（忽略空单元格）
            cells = [c.strip() for c in stripped[1:-1].split('|')]
            table_buffer.append(cells)
        else:
            if table_buffer:
                flush_table()
            new_lines.append(line)
    # 处理文件末尾的表格
    if table_buffer:
        flush_table()
    
    return '\n'.join(new_lines)

# 主程序
print("🔍 开始扫描文件...")
total = 0
converted = 0

for root, dirs, files in os.walk(VAULT_PATH):
    # 跳过 Obsidian 系统目录
    if '.obsidian' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.md'):
            total += 1
            file_path = os.path.join(root, file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 跳过含有保护注释的文件
            if '<!-- no-convert -->' in content:
                continue
            
            if '|' in content:
                new_content = convert_table_to_list(content)
                if new_content != content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"✅ 已转换: {file}")
                    converted += 1

print(f"\n📁 共扫描 {total} 个 .md 文件，实际转换 {converted} 个。")