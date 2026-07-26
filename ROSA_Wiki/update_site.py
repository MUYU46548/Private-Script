#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Quartz 自动构建与预览工具
用法: python update_site.py [--serve] [--push] [--port PORT] [--path PATH] [--help]
监听文件变化自动热重载：npx quartz build --serve
"""

import subprocess
import sys
import os
import argparse
import webbrowser
import time
from pathlib import Path
import datetime

# ===== 默认配置 =====
DEFAULT_PROJECT_ROOT = r"E:\图书馆\quartz"          # 默认项目路径
DEFAULT_PORT = 8080                                # 预览服务器端口
DEFAULT_BRANCH = "v5"                              # Git 分支名


def find_quartz_root():
    """自动检测 Quartz 项目根目录（优先环境变量，其次当前目录）"""
    # 1. 检查环境变量
    env_root = os.environ.get("QUARTZ_ROOT")
    if env_root and os.path.exists(os.path.join(env_root, "quartz.config.yaml")):
        return env_root

    # 2. 检查当前目录
    if os.path.exists("quartz.config.yaml"):
        return os.getcwd()

    # 3. 返回默认路径（用户可后续用 --path 覆盖）
    return DEFAULT_PROJECT_ROOT


def run_command(cmd, cwd=None, verbose=False):
    """
    执行系统命令，实时打印输出，返回 (返回码, 输出文本)
    """
    print(f"\n>>> 执行: {cmd}")
    if cwd:
        print(f"    工作目录: {cwd}")

    # 使用 Popen 实时输出
    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    output_lines = []
    for line in process.stdout:
        print(line, end='')          # 实时打印
        output_lines.append(line)

    process.wait()
    return process.returncode, ''.join(output_lines)


def check_dependencies():
    """检查 node, npx, python 是否可用"""
    deps = {
        "node": "node --version",
        "npx": "npx --version",
        "python": "python --version"
    }
    missing = []
    for name, cmd in deps.items():
        try:
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            missing.append(name)
    if missing:
        print(f"❌ 错误: 缺少依赖: {', '.join(missing)}")
        print("   请确保已安装 Node.js 和 Python，并已添加到 PATH。")
        return False
    return True


def build_quartz(project_root, verbose=False):
    """执行 npx quartz build"""
    print("\n🚀 开始构建 Quartz ...")
    cmd = "npx quartz build"
    if verbose:
        cmd += " --verbose"
    return run_command(cmd, cwd=project_root, verbose=verbose)


def start_preview_server(public_dir, port, open_browser=True):
    """启动 Python HTTP 服务器，在后台预览 public 目录"""
    if not os.path.exists(public_dir):
        print(f"❌ 错误: public 目录不存在: {public_dir}")
        return False

    print(f"\n🌐 启动预览服务器（端口 {port}）...")
    
    # Windows 下打开新 CMD 窗口运行
    if sys.platform == "win32":
        cmd = f'start cmd /k "cd /d {public_dir} && python -m http.server {port}"'
        try:
            subprocess.Popen(cmd, shell=True)
            print(f"✅ 预览服务器已启动，访问 http://localhost:{port}")
            if open_browser:
                webbrowser.open(f"http://localhost:{port}")
            return True
        except Exception as e:
            print(f"❌ 启动预览服务器失败: {e}")
            return False
    else:
        # Linux/macOS：提示用户手动启动（或使用 xdg-open）
        print("📢 请在另一个终端执行以下命令启动预览：")
        print(f"    cd {public_dir} && python -m http.server {port}")
        # 可选：尝试自动打开浏览器
        if open_browser:
            webbrowser.open(f"http://localhost:{port}")
        return True

def git_push(project_root, branch):
    """提交 public 目录到 Git"""
    print(f"\n📤 开始 Git 推送（分支 {branch}）...")

    git_dir = os.path.join(project_root, ".git")
    if not os.path.exists(git_dir):
        print("⚠️  当前目录不是 Git 仓库，跳过推送")
        return False

    # 用 Python 生成时间戳，彻底兼容 Windows / Linux / macOS
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"自动构建更新 [{timestamp}]"

    commands = [
        "git add public",           # 只添加 public 目录
        f'git commit -m "{commit_msg}"',
        f"git push origin {branch}"
    ]

    for cmd in commands:
        ret, output = run_command(cmd, cwd=project_root)
        if ret != 0:
            # 如果是因为没有变更而失败，不算错误
            if "nothing to commit" in output or "no changes" in output:
                print("ℹ️ 没有内容变更，跳过提交")
                return True
            print(f"❌ Git 命令失败: {cmd}")
            return False

    print("✅ Git 推送完成")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Quartz 自动构建与预览工具",
        epilog="示例: python update_site.py --serve --push"
    )
    parser.add_argument(
        "--serve", "-s",
        action="store_true",
        help="构建后自动启动预览服务器"
    )
    parser.add_argument(
        "--push", "-p",
        action="store_true",
        help="构建后推送到 Git（默认分支 v5）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"预览服务器端口（默认 {DEFAULT_PORT}）"
    )
    parser.add_argument(
        "--path",
        type=str,
        help="Quartz 项目根目录（默认自动检测）"
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=DEFAULT_BRANCH,
        help=f"Git 分支名（默认 {DEFAULT_BRANCH}）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细的构建日志"
    )
    args = parser.parse_args()

    # ------ 确定项目根目录 ------
    if args.path:
        project_root = args.path
    else:
        project_root = find_quartz_root()

    # 验证目录有效性
    config_file = os.path.join(project_root, "quartz.config.yaml")
    if not os.path.exists(config_file):
        print(f"❌ 错误: 在 {project_root} 找不到 quartz.config.yaml")
        print("   请指定正确的项目路径，或设置环境变量 QUARTZ_ROOT")
        sys.exit(1)

    print(f"📁 Quartz 项目根目录: {project_root}")

    # ------ 检查依赖 ------
    if not check_dependencies():
        sys.exit(1)

    # ------ 执行构建 ------
    ret, _ = build_quartz(project_root, args.verbose)
    if ret != 0:
        print("\n❌ 构建失败，退出")
        sys.exit(1)

    print("\n✅ 构建成功！")

    # ------ Git 推送（可选） ------
    if args.push:
        git_push(project_root, args.branch)

    # ------ 启动预览服务器（可选） ------
    if args.serve:
        public_dir = os.path.join(project_root, "public")
        if not os.path.exists(public_dir):
            print(f"❌ 错误: 找不到 public 目录: {public_dir}")
            sys.exit(1)
        start_preview_server(public_dir, args.port, open_browser=True)
        # 保持脚本运行，等待用户按键（以便看到输出）
        print("\n按任意键退出脚本（预览服务器将继续在后台运行）...")
        input()
    else:
        print("\n🎉 完成！")
        print("   要启动预览，请运行: python update_site.py --serve")
        print("   或手动进入 public 目录运行: python -m http.server")


if __name__ == "__main__":
    main()