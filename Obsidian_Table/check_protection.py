import os

# 将这里改成你的 Obsidian 仓库路径，或者保持 '.'（当前目录）
VAULT_PATH = r'E:\图书馆\ROSA'

def check_files():
    unprotected_files = []
    
    for root, dirs, files in os.walk(VAULT_PATH):
        # 跳过隐藏目录
        if '.obsidian' in root or '.git' in root:
            continue
            
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 核心检查逻辑：
                    # 1. 文件里有表格（包含 |）
                    # 2. 但没有保护标记（<!-- no-convert -->）
                    if '|' in content and '<!-- no-convert -->' not in content:
                        unprotected_files.append(file_path)
                except Exception as e:
                    print(f"⚠️ 读取失败（跳过）: {file_path}，错误: {e}")
    
    # 输出结果
    if not unprotected_files:
        print("🎉 太棒了！所有包含表格的文件都已添加保护标记。")
    else:
        print(f"⚠️ 以下 {len(unprotected_files)} 个文件包含表格但未受保护：\n")
        for f in unprotected_files:
            print(f"  - {f}")
        print("\n💡 请打开上述文件，在末尾添加: <!-- no-convert -->")

if __name__ == "__main__":
    check_files()