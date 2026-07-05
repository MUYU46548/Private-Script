import os
import re
import yaml
from pathlib import Path

# ===== 配置区 =====
VAULT_PATH = r'E:\图书馆\ROSA'          # 当前目录，可改为绝对路径如 '/Users/name/Obsidian'
TAG_PATTERN = r'#([\w\u4e00-\u9fa5/\-\.\+]+)'  # 匹配 #标签，支持中文/英文/数字/-/./+/
# =================

def parse_frontmatter(content):
    """分离 frontmatter 和正文，返回 (frontmatter_dict, body_content)"""
    if not content.startswith('---'):
        return {}, content  # 没有 frontmatter

    # 匹配从开头到第二个 --- 之间的内容
    match = re.match(r'^---\n(.*?)\n---\n?', content, re.DOTALL)
    if not match:
        return {}, content

    yaml_str = match.group(1)
    rest = content[match.end():]  # 剩余正文

    try:
        fm_data = yaml.safe_load(yaml_str) or {}
        if not isinstance(fm_data, dict):
            fm_data = {}
    except yaml.YAMLError:
        # 如果YAML格式损坏，保留原字符串，后续只做追加不破坏
        fm_data = {'_raw_yaml': yaml_str}

    return fm_data, rest

def extract_tail_tags(body):
    lines = body.splitlines()
    removed_tags = []

    # 从末尾反向扫描纯标签行
    while lines:
        line = lines[-1].strip()
        if re.fullmatch(r'(#[\w\u4e00-\u9fa5/\-\.\+]+\s*)+', line):
            tags_in_line = re.findall(TAG_PATTERN, line)
            removed_tags.extend(tags_in_line)
            lines.pop()
        else:
            break

    # 删掉所有因移除标签而产生的尾部空行
    while lines and lines[-1].strip() == '':
        lines.pop()

    cleaned_body = '\n'.join(lines)
    return list(set(removed_tags)), cleaned_body

def merge_tags(existing_tags, new_tags):
    """合并标签，去重，并保证格式为列表"""
    if not existing_tags:
        existing_tags = []
    elif isinstance(existing_tags, str):
        # 如果是字符串 "tag1, tag2" 或 "tag1" 转为列表
        existing_tags = [t.strip() for t in existing_tags.split(',') if t.strip()]
    elif not isinstance(existing_tags, list):
        existing_tags = []

    # 合并并去重
    all_tags = list(set(existing_tags + new_tags))
    # 按字母排序（可选），让结果更美观
    all_tags.sort()
    return all_tags

def process_file(file_path):
    print(f"处理中: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. 解析现有 frontmatter
    fm_data, body = parse_frontmatter(content)

    # 2. 提取底部标签，并清理正文
    tail_tags, cleaned_body = extract_tail_tags(body)

    if not tail_tags:
        print(f"  └─ 无底部标签，跳过")
        return

    # 3. 合并标签
    existing_tags = fm_data.get('tags', [])
    merged_tags = merge_tags(existing_tags, tail_tags)

    # 4. 更新 frontmatter 字典
    fm_data['tags'] = merged_tags

    # 5. 重新构造 YAML 块
    # 如果原来有 _raw_yaml（解析失败），保留原样，只追加 tags（不破坏已有内容）
    if '_raw_yaml' in fm_data:
        raw = fm_data['_raw_yaml']
        # 如果原YAML没有tags，追加一行
        if 'tags:' not in raw:
            raw += f'\ntags: {merged_tags}'
        else:
            # 这里简单替换，更复杂的情况可以再做正则，但概率极低
            raw = re.sub(r'tags:.*', f'tags: {merged_tags}', raw)
        new_yaml_block = f"---\n{raw}\n---"
    else:
        # 正常使用 yaml.dump
        # 使用 default_flow_style=True 输出为行内数组 [a, b, c]
        yaml_str = yaml.dump(fm_data, allow_unicode=True, default_flow_style=True, sort_keys=False).strip()
        new_yaml_block = f"---\n{yaml_str}\n---"

    # 6. 拼接最终内容（保证尾部保留一个换行）
    new_content = new_yaml_block + '\n' + cleaned_body
    if not cleaned_body.endswith('\n'):
        new_content += '\n'

    # 7. 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  └─ 迁移成功！合并标签: {merged_tags}")

def main():
    # 遍历所有 .md 文件
    for root, _, files in os.walk(VAULT_PATH):
        # 忽略隐藏目录（如 .obsidian, .git）
        if any(part.startswith('.') for part in Path(root).parts):
            continue
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                process_file(file_path)

    print("\n🎉 全部处理完成！")

if __name__ == "__main__":
    main()