#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿里云百炼 qwen-image-max-2025-12-30 文生图 - 同步调用脚本
解决 "current user api does not support asynchronous calls" 403 错误
"""

import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path

# ==================== 配置区 ====================
WORKSPACE_ID = "ws-jpfxicqpptynsgny"  # ⚠️ 替换为你的 Workspace ID
API_KEY = os.environ.get("DASHSCOPE_API_KEY", "your-dashscope-api-key")
MODEL_NAME = "qwen-image-max-2025-12-30"
TIMEOUT = 180  # 生图超时（秒），高分辨率建议设大
# ================================================

def get_windows_download_folder() -> Path:
    """获取 Windows 默认下载文件夹路径（兼容用户自定义路径）"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        download_path = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
        winreg.CloseKey(key)
        return Path(download_path)
    except Exception:
        # 回退方案：用户目录下的 Downloads
        return Path.home() / "Downloads"


def generate_unique_filename(folder: Path, prefix: str = "qwen_image", ext: str = ".png") -> Path:
    """
    生成不重复的文件名，防止覆盖
    命名格式: qwen_image_20260723_140125.png
    若已存在: qwen_image_20260723_140125_1.png, _2.png, _3.png ...
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{prefix}_{timestamp}"
    
    candidate = folder / f"{base_name}{ext}"
    counter = 1
    
    while candidate.exists():
        candidate = folder / f"{base_name}_{counter}{ext}"
        counter += 1
    
    return candidate


def download_image(url: str, save_path: Path) -> bool:
    """流式下载图片到本地"""
    try:
        print(f"⬇️  正在下载: {url}")
        print(f"📁 保存路径: {save_path}")
        
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        
        # 流式写入，适合大文件
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size_mb = save_path.stat().st_size / (1024 * 1024)
        print(f"✅ 下载完成！文件大小: {file_size_mb:.2f} MB")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 下载失败: {e}")
        return False


def call_qwen_image_sync(prompt: str, negative_prompt: str = "", size: str = "2048*2048") -> dict:
    """同步调用百炼文生图 API"""
    
    url = f"https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": MODEL_NAME,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ]
                }
            ]
        },
        "parameters": {
            "negative_prompt": negative_prompt,
            "prompt_extend": True,
            "watermark": False,
            "size": size
        }
    }
    
    print(f"🔄 正在同步调用 {MODEL_NAME} ...")
    print(f"📐 分辨率: {size}")
    print(f"⏱️  超时设置: {TIMEOUT}s")
    print("-" * 50)
    
    response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    
    return response.json()


def extract_image_urls(result: dict) -> list:
    """从返回结果中提取所有图片 URL"""
    urls = []
    
    # 尝试多种可能的返回结构
    # 结构1: output.choices[].message.content[].image
    if "output" in result:
        output = result["output"]
        if "choices" in output:
            for choice in output["choices"]:
                contents = choice.get("message", {}).get("content", [])
                for item in contents:
                    if isinstance(item, dict) and "image" in item:
                        urls.append(item["image"])
        
        # 结构2: output.results[].url
        if "results" in output:
            for item in output["results"]:
                if "url" in item:
                    urls.append(item["url"])
    
    # 结构3: 顶层 results
    if "results" in result:
        for item in result["results"]:
            if "url" in item:
                urls.append(item["url"])
    
    return urls


def main():
    # ==================== Prompt 配置 ====================
    prompt = (
        # ---- 风格锚定（权重最高，必须放最前面）----
        "日系赛璐璐动画风格，2D手绘插画，平涂色块，清晰黑色描线，硬边阴影，无渐变，"
        "京都动画画风，芳文社日常系，TV动画截图质感，"
        # ---- 主体 ----
        "紫色长发少女，全身像，紫色瞳孔，大眼睛，"
        "身穿白色连衣裙，头戴白色太阳帽，裙摆微扬，"
        "表情温柔，单手轻提裙摆，另一手自然下垂，"
        # ---- 场景 ----
        "背景是欧式庭院，青砖地面，喷泉，翠竹掩映，石灯笼，"
        "晴天，明亮的自然光，光影分界清晰，"
        # ---- 画面质感 ----
        "高饱和度色彩，干净的色块填充，无噪点，无纹理，"
        "线条锐利，边缘清晰，纯2D平面渲染，"
        "动画原画级别，高质量作画"
    )

    negative_prompt = (
        # ---- 封杀3D/写实/蜡像 ----
        "3D渲染，3D建模，CG渲染，写实风格，真实照片，真人，照片级，"
        "蜡像感，塑料质感，过度光滑，皮肤反光，次表面散射，"
        "柔和渐变阴影，环境光遮蔽，全局光照，光线追踪，"
        # ---- 封杀AI通病 ----
        "低分辨率，低画质，模糊，噪点，JPEG压缩伪影，"
        "肢体畸形，手指畸形，多余手指，扭曲的肢体，"
        "面容僵硬，表情不自然，死鱼眼，"
        # ---- 封杀不需要的元素 ----
        "画面过饱和，构图混乱，水印，文字，签名，"
        "散景，景深模糊，镜头光晕，"
        "肌肉过度，多余人像，"
        # ---- 封杀半写实/厚涂 ----
        "半写实，2.5D，厚涂，油画质感，水彩晕染，"
        "虚幻引擎，Unity渲染，Blender渲染，"
        "电影级光影，体积光，丁达尔效应"
    )
    # ====================================================
    try:
        # 1️⃣ 同步调用生图 API
        result = call_qwen_image_sync(
            prompt=prompt,
            negative_prompt=negative_prompt,
            size="1664*928"
        )
        
        print("\n📋 API 返回：")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 50)
        
        # 2️⃣ 提取图片链接
        image_urls = extract_image_urls(result)
        
        if not image_urls:
            print("⚠️  未从返回结果中解析到图片 URL，请检查返回结构。")
            return
        
        print(f"🖼️  共获取到 {len(image_urls)} 张图片")
        
        # 3️⃣ 获取 Windows 下载文件夹
        download_folder = get_windows_download_folder()
        download_folder.mkdir(parents=True, exist_ok=True)  # 确保文件夹存在
        print(f"📂 下载目录: {download_folder}")
        print("-" * 50)
        
        # 4️⃣ 逐张下载（防重名）
        for i, img_url in enumerate(image_urls, 1):
            print(f"\n[{i}/{len(image_urls)}]")
            save_path = generate_unique_filename(
                folder=download_folder,
                prefix="qwen_image",
                ext=".png"
            )
            download_image(img_url, save_path)
        
        print("\n" + "=" * 50)
        print("🎉 全部完成！")
        
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时（{TIMEOUT}s），生图耗时过长，请增大 TIMEOUT 或降低分辨率")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误: {e.response.status_code}")
        print(f"   响应: {e.response.text}")
    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    main()
