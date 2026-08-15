#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Obsidian 维护总线脚本
按序调用全部维护检测脚本，聚合输出总览（stdout 即投递内容，供 cron 直接使用）。
调用顺序：
  1. obsidian_change_logs.py      变更日志（唯一有副作用：写日志+基线）
  2. unidirectional_link_check.py 单向链接 + 断链
  3. placeholder_check.py         占位符
  4. mention_link_check.py        提及未链接
  5. publish_check.py             发布前检查
  6. image_link_check.py          图片引用断链
  7. link_refactor.py             断链修复建议（恒为 dry-run，绝不自动改文件）
  8. duplicate_note_check.py      近似重复
安全：link_refactor 始终不带 --apply，其余子脚本均为只读。
用法：
  python maintenance_runner.py [--vault ...] [--skip-changelog] [--quiet]
cron 用法（no_agent 模式）：script 指向本文件，stdout 自动投递。
"""

import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Windows 下 stdout 被 pipe 捕获时默认 GBK，强制 UTF-8 保证 cron 投递不乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# =========================================================
# 默认配置
# =========================================================
VAULT_PATH = r"E:/图书馆/ROSA"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent  # Python_Workspace/
REPORT_DIR = Path(VAULT_PATH) / "96 事务管理"
SUMMARY_PATH = REPORT_DIR / "Obsidian维护总览.md"

# (名称, 相对路径, 超时秒, 额外参数)
SCRIPTS = [
    ("变更日志",   "Automatically_Obtain_Change_Logs/obsidian_change_logs.py",   90,  []),
    ("单向链接",   "Unidirectional_Link_Check/unidirectional_link_check.py",     60,  []),
    ("占位符",     "Placeholder_Check/placeholder_check.py",                     60,  []),
    ("提及未链接", "Mention_Link_Check/mention_link_check.py",                   120, []),
    ("发布前检查", "Publish_Check/publish_check.py",                             30,  []),
    ("图片断链",   "Image_Link_Check/image_link_check.py",                       30,  []),
    ("断链修复建议", "Link_Refactor/link_refactor.py",                          120, []),
    ("近似重复",   "Duplicate_Note_Check/duplicate_note_check.py",               240, []),
]


# =========================================================
# 子脚本调用与指标解析
# =========================================================
def run_script(name: str, rel_path: str, timeout: int, extra: list, vault: str):
    """调用子脚本，返回 (ok, full_stdout, 摘要行)"""
    script = SCRIPTS_DIR / rel_path
    cmd = [sys.executable, str(script), "--vault", vault] + extra
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=env)
        out = proc.stdout or ""
        if proc.returncode != 0:
            return False, out, f"退出码 {proc.returncode}"
        # 摘要行：优先取含"检测完成"/"检测到"的指标行，否则取最后非空行
        lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("⚠")]
        summary = ""
        for l in lines:
            if "检测完成" in l or "检测到" in l or "首次运行" in l:
                summary = l
                break
        if not summary and lines:
            summary = lines[-1]
        return True, out, summary
    except subprocess.TimeoutExpired:
        return False, "", f"超时（{timeout}s）"
    except Exception as e:
        return False, "", f"异常：{e}"


def extract(pattern: str, text: str, group: int = 1, default=0):
    m = re.search(pattern, text)
    return int(m.group(group)) if m else default


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Obsidian 维护总线（聚合调用全部检测脚本）")
    parser.add_argument("--vault", default=VAULT_PATH)
    parser.add_argument("--skip-changelog", action="store_true", help="跳过变更日志脚本（调试）")
    parser.add_argument("--brief", action="store_true", help="精简输出：仅执行状态+报告路径（cron 投递用）")
    parser.add_argument("--quiet", action="store_true", help="精简输出")
    args = parser.parse_args()

    vault = str(Path(args.vault))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"📊 Obsidian 维护总览 {now}", "=" * 30]

    results = {}
    for name, rel, timeout, extra in SCRIPTS:
        if args.skip_changelog and "change_logs" in rel:
            continue
        ok, out, summary = run_script(name, rel, timeout, extra, vault)
        results[name] = {"ok": ok, "summary": summary, "out": out}
        status = "✅" if ok else "❌"
        lines.append(f"{status} {name}: {summary if ok else summary}")

    # 聚合关键指标（从子脚本完整 stdout 解析）
    def get(name):
        return results.get(name, {})

    # ---- 汇总行 ----
    lines.append("=" * 30)
    attention = []
    # 单向链接
    r = get("单向链接")
    if r.get("ok"):
        uni = extract(r"单向链接对: (\d+)", r["out"])
        broken = extract(r"断链\(需创建\): (\d+)", r["out"])
        lines.append(f"🔗 单向链接：{uni} 对 / 断链 {broken}")
        if uni > 0:
            attention.append(f"单向链接 {uni} 对需补反向链接；断链 {broken} 个待创建页")
    # 占位符
    r = get("占位符")
    if r.get("ok"):
        m = re.search(r"(\d+) 个文件含占位符（共 (\d+) 条）", r["out"])
        if m:
            lines.append(f"🏷️ 占位符：{m.group(1)} 文件 / {m.group(2)} 条")
            if int(m.group(2)) > 0:
                attention.append(f"占位符 {m.group(2)} 条待清理")
    # 提及
    r = get("提及未链接")
    if r.get("ok"):
        n = extract(r"首次提及未链接文件: (\d+)", r["out"])
        lines.append(f"🔗 提及未链接：{n} 文件")
        if n > 0:
            attention.append(f"提及未链接 {n} 文件待补首次链接")
    # 发布
    r = get("发布前检查")
    if r.get("ok"):
        m = re.search(r"(\d+) 通过，(\d+) 存在问题", r["out"])
        if m:
            lines.append(f"📋 发布前检查：{m.group(1)} 通过 / {m.group(2)} 问题")
            if int(m.group(2)) > 0:
                attention.append(f"发布前检查 {m.group(2)} 个问题")
    # 图片
    r = get("图片断链")
    if r.get("ok"):
        n = extract(r"缺失 (\d+) 个", r["out"])
        lines.append(f"🖼️ 图片断链：{n} 缺失")
        if n > 0:
            attention.append(f"图片断链 {n} 个")
    # 断链修复建议
    r = get("断链修复建议")
    if r.get("ok"):
        m = re.search(r"断链 (\d+)，建议 (\d+)，可执行 (\d+)", r["out"])
        if m:
            lines.append(f"🔧 断链修复建议：{m.group(2)} 建议 / {m.group(3)} 可执行")
            if int(m.group(2)) > 0:
                attention.append(f"断链修复建议 {m.group(2)} 条（仅建议，需人工判断，勿直接 --apply）")
    # 近似重复
    r = get("近似重复")
    if r.get("ok"):
        n = extract(r"近似重复对 (\d+)", r["out"])
        lines.append(f"👯 近似重复：{n} 对")
        if n > 0:
            attention.append(f"近似重复 {n} 对需核对")

    lines.append("=" * 30)
    if attention:
        lines.append("⚠️ 需人工关注：")
        for a in attention:
            lines.append(f"  - {a}")
    else:
        lines.append("✅ 全库健康，无需人工关注")
    lines.append(f"📄 详细报告目录：`{REPORT_DIR}`")

    # 失败汇总
    failed = [n for n, r in results.items() if not r["ok"]]
    if failed:
        lines.append(f"❌ 执行失败：{'、'.join(failed)}（详见上方）")

    # ---- cron 精简模式：仅执行状态 + 报告路径 ----
    if args.brief:
        brief = []
        ok_all = not failed
        brief.append(f"📊 Obsidian 维护{'完成' if ok_all else '部分失败'} {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        brief.append(f"{'✅' if ok_all else '⚠️'} {len(results) - len(failed)}/{len(results)} 个脚本执行成功")
        if failed:
            for n in failed:
                r = results[n]
                brief.append(f"❌ {n}: {r['summary']}")
        brief.append("📄 报告目录：`E:/图书馆/ROSA/96 事务管理/`")
        report_files = sorted(p.name for p in REPORT_DIR.glob("*.md") if "维护总览" not in p.name)
        for fn in report_files:
            brief.append(f"   - {fn}")
        output = "\n".join(brief)
    else:
        output = "\n".join(lines)

    # 写总览文件（供本地查阅）
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "Obsidian维护总览.md").write_text(
            f"# 📊 Obsidian 维护总览\n\n> **生成时间**：{now}\n> **模式**：聚合只读检测（link_refactor 恒为 dry-run）\n\n```\n{output}\n```\n",
            encoding="utf-8")
    except Exception:
        pass

    print(output)
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
