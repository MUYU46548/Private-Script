#!/usr/bin/env python3
"""
阿里云万相 wan2.2-t2i-plus 文生图脚本
使用 DashScope API 异步调用
"""

import os
import time
import json
import requests
from datetime import datetime

# ================== 配置区域 ==================
# 你的 API Key 已配置在环境变量 DASHSCOPE_API_KEY 中
API_KEY = os.environ.get("DASHSCOPE_API_KEY")
if not API_KEY:
    raise ValueError("❌ 请先设置环境变量 DASHSCOPE_API_KEY")

# 模型名称
MODEL = "wan2.2-t2i-plus"

# API 端点（使用华北2（北京）地域，如使用其他地域请自行修改）
# 推荐使用业务空间专属域名，将 {WorkspaceId} 替换为你的实际ID[reference:2]
# BASE_URL = "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com"
BASE_URL = "https://ws-jpfxicqpptynsgny.cn-beijing.maas.aliyuncs.com"

# 提交任务和查询任务的 API 路径
SUBMIT_URL = f"{BASE_URL}/api/v1/services/aigc/text2image/image-synthesis"
TASK_URL = f"{BASE_URL}/api/v1/tasks"

# ================== 保存路径配置 ==================
# 自动获取当前系统的"下载"文件夹路径
DOWNLOAD_FOLDER = os.path.expanduser("~/Downloads")

OUTPUT_DIR = DOWNLOAD_FOLDER

# ================== 辅助函数 ==================

def ensure_output_dir():
    """确保输出目录存在"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📁 创建目录: {OUTPUT_DIR}")

def download_image(url, prompt="image", index=1):
    """下载图片到本地"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 用提示词前20个字符作为文件名的一部分
        safe_prompt = "".join(c if c.isalnum() or c in "_-" else "_" for c in prompt[:20])
        # 添加序号，防止同一秒内下载的多张图片互相覆盖
        filepath = os.path.join(OUTPUT_DIR, f"{timestamp}_{index:02d}.png")

        print(f"⬇️  正在下载: {url[:80]}...")
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"✅ 图片已保存: {filepath} ({len(resp.content) // 1024} KB)")
            return filepath
        else:
            print(f"❌ 下载失败，状态码: {resp.status_code}")
            return None
    except Exception as e:
        print(f"❌ 下载异常: {e}")
        return None

# ================== 核心 API 调用函数 ==================

def submit_task(prompt, size="1024*1024", n=1, negative_prompt=None):
    """
    提交文生图异步任务
    """
    print(f"\n🚀 提交任务...")
    print(f"   📝 提示词: {prompt}")
    print(f"   📐 尺寸: {size}")
    print(f"   🔢 数量: {n}")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"
    }

    payload = {
        "model": MODEL,
        "input": {"prompt": prompt},
        "parameters": {"size": size, "n": n}
    }
    if negative_prompt:
        payload["parameters"]["negative_prompt"] = negative_prompt

    try:
        response = requests.post(SUBMIT_URL, headers=headers, json=payload, timeout=30)
        
        # ========== 🔥 新增：打印详细的原始响应 ==========
        print(f"   📡 HTTP 状态码: {response.status_code}")
        
        # 尝试获取响应内容（如果是图片流或二进制，只打印前500个字符）
        raw_content = response.text[:500] if response.text else "[空响应]"
        print(f"   📄 原始响应内容: {raw_content}")
        # ===============================================

        # 如果状态码不是 200，直接报错
        if response.status_code != 200:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            return None

        # 尝试解析 JSON
        result = response.json()
        
        task_id = result.get("output", {}).get("task_id")
        if task_id:
            print(f"✅ 任务提交成功，任务ID: {task_id}")
            return task_id
        else:
            print(f"❌ 响应中未找到 task_id")
            print(f"   完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求异常: {e}")
        return None
    except ValueError as e:
        print(f"❌ JSON 解析异常: {e}")
        print(f"   服务器返回的不是 JSON，请检查以上原始内容")
        return None

