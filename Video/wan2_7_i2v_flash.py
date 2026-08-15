# -*- coding: utf-8 -*-
"""
Wan 2.7 图生视频（首帧生视频）示例
适用于：wan2.7-i2v-2026-04-25
"""
from http import HTTPStatus
from dashscope import VideoSynthesis
import dashscope
import os
import time
import requests
from pathlib import Path
from datetime import datetime

# ============================================================
# 🎬 在这里填写你的参数
# ============================================================

# -------- 必填参数 --------
IMAGE_PATH = "https://bee-reg-ab.imagency.cn/p/2301b7261df7698c03bdfbe6e8884da0.png"  # 首帧图片 URL
PROMPT = "镜头缓慢拉远，两人微笑着互相看了一眼，头发和衣服随呼吸轻微起伏。"

# -------- 可选参数 --------
MODEL_NAME = "wan2.7-i2v-2026-04-25"      # 固定为 2.7 图生视频模型
DURATION = 5                               # 视频时长（秒），2~15
RESOLUTION = "1080P"                        # 可选 "720P" 或 "1080P"
PROMPT_EXTEND = False                      # 是否开启提示词智能改写
WATERMARK = False                          # 是否加水印
SEED = None                                # 随机种子（可选）
NEGATIVE_PROMPT = "真人，3D，模糊，变形，低画质，多出的肢体，多余的手指，画面抖动。"                       # 反向提示词（可选）

# -------- SDK 配置 --------
# 根据你的业务空间所在地域填写对应的 URL：
# 华北2（北京）示例：
# dashscope.base_http_api_url = "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1"
# 新加坡示例：
# dashscope.base_http_api_url = "https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api/v1"
# 你原来的脚本用的是北京业务空间，下面按你原来的格式写一个例子：
DASHSCOPE_BASE_HTTP_API_URL = "https://ws-jpfxicqpptynsgny.cn-beijing.maas.aliyuncs.com/api/v1"

def get_api_key():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError(
            "未找到 DASHSCOPE_API_KEY 环境变量。\n"
            "请通过以下方式之一设置：\n"
            " 1. 系统环境变量：set DASHSCOPE_API_KEY=your_key\n"
            " 2. 临时设置：$env:DASHSCOPE_API_KEY='your_key' (PowerShell)"
        )
    return api_key

def generate_video_from_image_2_7(
    image_url: str,
    prompt: str = "",
    model: str = MODEL_NAME,
    duration: int = 5,
    resolution: str = RESOLUTION,
    seed: int = None,
    negative_prompt: str = "",
    prompt_extend: bool = PROMPT_EXTEND,
    watermark: bool = WATERMARK,
):
    """
    使用 Wan 2.7 图生视频（首帧生视频）生成视频
    """
    api_key = get_api_key()
    dashscope.base_http_api_url = DASHSCOPE_BASE_HTTP_API_URL

    # 构造 media 数组：仅首帧
    media = [
        {
            "type": "first_frame",
            "url": image_url
        }
    ]

    print(f"\n{'='*60}")
    print(f"正在创建 Wan 2.7 图生视频任务...")
    print(f"{'='*60}")
    print(f"模型: {model}")
    print(f"首帧图片: {image_url}")
    print(f"提示词: {prompt or '(无)'}")
    print(f"时长: {duration}秒")
    print(f"分辨率: {resolution}")
    print(f"{'='*60}\n")

    # 异步调用
    rsp = VideoSynthesis.async_call(
        api_key=api_key,
        model=model,
        media=media,
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        seed=seed,
        negative_prompt=negative_prompt,
        prompt_extend=prompt_extend,
        watermark=watermark,
    )

    if rsp.status_code != HTTPStatus.OK:
        print(f"❌ 任务创建失败！")
        print(f"状态码: {rsp.status_code}")
        print(f"错误码: {rsp.code}")
        print(f"错误信息: {rsp.message}")
        return None

    task_id = rsp.output.task_id
    task_status = rsp.output.task_status
    print(f"✅ 任务创建成功！")
    print(f"任务 ID: {task_id}")
    print(f"初始状态: {task_status}")

    # 简单轮询
    for _ in range(120):
        time.sleep(5)
        rsp = VideoSynthesis.fetch(
            api_key=api_key,
            task=task_id,
        )
        if rsp.status_code != HTTPStatus.OK:
            print(f"查询失败: {rsp.message}")
            continue
        status = rsp.output.task_status
        print(f"状态: {status}")
        if status == "SUCCEEDED":
            video_url = rsp.output.video_url
            print(f"\n✅ 视频生成成功！")
            print(f"视频 URL: {video_url}")
            return {
                "task_id": task_id,
                "video_url": video_url,
                "success": True
            }
        elif status == "FAILED":
            print(f"\n❌ 视频生成失败！")
            print(f"错误码: {rsp.output.code}")
            print(f"错误信息: {rsp.output.message}")
            return {
                "task_id": task_id,
                "video_url": None,
                "success": False
            }
        # 其他状态继续轮询

    print("轮询超时，请稍后通过 task_id 查询结果。")
    return {
        "task_id": task_id,
        "video_url": None,
        "success": False
    }

# ============================================================
# 主程序入口
# ============================================================
if __name__ == "__main__":
    result = generate_video_from_image_2_7(
        image_url=IMAGE_PATH,
        prompt=PROMPT,
        model=MODEL_NAME,
        duration=DURATION,
        resolution=RESOLUTION,
        seed=SEED,
        negative_prompt=NEGATIVE_PROMPT,
        prompt_extend=PROMPT_EXTEND,
        watermark=WATERMARK,
    )

    print(f"\n{'='*60}")
    print(f"📊 生成结果")
    print(f"{'='*60}")
    print(f"✅ 成功: {'是' if result['success'] else '否'}")
    print(f"🆔 任务ID: {result['task_id']}")
    print(f"🔗 视频URL: {result['video_url']}")
    print(f"{'='*60}")