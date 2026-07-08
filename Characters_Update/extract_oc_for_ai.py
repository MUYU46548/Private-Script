"""
角色文档分模块提取脚本
根据模块直接生成可用于通用AI的提示词
未达到预期，封存中
"""

import os
import re
import shutil
from pathlib import Path
from collections import defaultdict
from config import (
    OBSIDIAN_VAULT_PATH,
    CHARACTER_NAME,
    ALIASES,
    TEMPLATE_SECTIONS,
    OUTPUT_DIR
)

def load_all_notes(vault_path):
    """加载库中所有 Markdown 笔记"""
    notes = {}
    for root, _, files in os.walk(vault_path):
        for file in files:
            if file.endswith(".md"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                rel_path = os.path.relpath(path, vault_path)
                notes[rel_path] = content
    return notes

def is_relevant(content, names):
    """判断笔记是否提及角色（支持别名）"""
    text = content.lower()
    for name in names:
        if name.lower() in text:
            return True
    return False

def extract_contextual_snippets(content, filename, keywords, window_lines=3):
    """提取包含关键词的段落（带上下文）"""
    lines = content.split("\n")
    snippets = []
    keyword_set = set(kw.lower() for kw in keywords)
    
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in keyword_set):
            # 向前向后扩展 window_lines 行
            start = max(0, i - window_lines)
            end = min(len(lines), i + window_lines + 1)
            snippet = "\n".join(lines[start:end]).strip()
            if snippet and len(snippet) > 20:  # 过滤太短的
                snippets.append(f"<!-- 来源: {filename} -->\n{snippet}\n")
    return snippets

def main():
    # 清理输出目录
    out_dir = Path(OUTPUT_DIR)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(exist_ok=True)
    
    # 加载笔记
    print("正在加载 Obsidian 库...")
    all_notes = load_all_notes(OBSIDIAN_VAULT_PATH)
    
    # 筛选相关笔记
    relevant_notes = {
        name: content for name, content in all_notes.items()
        if is_relevant(content, [CHARACTER_NAME] + ALIASES)
    }
    print(f"找到 {len(relevant_notes)} 篇相关笔记")
    
    # 为每个模板章节提取片段
    section_snippets = defaultdict(list)
    all_names = [CHARACTER_NAME] + ALIASES
    
    for filename, content in relevant_notes.items():
        # 全局相关性：必须包含角色名
        if not is_relevant(content, all_names):
            continue
            
        for section, keywords in TEMPLATE_SECTIONS.items():
            snippets = extract_contextual_snippets(content, filename, keywords)
            section_snippets[section].extend(snippets)
    
    # 生成 Prompt 文件
    for section, snippets in section_snippets.items():
        if not snippets:
            snippets = ["（未找到相关内容）"]
        
        prompt_content = f"""你正在填写原创角色「{CHARACTER_NAME}」文档的“{section}”部分。
请基于以下来源材料，撰写一段连贯、准确、保留细节的内容。

【要求】：
- 忠实于原文，不编造设定
- 合并重复信息，消除矛盾（以最新事件为准）
- 保留关键细节、情感张力和复杂性
- 使用冷静、略带疏离感的第三人称叙述风格
- 如需引用具体事件，请用 [[笔记名]] 格式

【来源材料】：
{''.join(snippets[:50])}  <!-- 最多取前50段避免过长 -->

请直接输出该章节内容，不要包含解释、标题或注释。
"""
        # 保存 Prompt
        safe_name = re.sub(r'[^\w\-_\. ]', '_', section)
        with open(out_dir / f"{safe_name}.prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt_content)
    
    # 生成完整草案框架
    draft = f"# {CHARACTER_NAME}（AI辅助修订版）\n\n"
    for section in TEMPLATE_SECTIONS:
        draft += f"## {section}\n（待填充）\n\n"
    
    with open(out_dir / "FULL_DRAFT_TEMPLATE.md", "w", encoding="utf-8") as f:
        f.write(draft)
    
    print(f"\n✅ 完成！Prompt 文件已生成至: {OUTPUT_DIR}")
    print("下一步：")
    print("1. 打开每个 .prompt.txt 文件")
    print("2. 复制内容到 Qwen3-Max（或其他AI）")
    print("3. 将AI输出填入 FULL_DRAFT_TEMPLATE.md")

if __name__ == "__main__":
    main()
