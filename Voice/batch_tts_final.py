# -*- coding: utf-8 -*-
"""
正确使用 CosyVoice instruction 的方法
必须先 connect()，再 call()
"""

import os
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
# dashscope.api_key = "sk-xxx"  # 或直接填写

def synthesize_with_instruction(voice, text, instruction, filename):
    """
    使用 instruction 参数的正确方法：
    1. 创建 synthesizer
    2. 调用 connect() 建立 WebSocket 连接
    3. 调用 call() 合成
    4. 调用 close() 关闭连接
    """
    print(f"📝 合成: {text}")
    print(f"   voice: {voice}")
    print(f"   instruction: {instruction}")
    
    synthesizer = None
    try:
        # 1. 创建合成器
        synthesizer = SpeechSynthesizer(
            model="cosyvoice-v3-flash",
            voice=voice,
            instruction=instruction
        )
        
        # 2. ⭐ 关键：建立 WebSocket 连接
        print("   正在连接...")
        synthesizer.connect()
        print("   ✅ 已连接")
        
        # 3. 调用合成
        print("   正在合成...")
        audio = synthesizer.call(text)
        
        if audio:
            # 4. 保存文件
            with open(filename, "wb") as f:
                f.write(audio)
            print(f"   ✅✅ 已保存: {filename}")
            return True
        else:
            print("   ❌ 未返回音频数据")
            return False
            
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 5. ⭐ 关键：关闭连接（释放资源）
        if synthesizer:
            try:
                synthesizer.close()
                print("   🔌 已断开连接")
            except:
                pass

def synthesize_without_instruction(voice, text, filename):
    """
    不需要 instruction 的简化调用（像你之前成功的那些）
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
            print("   ❌ 未返回音频数据")
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
    print("🎙️  开始合成所有台词")
    print("=" * 60)
    
    # 1. 小月（需要 instruction）
    print("\n【第1条】小月 - 欢脱元气")
    synthesize_with_instruction(
        voice="longanhuan_v3",
        text="大煎饼卷好咯，风灵姐姐快来尝尝。",
        instruction="你说话的情感是happy。",
        filename="01_xiaoyue.wav"
    )
    
    import time
    time.sleep(1)
    
    # 2-4. 风灵（不需要 instruction）
    # print("\n【第2条】风灵 - 稚气呆板")
    # synthesize_without_instruction(
        # voice="longling_v3",
        # text="哇~大煎饼！",
        # filename="02_fengling_amazed.wav"
    # )
    
    print("\n" + "=" * 60)
    print("🎉 全部完成！检查当前目录下的 .wav 文件")
    print("=" * 60)

