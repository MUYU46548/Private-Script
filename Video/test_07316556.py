# -*- coding: utf-8 -*-
"""
图生视频脚本 - 完整版本
支持自定义时长、分辨率等参数
临时禁用代理提高稳定性
"""

import os
import requests
import json
import time

# ============================================================
# 配置区 - 在这里修改你的参数
# ============================================================
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-你的Key")  # ← 你的 API Key

# 视频参数配置
VIDEO_CONFIG = {
    "duration": 5,           # ← 视频时长（1-10秒）
    "resolution": "1080P",    # ← 分辨率：480P, 720P, 1080P
    "watermark": False,       # ← 是否添加水印
    "prompt_extend": False,   # ← 是否让AI扩展提示词
}

# 首帧图片URL
FIRST_FRAME_URL = "https://picgocloud.com/m/c0df5ba7-aec3-4ea6-afd6-6247a0769a85.png"

# 提示词
PROMPT = "镜头缓慢拉远，两人微笑着互相看了一眼，头发和衣服随呼吸轻微起伏。"
NEGATIVE_PROMPT = "真人，3D，模糊，变形，低画质，纪录片。"

# ============================================================
# 以下为函数定义，一般不需要修改
# ============================================================

BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
MODEL = "wan2.7-i2v-2026-04-25"
PROXIES = {"http": None, "https": None}  # 禁用代理

def create_video_task():
    """创建图生视频任务"""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"
    }
    
    payload = {
        "model": MODEL,
        "input": {
            "prompt": PROMPT,
            "negative_prompt": NEGATIVE_PROMPT,
            "media": [
                {"type": "first_frame", "url": FIRST_FRAME_URL}
            ]
        },
        "parameters": {
            "resolution": VIDEO_CONFIG["resolution"],
            "duration": VIDEO_CONFIG["duration"],      # ← 时长在这里
            "prompt_extend": VIDEO_CONFIG["prompt_extend"],
            "watermark": VIDEO_CONFIG["watermark"]
        }
    }
    
    print("=" * 60)
    print("🎬 创建图生视频任务")
    print("=" * 60)
    print(f"模型: {MODEL}")
    print(f"首帧图片: {FIRST_FRAME_URL}")
    print(f"提示词: {PROMPT}")
    print(f"时长: {VIDEO_CONFIG['duration']} 秒")
    print(f"分辨率: {VIDEO_CONFIG['resolution']}")
    print("=" * 60)
    
    try:
        resp = requests.post(
            BASE_URL, 
            headers=headers, 
            json=payload, 
            proxies=PROXIES,
            timeout=30
        )
        
        print(f"\n📡 HTTP 状态码: {resp.status_code}")
        
        data = resp.json()
        
        if "output" in data and "task_id" in data["output"]:
            task_id = data["output"]["task_id"]
            print(f"✅ 任务创建成功！ID: {task_id}")
            return task_id
        else:
            print("❌ 任务创建失败")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return None
            
    except Exception as e:
        print(f"❌ 异常: {type(e).__name__}: {e}")
        return None

def query_task_status(task_id, max_wait=600):
    """轮询查询任务状态"""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    query_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    
    print(f"\n⏱️  开始轮询任务状态（时长：{VIDEO_CONFIG['duration']}秒，预计生成时间：{VIDEO_CONFIG['duration']*10}秒左右）...")
    
    start_time = time.time()
    check_count = 0
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait:
            print(f"\n⏰ 超时！已等待 {max_wait} 秒")
            return None
        
        try:
            resp = requests.get(
                query_url, 
                headers=headers, 
                proxies=PROXIES,
                timeout=30
            )
            
            data = resp.json()
            output = data.get("output", {})
            status = output.get("task_status")
            
            check_count += 1
            elapsed_int = int(elapsed)
            print(f"  [{check_count}] 状态: {status} (已等待 {elapsed_int}秒)", end='\r')
            
            if status == "SUCCEEDED":
                video_url = output.get("video_url")
                print(f"\n\n✅ 视频生成成功！用时 {elapsed_int} 秒")
                print(f"视频 URL: {video_url}")
                return video_url
                
            elif status == "FAILED":
                code = output.get("code")
                message = output.get("message")
                print(f"\n\n❌ 任务失败: {code} - {message}")
                return None
                
            elif status in ("PENDING", "RUNNING"):
                time.sleep(5)
                continue
                
        except Exception as e:
            print(f"\n  查询异常: {e}")
            time.sleep(5)
            continue
    
    return None

def download_video(video_url, output_path):
    """下载视频到本地"""
    
    print(f"\n📥 正在下载视频到: {output_path}")
    
    try:
        resp = requests.get(
            video_url, 
            stream=True, 
            proxies=PROXIES,
            timeout=60
        )
        
        if resp.status_code == 200:
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"  下载进度: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='\r')
            
            print(f"\n✅ 已保存到: {output_path}")
            print(f"   文件大小: {downloaded / 1024 / 1024:.2f} MB")
            return True
        else:
            print(f"\n❌ 下载失败，状态码: {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ 下载异常: {e}")
        return False

if __name__ == "__main__":
    if API_KEY == "sk-你的Key":
        print("❌ 请设置 API_KEY")
        import sys
        sys.exit(1)
    
    # 1. 创建任务
    task_id = create_video_task()
    
    if task_id:
        # 2. 等待完成
        video_url = query_task_status(task_id)
        
        if video_url:
            # 3. 下载视频
            timestamp = int(time.time())
            output_file = f"煎饼特写_{VIDEO_CONFIG['duration']}秒_{timestamp}.mp4"  # 文件命名
            download_video(video_url, output_file)
    
    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)

