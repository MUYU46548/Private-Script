from http import HTTPStatus
from dashscope import VideoSynthesis
import dashscope
import os
import time

# ===说明===
# 仅适用于阿里云百炼平台。
# 模型名称等参数可随时调整

# ==================== 配置区域 ====================
# 1. 设置API地址（请将 {WorkspaceId} 替换为你的真实业务空间ID）
#    北京地域专属域名，建议使用[reference:2]
dashscope.base_http_api_url = 'https://ws-jpfxicqpptynsgny.cn-beijing.maas.aliyuncs.com/api/v1'

# 2. 设置API Key（推荐从环境变量读取，更安全）
# 配置环境变量DASHSCOPE_API_KEY后再使用
api_key = os.getenv("DASHSCOPE_API_KEY")

# ==================== 核心函数 ====================
def generate_video():
    """
    调用 wan2.6-t2v 模型生成视频
    """
    if not api_key:
        print("错误：未找到API Key。请设置环境变量 DASHSCOPE_API_KEY 或在代码中直接赋值。")
        return

    print("正在提交视频生成任务，请稍候... (wan2.6-t2v 模型生成耗时约1-5分钟)[reference:3]")

    # 调用 wan2.6-t2v 模型[reference:4]
    # 注意：wan2.6-t2v 的 duration 取值范围为 [2, 15][reference:5]
    rsp = VideoSynthesis.call(
        api_key=api_key,
        model='wan2.6-t2v',  # 指定使用的模型
        prompt='一位蓝色短发的少女，头发是清爽的齐耳直短发，发尾整齐，没有任何卷曲。她有着一双清澈的蓝色大眼睛，眼神温柔而灵动。身穿一件粉红色的连衣裙，裙摆轻盈，带有简单的蕾丝边装饰。白色过膝袜。整体风格为3D动漫风格，色彩明亮，质感像精致的游戏CG。'
                '午后的中式风格庭院，少女侧身站立，背靠一面爬满深绿色蔷薇枝叶的白墙。她的双手微微向后搭在墙上，指尖轻轻触碰到粗糙的墙面和冰凉的藤蔓。粉色的连衣裙与背后浓绿的藤蔓、纯白的墙面形成强烈的色彩对比。'
                '她微微仰起头，闭上眼睛，一片鲜红的蔷薇花瓣恰好从枝头飘落，轻轻落在她的额头上。她的嘴角带着一丝若有若无的浅笑。'
                '阳光透过枝叶的缝隙，在她脸上投下斑驳跃动的光影。镜头从远景开始，以极其缓慢的速度横向移动，最终定格在她的面部特写，捕捉光影在她脸颊上流动的细节。'
                '氛围静谧而慵懒，充满夏日午后的油画感。电影级浅景深，背景的蔷薇与白墙虚化柔和。',
        # audio_url='https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20250923/hbiayh/%E4%BB%8E%E5%86%9B%E8%A1%8C.mp3',  # 可选：自定义配音
        resolution='1080P',   # 1080P 对应 1920*1080[reference:6]
        ratio='16:9',        # 宽高比 16:9[reference:7]
        duration=15,         # wan2.6-t2v 最大支持15秒[reference:8]
        negative_prompt="",  # 可选：反向提示词，排除不想出现的元素
        prompt_extend=True,  # 开启提示词智能优化[reference:9]
        watermark=False,     # 是否添加水印[reference:10]
        seed=12345           # 种子数，固定可保持一定一致性
    )

    # ==================== 处理响应 ====================
    if rsp.status_code == HTTPStatus.OK:
        print("\n✅ 视频生成成功！")
        print(f"视频下载链接: {rsp.output.video_url}")
        # 打印计费时长信息（单位：秒）[reference:11]
        if hasattr(rsp, 'usage') and rsp.usage:
            print(f"计费时长: {rsp.usage.get('duration', '未知')} 秒")
    else:
        print('\n❌ 视频生成失败！')
        print(f'状态码: {rsp.status_code}')
        print(f'错误码: {rsp.code}')
        print(f'错误信息: {rsp.message}')

# ==================== 程序入口 ====================
if __name__ == '__main__':
    generate_video()