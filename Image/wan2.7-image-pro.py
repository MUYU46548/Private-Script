import os
import json
import urllib.request
import urllib.error

# 从环境变量获取配置
API_KEY = os.getenv("DASHSCOPE_API_KEY")
WORKSPACE_ID = os.getenv("DASHSCOPE_WORKSPACE")

# 必要的验证
if not API_KEY:
    raise ValueError("错误：环境变量 DASHSCOPE_API_KEY 未设置")
if not WORKSPACE_ID:
    raise ValueError("错误：环境变量 DASHSCOPE_WORKSPACE 未设置")

# 选择地域（也支持从环境变量读取）
REGION = os.getenv("DASHSCOPE_REGION", "beijing")  # 默认北京

# 构建请求 URL
BASE_URL = {
    "beijing": f"https://{WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    "singapore": f"https://{WORKSPACE_ID}.ap-southeast-1.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
}[REGION]

print(f"使用配置 - Workspace ID: {WORKSPACE_ID}, 地域: {REGION}")
print(f"请求 URL: {BASE_URL}")

def call_wan27_sync():
    url = BASE_URL
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": "wan2.7-image-pro",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": "二次元平涂动漫CG风格，角色设定参考图，全身正面站姿。天蓝色齐下巴直发，天蓝色眼睛，粉红色连衣裙，白色衣领，粉色系小配饰。少女纤细体态。表情开朗温柔，带淡淡笑意。纯白背景，全身可见，设定图风格。"}
                    ]
                }
            ]
        },
        "parameters": {
            "size": "2K",
            "n": 1,
            "watermark": False,
            "thinking_mode": True
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("响应：", json.dumps(data, indent=2, ensure_ascii=False))
            
            # 提取图片 URL 并保存
            for choice in data.get("output", {}).get("choices", []):
                for item in choice.get("message", {}).get("content", []):
                    if item.get("type") == "image":
                        img_url = item["image"]
                        fname = f"output_{os.urandom(4).hex()}.png"
                        urllib.request.urlretrieve(img_url, fname)
                        print(f"图片已保存：{fname}")
    except urllib.error.HTTPError as e:
        print(f"HTTP 错误：{e.code}")
        print(e.read().decode("utf-8"))
    except Exception as e:
        print(f"请求异常：{e}")

if __name__ == "__main__":
    call_wan27_sync()
