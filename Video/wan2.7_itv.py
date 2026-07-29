import os
from http import HTTPStatus
from dashscope import VideoSynthesis
import dashscope

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
prompt = "一只小猫在月光下的屋顶奔跑，镜头从低角度跟随拍摄，背景是夜晚的城市天际线。"

def generate_video():
    """视频生成主函数"""
    print("正在初始化配置...")
    
    # 1. 获取必要的配置
    try:
        workspace_id = get_workspace()
        api_key = API_KEY
        if not api_key:
            raise ValueError("请设置环境变量 'DASHSCOPE_API_KEY'")
    except ValueError as e:
        print(f"配置错误: {e}")
        return

    # 2. 动态设置 SDK 的请求地址（这是关键步骤）
    dashscope.base_http_api_url = f"https://{workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1"
    print(f"请求端点已设置为: {dashscope.base_http_api_url}")

    print("正在生成视频，请稍候（可能需要 1~5 分钟）...")

    # 3. 发起调用
    rsp = VideoSynthesis.call(
        api_key=api_key,
        model=MODEL,
        prompt=prompt,
        resolution="720P",
        ratio="16:9",
        duration=5,
        prompt_extend=True,
        watermark=False,
    )

    # 4. 处理结果
    if rsp.status_code == HTTPStatus.OK:
        print("任务完成！")
        # video_url 在 rsp.output.video_url 中，有效期 24 小时
        if hasattr(rsp.output, 'video_url'):
            print(f"视频URL: {rsp.output.video_url}")
            # 可以在这里添加代码下载视频
    else:
        print(f"生成失败: {rsp.status_code} - {rsp.code} - {rsp.message}")

if __name__ == "__main__":
    generate_video()
