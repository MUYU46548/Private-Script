import frontmatter
import os
from pathlib import Path

VAULT_PATH = Path("E:/图书馆/ROSA/")  # 替换为你的发布文件夹
DRY_RUN = False  # 先设为 True 预览，确认无误后改为 False

def process_file(filepath: Path):
    post = frontmatter.load(filepath)
    
    # 检查是否已有 publish 字段
    if 'publish' in post.metadata:
        return False  # 无需修改
    
    # 添加字段
    post.metadata['publish'] = True
    
    if DRY_RUN:
        print(f"[预览] 将修改: {filepath}")
        # 显示修改后的 front matter 预览
        print(frontmatter.dumps(post))
        print("---")
    else:
        # 真正写入文件
        frontmatter.dump(post, filepath)
        print(f"[修改] {filepath}")
    return True

def main():
    md_files = list(VAULT_PATH.rglob("*.md"))
    modified = 0
    for f in md_files:
        if process_file(f):
            modified += 1
    print(f"处理完成，修改了 {modified} 个文件。")

if __name__ == "__main__":
    main()