def check_task(task_id):
    """查询任务状态"""
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    url = f"{TASK_URL}/{task_id}"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        result = response.json()

        if response.status_code != 200:
            print(f"❌ 查询失败，状态码: {response.status_code}")
            print(f"   错误信息: {result.get('message', '未知错误')}")
            return None

        status = result.get("output", {}).get("task_status")
        # 有些版本可能使用不同的字段名
        if not status:
            status = result.get("output", {}).get("status")

        return result
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        return None

def wait_for_task(task_id, max_wait=180, poll_interval=3):
    """
    轮询等待任务完成（静默模式）
    """
    print(f"\n⏳ 任务处理中", end="", flush=True)
    
    start_time = time.time()
    while True:
        elapsed = int(time.time() - start_time)
        if elapsed > max_wait:
            print(f"\n❌ 等待超时 ({max_wait} 秒)")
            return None

        result = check_task(task_id)
        if result is None:
            time.sleep(poll_interval)
            continue

        status = result.get("output", {}).get("task_status")
        if not status:
            status = result.get("output", {}).get("status")

        # 只在状态变化时打印一次，而不是每秒都打
        if status == "SUCCEEDED":
            print(f"\n✅ 任务完成！(耗时 {elapsed} 秒)")
            return result
        elif status == "FAILED":
            error_msg = result.get("output", {}).get("message", "未知错误")
            print(f"\n❌ 任务失败: {error_msg}")
            return None
        elif status in ["PENDING", "RUNNING"]:
            # 静默等待，不刷屏
            time.sleep(poll_interval)
        else:
            print(f"\n⚠️  未知状态: {status}")
            time.sleep(poll_interval)

    return None

# ================== 主函数 ==================

def generate_image(prompt, size="1024*1024", n=1, negative_prompt=None):
    """
    完整的文生图流程：提交 -> 等待 -> 下载
    """
    ensure_output_dir()

    task_id = submit_task(prompt, size, n, negative_prompt)
    if not task_id:
        return None

    result = wait_for_task(task_id)
    if not result:
        return None

    results = result.get("output", {}).get("results", [])
    print(f"📦 实际生成图片数: {len(results)} / 请求数: {n}")

    if not results:
        print("❌ 未找到生成的图片")
        return None

    downloaded = []
    for i, item in enumerate(results):
        url = item.get("url")
        if not url:
            print(f"⚠️  第 {i+1} 张图片缺少 URL，跳过")
            continue

        print(f"\n🖼️  第 {i+1} 张图片:")
        # 关键：传递 index=i+1
        filepath = download_image(url, prompt, index=i+1)
        if filepath:
            downloaded.append(filepath)
        else:
            print(f"⚠️  第 {i+1} 张图片下载失败")

    print(f"\n🎉 成功下载 {len(downloaded)} 张图片")
    return downloaded

# ================== 运行示例 ==================

if __name__ == "__main__":
    # ===== OC 人物设定示例 =====
    prompt = """一位黑发少女的动漫角色设定图，平涂风格，短发及耳，清爽直发，发梢泛起淡蓝色微光，棕黄色眼眸映着星光，眼神沉静而疏离。
    身穿明制汉服，宽袖长袄，象牙白面料，领缘和袖口绣有暗银色云纹，领口用细带系结。下配一条深红色的织金马面裙，裙面平整宽大，裙门处绣有精致的五角星和缠枝花纹。
    她穿着黑色皮鞋，站在古镇长桥上，背景是青山与黑瓦白墙。
    风吹起披帛和发梢，画面呈广角全景，色彩以紫、蓝、粉白为主，氛围唯美飘渺，自带仙气。"""

    # 负向提示词：排除不想要的元素
    negative_prompt = "低质量，模糊，变形，糟糕的构图，水印，文字，扭曲的肢体，扭曲的手，耳环，旗袍，民国装，修身旗袍，高开叉，立领，盘扣，侧开衩，过曝，偏色，杂线，粗糙阴影，写实风，3D感，肌肉过度，面容僵硬，多余人像"

    # 调用生成
    generate_image(
        prompt=prompt,
        size="1024*1024",      # 宽高均在 [512, 1440] 之间[reference:5]
        n=4,
        negative_prompt=negative_prompt
    )