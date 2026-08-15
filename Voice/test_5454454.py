# -*- coding: utf-8 -*-
"""
最终完整版：所有台词一次性合成
"""

import os
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
# dashscope.api_key = "sk-xxx"  # 如果环境变量没有，取消注释并填写

def synthesize_audio(voice, text, filename):
    """
    简化版合成函数（不使用 instruction）
    """
    print(f"📝 合成: {text}")
    print(f"   voice: {voice}")
    
    try:
        synthesizer = SpeechSynthesizer(
            model="cosyvoice-v3-flash",
            voice=voice
        )
        
        audio = synthesizer.call(text)
        
        if audio:
            with open(filename, "wb") as f:
                f.write(audio)
            print(f"   ✅ 已保存: {filename}")
            return True
        else:
            print(f"   ❌ 未返回音频数据")
            return False
            
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return False

if __name__ == "__main__":
    if not dashscope.api_key:
        print("❌ 请设置 DASHSCOPE_API_KEY")
        import sys
        sys.exit(1)
    
    print("=" * 60)
    print("🎙️  开始批量合成语音")
    print("=" * 60)
    
    import time
    
    # 所有台词配置
    # ========== 只跑之前失败的 3 条 ==========
    dialogues = [
        {
            "id": 2,
            "role": "风灵",
            "voice": "longling_v3",  # 温柔少女
            "text": "是呀是呀，文风很稳健呢。",
            "filename": "02_fengling_chat.wav"
        },
    ]

    success_count = 0

    for item in dialogues:
        print(f"\n【第{item['id']}条】{item['role']}: \"{item['text']}\"")
        result = synthesize_audio(
            voice=item['voice'],
            text=item['text'],
            filename=item['filename']
        )
        if result:
            success_count += 1
        time.sleep(0.5)  # 避免频率限制

    print("\n" + "=" * 60)
    print(f"🎉 完成！成功: {success_count}/{len(dialogues)}")
    print("=" * 60)

    if success_count > 0:
        print("\n📁 生成的音频文件：")
        import glob
        wav_files = glob.glob("*.wav")
        for f in sorted(wav_files):
            size = os.path.getsize(f) / 1024
            print(f"   - {f} ({size:.1f} KB)")
