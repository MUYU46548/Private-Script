import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
import os

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

print("正在重新合成第1条...")

synthesizer = SpeechSynthesizer(
    model="cosyvoice-v3-flash",
    voice="longanhuan_v3",
    instruction="你说话的情感是happy。"
)

audio = synthesizer.call("大煎饼卷好咯。")

if audio:
    with open("01_xiaoyue.wav", "wb") as f:
        f.write(audio)
    print("✅ 第1条已保存！")
else:
    print("❌ 仍然失败，尝试缩短文本...")
    
    # 备选：缩短文本
    audio2 = synthesizer.call("大煎饼卷好咯。")
    if audio2:
        with open("01_xiaoyue.wav", "wb") as f:
            f.write(audio2)
        print("✅ 已保存缩短版")
