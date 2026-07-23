#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
一键更新 Quartz 本地预览（并预留 GitHub 推送代码）
使用前请确保已在项目根目录下运行过 `npm install`
"""

import subprocess
import os
import sys

# === 直接指定 Quartz 项目路径 ===
PROJECT_ROOT = r"E:\图书馆\quartz"
os.chdir(PROJECT_ROOT)

def run_command(cmd, capture=True):
    """运行命令，打印输出"""
    print(f">>> {' '.join(cmd)}")
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result
    else:
        return subprocess.run(cmd)

def main():
    print("🚀 开始更新 Quartz 网站...\n")

    # 1. 执行构建（会重新复制原始库内容并生成 public）
    build_result = run_command(['npx', 'quartz', 'build'])
    if build_result.returncode != 0:
        print("\n❌ 构建失败，请检查错误信息。")
        sys.exit(1)
    else:
        print("\n✅ 构建成功！本地预览已更新。")
        print("   → 如果已启动预览服务器（如 python -m http.server），请刷新浏览器。")
        print("   → 若未启动，可运行：cd public && python -m http.server 3000\n")

    # ===================================================================
    # 2. （预留）推送到 GitHub 的代码
    #    当您审核完所有内容，确认无误后，可取消下方注释，然后运行此脚本
    #    即可同时完成构建和推送上线。
    # ===================================================================

    # print("📤 准备推送到 GitHub...")
    # 
    # # 添加所有更改
    # add_result = run_command(['git', 'add', '.'])
    # if add_result.returncode != 0:
    #     print("❌ git add 失败")
    #     sys.exit(1)
    # 
    # # 提交（可修改提交信息）
    # commit_msg = "自动更新网站内容 " + __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # commit_result = run_command(['git', 'commit', '-m', commit_msg])
    # if commit_result.returncode != 0:
    #     print("⚠️  提交可能失败（若无更改则忽略）")
    # 
    # # 推送到远程 v5 分支
    # push_result = run_command(['git', 'push', 'origin', 'v5'])
    # if push_result.returncode != 0:
    #     print("❌ 推送失败")
    #     sys.exit(1)
    # 
    # print("✅ 已推送到 GitHub，等待 Actions 自动部署...")

if __name__ == "__main__":
    main()