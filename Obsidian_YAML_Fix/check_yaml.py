import frontmatter
from pathlib import Path

VAULT_PATH = Path("E:/图书馆/ROSA/")  # 修改为你的实际路径

bad_files = []
for md_file in VAULT_PATH.rglob("*.md"):
    try:
        # 尝试加载，如果有 YAML 语法错误会抛出异常
        post = frontmatter.load(md_file)
        # 同时检查 publish 字段是否确实是布尔值，以防万一
        if 'publish' in post.metadata and not isinstance(post.metadata['publish'], bool):
            bad_files.append((md_file, "publish 字段不是布尔值"))
    except Exception as e:
        bad_files.append((md_file, str(e)))

if bad_files:
    print("发现以下文件存在问题：")
    for f, reason in bad_files:
        print(f"{f}  ——  {reason}")
else:
    print("所有文件解析正常，没有 YAML 错误。")