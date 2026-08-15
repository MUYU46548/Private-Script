# 导入原脚本的所有功能
from image_to_video import (
    generate_video_from_image,
    dashscope,
    DASHSCOPE_BASE_HTTP_API_URL,
    DOWNLOAD_DIR,
)

# ============================================================
# 🎬 在这里填写你的所有参数（掌控感拉满，且绝对安全）
# ============================================================

# -------- 必填参数 --------
IMAGE_PATH = "https://picgocloud.com/m/cc286950-9999-4876-aadc-874fd8128020.png"      # 你的图片路径
PROMPT = "镜头缓慢移动，煎饼冒着微微热气上升，动漫美食特写。"          # 动态效果描述

# -------- 可选参数 --------
MODEL_NAME = "wan2.7-i2v-2026-04-25"              # 模型决定一切
DURATION = 4                                   # 视频时长（秒）
VIDEO_SIZE = "1080P"                              # 尺寸："1280*720" 或 None，详见模型文档
SEED = None                                    # 随机种子（固定数字可复现）
NEGATIVE_PROMPT = "真人，3D，模糊，变形，低画质，纪录片。"                         # 反向提示词
PROMPT_EXTEND = False                           # True=AI优化提示词
WATERMARK = False                              # False=无水印
TAIL_IMAGE = None                              # 尾帧图片（首尾帧模型用）
AUTO_DOWNLOAD = True                           # True=自动下载

# ============================================================

# 设置API地址（保持不动）
dashscope.base_http_api_url = DASHSCOPE_BASE_HTTP_API_URL

# 执行生成
result = generate_video_from_image(
    image_url=IMAGE_PATH,
    prompt=PROMPT,
    model=MODEL_NAME,
    duration=DURATION,
    size=VIDEO_SIZE,
    seed=SEED,
    negative_prompt=NEGATIVE_PROMPT,
    prompt_extend=PROMPT_EXTEND,
    watermark=WATERMARK,
    tail_image_url=TAIL_IMAGE,
    auto_download=AUTO_DOWNLOAD,
    output_dir=DOWNLOAD_DIR,
)

# 打印结果
print(f"\n{'='*60}")
print(f"📊 生成结果")
print(f"{'='*60}")
print(f"✅ 成功: {'是' if result['success'] else '否'}")
print(f"🆔 任务ID: {result['task_id']}")
print(f"🔗 视频URL: {result['video_url']}")
print(f"📁 本地路径: {result['local_path'] or '未下载'}")
print(f"{'='*60}")