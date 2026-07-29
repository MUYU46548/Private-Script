"""
万相图生视频脚本 - 阿里云百炼平台
=====================================
采用异步调用模式：创建任务 -> 轮询获取 -> 自动下载

模型说明：
- 默认使用 wanx2.1-i2v-turbo（快速图生视频）
- 可选 wanx2.1-i2v-plus（高质量图生视频）
- 可选 wanx2.1-kf2v-plus（首尾帧生视频）
- 若使用更新模型（如 wan2.7），直接修改 MODEL 常量即可

使用前提：
1. 安装 dashscope: pip install dashscope
2. 设置环境变量 DASHSCOPE_API_KEY
3. 可选：设置 DASHSCOPE_WORKSPACE（业务空间ID）
"""

from http import HTTPStatus
from dashscope import VideoSynthesis
import dashscope
import os
import time
import requests
import argparse
from pathlib import Path
from datetime import datetime

# ==================== 配置区域 ====================

# API 配置-请将 {WorkspaceId} 替换为你的真实业务空间ID
DASHSCOPE_BASE_HTTP_API_URL = 'https://ws-jpfxicqpptynsgny.cn-beijing.maas.aliyuncs.com/api/v1'

# 模型选择
# 可选值：
#   - "wanx2.1-i2v-turbo"   : 快速图生视频（推荐，速度快）
#   - "wanx2.1-i2v-plus"    : 高质量图生视频（质量更好）
#   - "wanx2.1-kf2v-plus"   : 首尾帧生视频（需提供首帧和尾帧）
#   - "wanx-img2video-pro"  : 专业图生视频
#   - 其他万相模型名称（如 wan2.7 系列，待 SDK 更新后可直接使用）
MODEL = "wanx2.1-i2v-turbo"

# 轮询配置
POLL_INTERVAL = 5          # 轮询间隔（秒）
MAX_POLL_ATTEMPTS = 120    # 最大轮询次数（防止无限等待，120次 × 5秒 = 10分钟）

# 下载配置
DOWNLOAD_DIR = Path(os.path.join(os.path.expanduser('~'), 'Downloads'))  # Windows 默认下载文件夹
DOWNLOAD_TIMEOUT = 120     # 下载超时（秒）

# ==================== 核心函数 ====================

