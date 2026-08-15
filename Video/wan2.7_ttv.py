import os
from http import HTTPStatus
from dashscope import VideoSynthesis
import dashscope
import requests
from datetime import datetime

# ====== 配置区 ======
def get_workspace():
    """从环境变量获取业务空间 ID"""
    workspace = os.getenv("DASHSCOPE_WORKSPACE")
    if not workspace:
        raise ValueError(
            "请设置环境变量 'DASHSCOPE_WORKSPACE' 为你的业务空间ID。\n"
            "或者在代码中直接赋值：workspace = '你的ID'"
        )
    return workspace

# API Key 也可以通过环境变量获取
API_KEY = os.getenv("DASHSCOPE_API_KEY")

# 模型名称
MODEL = "wan2.7-t2v"

# 提示词
prompt = """日系动漫风格，吉卜力画风，2D赛璐璐上色，柔和粉彩色调，明亮日光。
角色风灵：蓝色短发，蓝色眼睛，粉色连衣裙，白色衣领，深粉色领结，白色荷叶边，白色过膝袜，粉色乐福鞋。
角色暮雨：黑色短发，棕色眼睛，明黄色汉服，交领右衽，宽大袖袍，腰间系带（非旗袍，非紧身，非现代装）。
两人均为少女体型，身形纤细，表情温柔。
双人同框，亭中风灵和暮雨互动，风灵闭上一只眼双手合十求饶，暮雨举着空画板假装要打她，两人笑容温暖，衣袖交叠，背景是青翠山林，治愈可爱的互动场景。奇幻国风特效，温暖收尾氛围。"""

def generate_video():
    """视频生成主函数"""
    print("正在初始化配置...")
    
    try:
        workspace_id = get_workspace()
        api_key = API_KEY
        if not api_key:
            raise ValueError("请设置环境变量 'DASHSCOPE_API_KEY'")
    except ValueError as e:
        print(f"配置错误: {e}")
        return

    dashscope.base_http_api_url = f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1"
    print(f"请求端点: {dashscope.base_http_api_url}")

    print("正在生成视频，请稍候（可能需要 1~5 分钟）...")

    # ---------- 关键改动：用 try 包裹 ----------
    try:
        rsp = VideoSynthesis.call(
            api_key=api_key,
            model=MODEL,
            prompt=prompt,
            resolution="1080P",
            ratio="16:9",
            duration=9,
            prompt_extend=True,
            watermark=False,
        )
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return
    # -----------------------------------------

    # 现在 rsp 保证存在
    if rsp.status_code == HTTPStatus.OK:
        print("任务完成！")
        if hasattr(rsp.output, 'video_url'):
            video_url = rsp.output.video_url
            print(f"视频URL: {video_url}")

            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wan2.7_{timestamp}.mp4"   # 你用的是 wan2.7，改个名字
            file_path = os.path.join(downloads_path, filename)

            print(f"正在下载: {file_path}")
            try:
                r = requests.get(video_url, timeout=120)
                r.raise_for_status()
                with open(file_path, 'wb') as f:
                    f.write(r.content)
                print(f"✅ 下载完成！")
            except Exception as e:
                print(f"❌ 下载失败: {e}")
        else:
            print("⚠️ 响应中没有 video_url，请检查任务状态。")
    else:
        print(f"生成失败: {rsp.status_code} - {rsp.code} - {rsp.message}")

if __name__ == "__main__":
    generate_video()
