#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hermes cron 包装：调用 Obsidian 维护总线（--brief 精简模式）。
供 cron no_agent 任务使用；stdout 即投递内容（仅执行状态+报告路径）。
"""

import sys
import runpy
from pathlib import Path

MAIN = Path(r"E:/CODE/CangKu/Python_Workspace/Obsidian_Maintenance/maintenance_runner.py")

if __name__ == "__main__":
    sys.argv = ["maintenance_runner.py", "--brief"]
    runpy.run_path(str(MAIN), run_name="__main__")