def get_api_key():
    """从环境变量获取 API Key"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError(
            "未找到 DASHSCOPE_API_KEY 环境变量。\n"
            "请通过以下方式之一设置：\n"
            "  1. 系统环境变量：set DASHSCOPE_API_KEY=your_key\n"
            "  2. 临时设置：$env:DASHSCOPE_API_KEY='your_key' (PowerShell)"
        )
    return api_key


def get_workspace():
    """从环境变量获取业务空间 ID（可选）"""
    return os.getenv("DASHSCOPE_WORKSPACE", None)


def create_image_to_video_task(
    image_url: str,
    prompt: str = "",
    model: str = MODEL,
    duration: int = 5,
    size: str = None,
    seed: int = None,
    negative_prompt: str = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    tail_image_url: str = None,
):
    """
    创建图生视频异步任务

    参数:
        image_url: 首帧图片 URL（必需）
        prompt: 视频描述提示词
        model: 模型名称
        duration: 视频时长（秒），默认 5
        size: 视频尺寸（如 "1280*720"）
        seed: 随机种子
        negative_prompt: 反向提示词
        prompt_extend: 是否开启提示词智能优化
        watermark: 是否添加水印
        tail_image_url: 尾帧图片 URL（仅首尾帧模型需要）

    返回:
        task_id: 任务 ID
    """
    api_key = get_api_key()
    workspace = get_workspace()

    print(f"\n{'='*60}")
    print(f"正在创建图生视频任务...")
    print(f"{'='*60}")
    print(f"模型: {model}")
    print(f"首帧图片: {image_url}")
    if tail_image_url:
        print(f"尾帧图片: {tail_image_url}")
    print(f"提示词: {prompt or '(无)'}")
    print(f"时长: {duration}秒")
    print(f"{'='*60}\n")

    # 构建额外输入参数
    extra_input = {}
    if tail_image_url:
        extra_input["tail_image_url"] = tail_image_url

    # 调用异步接口创建任务
    rsp = VideoSynthesis.async_call(
        model=model,
        prompt=prompt,
        img_url=image_url,
        api_key=api_key,
        workspace=workspace,
        duration=duration,
        size=size,
        seed=seed,
        negative_prompt=negative_prompt,
        prompt_extend=prompt_extend,
        watermark=watermark,
        extra_input=extra_input if extra_input else None,
    )

    if rsp.status_code != HTTPStatus.OK:
        print(f"❌ 任务创建失败！")
        print(f"状态码: {rsp.status_code}")
        print(f"错误码: {rsp.code}")
        print(f"错误信息: {rsp.message}")
        return None

    task_id = rsp.output.task_id
    task_status = rsp.output.task_status
    print(f"✅ 任务创建成功！")
    print(f"任务 ID: {task_id}")
    print(f"初始状态: {task_status}")
    return task_id


def poll_task_status(task_id: str, interval: int = POLL_INTERVAL, max_attempts: int = MAX_POLL_ATTEMPTS):
    """
    轮询任务状态直到完成

    参数:
        task_id: 任务 ID
        interval: 轮询间隔（秒）
        max_attempts: 最大轮询次数

    返回:
        video_url: 视频下载 URL，失败返回 None
    """
    api_key = get_api_key()
    workspace = get_workspace()

    print(f"\n开始轮询任务状态（每 {interval} 秒检查一次，最多 {max_attempts} 次）...")
    print("-" * 60)

    for attempt in range(1, max_attempts + 1):
        time.sleep(interval)

        rsp = VideoSynthesis.fetch(
            task=task_id,
            api_key=api_key,
            workspace=workspace,
        )

        if rsp.status_code != HTTPStatus.OK:
            print(f"  [{attempt}/{max_attempts}] 查询失败: {rsp.message}")
            continue

        status = rsp.output.task_status
        print(f"  [{attempt}/{max_attempts}] 状态: {status}")

        if status == "SUCCEEDED":
            video_url = rsp.output.video_url
            print(f"\n✅ 视频生成成功！")
            print(f"视频 URL: {video_url}")
            return video_url
        elif status == "FAILED":
            print(f"\n❌ 视频生成失败！")
            print(f"任务 ID: {task_id}")
            return None
        elif status == "UNKNOWN":
            print(f"\n⚠️ 任务状态未知，继续轮询...")
            continue
        # 其他状态：PENDING, RUNNING, CANCELED 等，继续轮询

    print(f"\n⏰ 轮询超时（已等待 {max_attempts * interval} 秒）")
    print(f"任务 ID: {task_id}")
    print(f"请稍后通过任务 ID 手动查询结果。")
    return None


def download_video(video_url: str, output_dir: Path = DOWNLOAD_DIR, timeout: int = DOWNLOAD_TIMEOUT):
    """
    下载视频到本地默认下载文件夹

    参数:
        video_url: 视频下载 URL
        output_dir: 输出目录
        timeout: 下载超时（秒）

    返回:
        file_path: 本地文件路径，失败返回 None
    """
    if not video_url:
        return None

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"wanx_i2v_{timestamp}.mp4"
    file_path = output_dir / filename

    print(f"\n{'='*60}")
    print(f"正在下载视频到本地...")
    print(f"{'='*60}")
    print(f"保存位置: {file_path}")
    print(f"超时设置: {timeout}秒")

    try:
        response = requests.get(video_url, stream=True, timeout=timeout)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r  下载进度: {percent:.1f}% ({downloaded}/{total_size} bytes)", end="", flush=True)

        print(f"\n✅ 下载完成！")
        print(f"文件大小: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
        return str(file_path)

    except requests.exceptions.Timeout:
        print(f"\n❌ 下载超时（{timeout}秒）")
        print(f"视频 URL: {video_url}")
        print(f"请手动下载视频。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 下载失败: {e}")
        print(f"视频 URL: {video_url}")
        print(f"请手动下载视频。")
        return None


def generate_video_from_image(
    image_url: str,
    prompt: str = "",
    model: str = MODEL,
    duration: int = 5,
    size: str = None,
    seed: int = None,
    negative_prompt: str = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    tail_image_url: str = None,
    auto_download: bool = True,
    output_dir: Path = DOWNLOAD_DIR,
):
    """
    完整的图生视频流程：创建任务 -> 轮询 -> 下载

    参数:
        image_url: 首帧图片 URL
        prompt: 视频描述提示词
        model: 模型名称
        duration: 视频时长（秒）
        size: 视频尺寸
        seed: 随机种子
        negative_prompt: 反向提示词
        prompt_extend: 是否开启提示词智能优化
        watermark: 是否添加水印
        tail_image_url: 尾帧图片 URL
        auto_download: 是否自动下载视频
        output_dir: 下载目录

    返回:
        dict: 包含 task_id, video_url, local_path 的结果字典
    """
    result = {
        "task_id": None,
        "video_url": None,
        "local_path": None,
        "success": False,
    }

    # 步骤 1：创建任务
    task_id = create_image_to_video_task(
        image_url=image_url,
        prompt=prompt,
        model=model,
        duration=duration,
        size=size,
        seed=seed,
        negative_prompt=negative_prompt,
        prompt_extend=prompt_extend,
        watermark=watermark,
        tail_image_url=tail_image_url,
    )

    if not task_id:
        return result

    result["task_id"] = task_id

    # 步骤 2：轮询任务状态
    video_url = poll_task_status(task_id)

    if not video_url:
        return result

    result["video_url"] = video_url
    result["success"] = True

    # 步骤 3：自动下载视频
    if auto_download:
        local_path = download_video(video_url, output_dir=output_dir)
        result["local_path"] = local_path

    return result


# ==================== CLI 入口 ====================

def parse_args():
    parser = argparse.ArgumentParser(
        description="万相图生视频脚本 - 阿里云百炼平台",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法（仅图片）
  python image_to_video.py --image "https://example.com/image.jpg"

  # 带提示词
  python image_to_video.py --image "https://example.com/image.jpg" --prompt "花瓣飘落，微风轻拂"

  # 指定模型和时长
  python image_to_video.py --image "https://example.com/image.jpg" --model wanx2.1-i2v-plus --duration 10

  # 首尾帧生视频
  python image_to_video.py --image "https://example.com/first.jpg" --tail-image "https://example.com/last.jpg" --model wanx2.1-kf2v-plus

  # 不自动下载
  python image_to_video.py --image "https://example.com/image.jpg" --no-download
        """,
    )

    parser.add_argument("--image", "-i", required=True, help="首帧图片 URL")
    parser.add_argument("--tail-image", "-t", default=None, help="尾帧图片 URL（首尾帧模型使用）")
    parser.add_argument("--prompt", "-p", default="", help="视频描述提示词")
    parser.add_argument("--negative-prompt", "-n", default=None, help="反向提示词")
    parser.add_argument("--model", "-m", default=MODEL, help=f"模型名称（默认: {MODEL}）")
    parser.add_argument("--duration", "-d", type=int, default=5, help="视频时长（秒，默认: 5）")
    parser.add_argument("--size", "-s", default=None, help="视频尺寸（如 1280*720）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--no-prompt-extend", action="store_true", help="关闭提示词智能优化")
    parser.add_argument("--watermark", action="store_true", help="添加水印")
    parser.add_argument("--no-download", action="store_true", help="不自动下载视频")
    parser.add_argument("--output-dir", "-o", type=Path, default=DOWNLOAD_DIR, help=f"下载目录（默认: {DOWNLOAD_DIR}）")
    parser.add_argument("--poll-interval", type=int, default=POLL_INTERVAL, help=f"轮询间隔（秒，默认: {POLL_INTERVAL}）")
    parser.add_argument("--max-attempts", type=int, default=MAX_POLL_ATTEMPTS, help=f"最大轮询次数（默认: {MAX_POLL_ATTEMPTS}）")

    return parser.parse_args()


def main():
    args = parse_args()

    # 设置 API 地址
    dashscope.base_http_api_url = DASHSCOPE_BASE_HTTP_API_URL

    # 执行图生视频流程
    result = generate_video_from_image(
        image_url=args.image,
        prompt=args.prompt,
        model=args.model,
        duration=args.duration,
        size=args.size,
        seed=args.seed,
        negative_prompt=args.negative_prompt,
        prompt_extend=not args.no_prompt_extend,
        watermark=args.watermark,
        tail_image_url=args.tail_image,
        auto_download=not args.no_download,
        output_dir=args.output_dir,
    )

    # 打印最终结果
    print(f"\n{'='*60}")
    print(f"执行结果摘要")
    print(f"{'='*60}")
    print(f"成功: {'✅ 是' if result['success'] else '❌ 否'}")
    print(f"任务 ID: {result['task_id']}")
    print(f"视频 URL: {result['video_url']}")
    print(f"本地路径: {result['local_path'] or '未下载'}")
    print(f"{'='*60}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    exit(main())
