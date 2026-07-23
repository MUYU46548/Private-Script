"""
强化版图片生成脚本
针对多模态输入模型
支持文生图
"""
import os
import time
import requests
from pathlib import Path
from urllib.parse import urlparse

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")  # API Key 已配置在环境变量 DASHSCOPE_API_KEY 中
WORKSPACE_ID = "ws-jpfxicqpptynsgny"  # 替换成真实的

BASE_URL = f"https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com"

HEADERS_COMMON = {
    "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
    "Content-Type": "application/json",
}

# 获取Windows默认下载文件夹
DOWNLOAD_FOLDER = Path.home() / "Downloads"
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

def download_image(url: str, prompt: str, index: int) -> Path:
    """下载图片到下载文件夹"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # 从URL中获取文件扩展名
        parsed_url = urlparse(url)
        ext = os.path.splitext(parsed_url.path)[1] or '.png'
        
        # 生成文件名（使用提示词的前20个字符）
        safe_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_prompt:
            safe_prompt = "image"
        
        filename = f"{safe_prompt}_{index}{ext}"
        filepath = DOWNLOAD_FOLDER / filename
        
        # 保存文件
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return filepath
    except Exception as e:
        raise RuntimeError(f"下载图片失败: {str(e)}")

def create_task(prompt: str):
    url = f"{BASE_URL}/api/v1/services/aigc/image-generation/generation"
    headers = {**HEADERS_COMMON, "X-DashScope-Async": "enable"}
    
    payload = {
        "model": "wan2.6-image",
        "input": {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ]
        },
        "parameters": {
            "size": "1280*720",  # 尺寸，受限于模型
            "n": 1,  # 张数，受限于模型。部分模型为批量处理，该值为批次数
            "enable_interleave": True
        }
    }
    
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    if "output" not in data or "task_id" not in data["output"]:
        raise RuntimeError(f"创建任务失败: {data}")
    return data["output"]["task_id"]

def get_task_result(task_id: str):
    url = f"{BASE_URL}/api/v1/tasks/{task_id}"
    resp = requests.get(url, headers=HEADERS_COMMON, timeout=30)
    resp.raise_for_status()
    return resp.json()

def wait_for_task(task_id: str, interval: int = 10, max_wait: int = 600):
    start = time.time()
    while time.time() - start < max_wait:
        data = get_task_result(task_id)
        status = data.get("output", {}).get("task_status")
        
        if status == "SUCCEEDED":
            return data
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"任务失败: {data.get('output', {}).get('message', '未知错误')}")
        time.sleep(interval)
    raise RuntimeError("等待任务超时")

def generate_image(prompt: str, index: int = 1):
    try:
        task_id = create_task(prompt)
        result = wait_for_task(task_id)
        
        # 提取图片链接
        if "output" in result and "choices" in result["output"]:
            for choice in result["output"]["choices"]:
                if "message" in choice and isinstance(choice["message"], dict):
                    for item in choice["message"].get("content", []):
                        if item.get("type") == "image":
                            url = item.get("image")
                            # 立即下载图片
                            filepath = download_image(url, prompt, index)
                            print(f"✅ 第{index}张图片已下载: {filepath}")
                            return filepath
        raise RuntimeError("未找到生成的图片")
    except Exception as e:
        print(f"❌ 生成第{index}张图片失败: {str(e)}")
        raise

def generate_images(prompt: str, num_images: int = 4):
    print(f"🎨 开始生成 {num_images} 张图片...")
    print(f"📝 提示词: {prompt}")
    print(f"💾 保存位置: {DOWNLOAD_FOLDER}\n")
    
    saved_paths = []
    for i in range(1, num_images + 1):
        try:
            filepath = generate_image(prompt, i)
            saved_paths.append(filepath)
        except Exception as e:
            continue  # 即使某张失败也继续生成下一张
    
    print(f"\n🎉 完成！共生成 {len(saved_paths)} 张图片")
    return saved_paths

if __name__ == "__main__":
    try:
        prompt = "一位紫色长直发少女，温柔的文学气质，穿水手服与格纹裙，站在湖边。动漫二次元，2D，平涂，柔和色彩。"
        urls = generate_images(prompt, num_images=3)
        
        print("\n📂 已保存的图片:")
        for i, path in enumerate(urls, 1):
            print(f"  {i}. {path}")
    except KeyboardInterrupt:
        print("\n⚠️  用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序运行失败: {str(e)}")