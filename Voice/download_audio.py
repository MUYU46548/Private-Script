# -*- coding: utf-8 -*-
"""
CosyVoice-v3-flash 多角色配音脚本
- 不同角色用不同音色（voice）
- 通过 instruction 控制情绪/语气
- 音频直接保存成 .wav 文件
"""

import os
import time
import requests
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

# ============================================================
# 1. 配置区
# ============================================================
# 方式一：直接写死 API Key（方便测试）
# dashscope.api_key = "sk-xxx"  # 替成你自己的 Key

# 方式二：从环境变量读取（更安全）
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

# 北京地域 WebSocket 地址，注意替换 {WorkspaceId}
# 你可以在百炼控制台「业务空间详情」里看到真实的 WorkspaceId
dashscope.base_websocket_api_url = "wss://ws-jpfxicqpptynsgny.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"

# 模型固定为 cosyvoice-v3-flash，其他模型可能出错
MODEL = "cosyvoice-v3-flash"

# ============================================================
# 2. 台词配置（按角色分开）
# ============================================================
# 这里只列几句，你可以按需要扩展

DIALOGUES = [
    {
        "id": 1,
        "role": "xiaoyue",
        "voice": "longanhuan_v3",      # 活泼、开朗的女性音色
        "text": "大煎饼卷好咯，风灵姐姐快来尝尝。",
        "instruction": "你说话的情感是happy。",  # 情绪：开心
        "filename": "01_xiaoyue_happy.wav"
    },
    {
        "id": 2,
        "role": "fengling",
        "voice": "longling_v3",        # 天真、可爱的小女孩音色
        "text": "哇~大煎饼！",
        "instruction": "你说话的情感是surprised。",  # 惊喜
        "filename": "02_fengling_wa.wav"
    },
    {
        "id": 3,
        "role": "fengling",
        "voice": "longling_v3",
        "text": "好好吃！",
        "instruction": "你说话的情感是happy。",
        "filename": "03_fengling_happy.wav"
    },
    {
        "id": 4,
        "role": "fengling",
        "voice": "longling_v3",
        "text": "多做几份，我要带回去给暮雨。",
        "instruction": "你说话的情感是happy。",  # 可以改成 neutral / happy 等
        "filename": "04_fengling_request.wav"
    },
]

# ============================================================
# 3. 核心合成逻辑
# ============================================================
def synthesize_one(item):
    """
    单条语音合成：
    - 创建 SpeechSynthesizer 实例（实时合成）
    - 传入 model / voice / instruction
    - 将返回的音频二进制写入本地文件
    """
    print(f"📝 [{item['id']}] 合成: {item['text']} (voice={item['voice']})")

    # 构造合成器
    synthesizer = SpeechSynthesizer(
        model=MODEL,
        voice=item["voice"],
        instruction=item.get("instruction")  # 没有 instruction 也可以不传
    )

    # 调用合成，返回的是音频二进制
    audio = synthesizer.call(item["text"])

    if not audio:
        print(f"   ❌ 合成失败：未返回音频数据")
        return False

    # 写入本地文件
    with open(item["filename"], "wb") as f:
        f.write(audio)

    print(f"   ✅ 已保存: {item['filename']}")
    return True

def main():
    if not dashscope.api_key:
        print("❌ 请先设置 dashscope.api_key 或环境变量 DASHSCOPE_API_KEY")
        return

    print("=" * 60)
    print("🎙️  开始 CosyVoice-v3-flash 多角色配音...")
    print("=" * 60)

    success = 0
    for item in DIALOGUES:
        ok = synthesize_one(item)
        if ok:
            success += 1
        # 避免触发限流，每句之间稍微间隔一下
        time.sleep(1.5)

    print("\n" + "=" * 60)
    print(f"🎉 完成！成功合成 {success}/{len(DIALOGUES)} 条语音")
    print("=" * 60)

if __name__ == "__main__":
    main()
