"""
批量执行文生图脚本（text_to_image.py）
适用于后台跑图
"""

import os
import time
import random
import subprocess

# =========================================
# 唯一需要你修改的地方
# 改成你的生图脚本的完整路径（绝对路径）
your_script = r"E:\CODE\CangKu\Python_Workspace\Image\text_to_image.py"
# =========================================

# 获取脚本所在目录，作为工作目录
script_dir = os.path.dirname(your_script)

for i in range(3):  # 循环轮数，如填入10代表执行10轮，最终产出张数=循环轮数*生图脚本单批生成数
    print(f"\n{'='*50}")
    print(f"🔄 第 {i+1} 轮开始")
    print(f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*50)
    
    # 生成一个随机种子（虽然原脚本可能不用，但留着备用）
    seed = random.randint(1, 999999999)
    
    # 关键：用绝对路径 + 指定工作目录 + 继承完整环境变量
    result = subprocess.run(
        ["python", your_script],
        cwd=script_dir,                # 切换到脚本所在目录
        env=os.environ.copy(),         # 完整继承所有环境变量（含 API Key）
        capture_output=False,          # 让输出直接显示在终端
        text=True
    )
    
    # 检查执行结果
    if result.returncode == 0:
        print(f"✅ 第 {i+1} 轮执行成功")
    else:
        print(f"❌ 第 {i+1} 轮执行失败，退出码: {result.returncode}")

    time.sleep(20)  # 给服务器和本地足够的时间处理，单位：秒

print(f"\n🎉 全部 {i+1} 轮执行完成！")
