# =========================================================#
# PDF 页眉水印脚本
# 功能：为 PDF 文件添加浅色页眉水印，显示版权信息
# 依赖：PyMuPDF (fitz)
# 警告：实际使用中请把 DEFAULT_AUTHOR 改成你自己的名字，否则水印会显示默认作者名
# =========================================================#

import argparse
import os
import sys
from datetime import datetime

import fitz  # PyMuPDF

# ---------------------------------------------------------
# 默认配置
# ---------------------------------------------------------
DEFAULT_AUTHOR = "暮雨"  # 换成你自己的名字！！！
DEFAULT_YEAR = None  # None 表示自动获取当前年份
DEFAULT_TEXT = None  # None 自动生成 "© {year} {author}"
DEFAULT_FONT_SIZE = 9
DEFAULT_OPACITY = 0.45  # 不透明度（0=全透明，1=不透明）
DEFAULT_GRAY = 0.35  # 灰度值（0=黑，1=白），配合 opacity 使用
POSITION_RIGHT = "right"
POSITION_CENTER = "center"
POSITION_LEFT = "left"
DEFAULT_POSITION = POSITION_RIGHT
DEFAULT_MARGIN_X = 40  # 距页面边缘水平距离（点）
DEFAULT_MARGIN_Y = 25  # 距页面顶端距离（点）
DEFAULT_SUFFIX = "_watermarked"  # 输出文件名后缀
DEFAULT_FONT_FILE = None  # None 时自动选择

# 系统字体候选列表（按优先级）
SYSTEM_FONT_CANDIDATES = [
    "msyh.ttc",  # 微软雅黑 - TextWriter 兼容性最好
    "simkai.ttf",  # 楷体
    "msyhbd.ttc",  # 微软雅黑粗体
    "STXIHEI.TTF",  # 华文细黑
    "STSONG.TTF",  # 华文宋体
]


def find_system_font():
    """在系统字体目录中查找可用的中文字体"""
    fonts_dir = r"C:\Windows\Fonts"
    for font_name in SYSTEM_FONT_CANDIDATES:
        font_path = os.path.join(fonts_dir, font_name)
        if os.path.exists(font_path):
            return font_path
    return None


def calc_text_position(page_width, page_height, text, font, font_size, position, margin_x, margin_y):
    """根据位置模式和页面尺寸计算文本起始坐标"""
    font_obj = fitz.Font(fontfile=font)
    text_width = font_obj.text_length(text, fontsize=font_size)

    if position == POSITION_RIGHT:
        x = page_width - text_width - margin_x
    elif position == POSITION_CENTER:
        x = (page_width - text_width) / 2
    elif position == POSITION_LEFT:
        x = margin_x
    else:
        x = page_width - text_width - margin_x

    y = margin_y
    return x, y


def add_watermark_to_pdf(
    input_path,
    output_path,
    text=None,
    font_file=None,
    font_size=DEFAULT_FONT_SIZE,
    opacity=DEFAULT_OPACITY,
    gray=DEFAULT_GRAY,
    position=DEFAULT_POSITION,
    margin_x=DEFAULT_MARGIN_X,
    margin_y=DEFAULT_MARGIN_Y,
    verbose=True,
):
    """
    为单个 PDF 添加页眉水印

    参数:
        input_path: 输入 PDF 路径
        output_path: 输出 PDF 路径
        text: 水印文本（None 则自动生成）
        font_file: 字体文件路径（None 则自动查找）
        font_size: 字号
        opacity: 不透明度 0-1
        gray: 灰度 0-1
        position: 位置 (right/center/left)
        margin_x: 水平边距
        margin_y: 垂直边距
        verbose: 是否输出处理信息

    返回:
        (成功: bool, 消息: str)
    """
    if not os.path.exists(input_path):
        return False, f"文件不存在: {input_path}"

    if not input_path.lower().endswith('.pdf'):
        return False, f"不是 PDF 文件: {input_path}"

    # 检查输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    try:
        doc = fitz.open(input_path)
    except Exception as e:
        return False, f"无法打开文件: {e}"

    if len(doc) == 0:
        return False, "PDF 为空（无页面）"

    # 确定字体
    if font_file is None:
        font_file = find_system_font()
        if font_file is None:
            doc.close()
            return False, "未找到可用中文字体，请通过 --font 指定"

    # 检查字体文件是否存在
    if not os.path.exists(font_file):
        doc.close()
        return False, f"字体文件不存在: {font_file}"

    # 创建字体对象
    font_obj = fitz.Font(fontfile=font_file)

    # 处理每一页
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_width = page.rect.width
        page_height = page.rect.height

        # 计算文本位置
        x, y = calc_text_position(
            page_width, page_height, text, font_file,
            font_size, position, margin_x, margin_y
        )

        # 使用 TextWriter 渲染水印（解决中文显示问题）
        tw = fitz.TextWriter(page.rect, color=(gray, gray, gray))
        tw.append(fitz.Point(x, y), text, font=font_obj, fontsize=font_size)

        page.write_text(
            writers=[tw],
            opacity=opacity,
            overlay=True,
        )

    # 保存
    try:
        doc.save(output_path, garbage=4, deflate=True)
        if verbose:
            print(f"  ✓ 已保存: {output_path}")
    except Exception as e:
        return False, f"保存失败: {e}"
    finally:
        doc.close()

    return True, "成功"


def batch_process(
    input_dir,
    output_dir=None,
    text=None,
    suffix=DEFAULT_SUFFIX,
    recursive=False,
    **kwargs
):
    """
    批量处理目录下的所有 PDF

    参数:
        input_dir: 输入目录
        output_dir: 输出目录（None 则与输入相同）
        text: 水印文本
        suffix: 输出文件后缀
        recursive: 是否递归子目录
        **kwargs: 传给 add_watermark_to_pdf 的其他参数
    """
    if not os.path.isdir(input_dir):
        print(f"错误: 目录不存在 {input_dir}")
        return

    if output_dir is None:
        output_dir = input_dir
    os.makedirs(output_dir, exist_ok=True)

    # 收集 PDF 文件
    pdf_files = []
    if recursive:
        for root, dirs, files in os.walk(input_dir):
            for f in files:
                if f.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, f))
    else:
        for f in os.listdir(input_dir):
            if f.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(input_dir, f))

    if not pdf_files:
        print(f"未找到 PDF 文件: {input_dir}")
        return

    print(f"共找到 {len(pdf_files)} 个 PDF 文件")
    print("-" * 50)

    success_count = 0
    fail_count = 0

    for i, input_path in enumerate(pdf_files, 1):
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)

        # 生成输出路径
        if recursive:
            # 保持相对目录结构
            rel_path = os.path.relpath(input_path, input_dir)
            rel_dir = os.path.dirname(rel_path)
            out_name = f"{name}{suffix}{ext}"
            output_path = os.path.join(output_dir, rel_dir, out_name)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        else:
            output_path = os.path.join(output_dir, f"{name}{suffix}{ext}")

        print(f"[{i}/{len(pdf_files)}] 处理: {filename}")
        success, msg = add_watermark_to_pdf(
            input_path, output_path, text=text, **kwargs
        )
        if success:
            success_count += 1
        else:
            fail_count += 1
            print(f"  ✗ 失败: {msg}")

    print("-" * 50)
    print(f"完成: 成功 {success_count} / 失败 {fail_count}")


def main():
    parser = argparse.ArgumentParser(
        description="PDF 页眉水印工具 - 为 PDF 添加版权信息水印",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 单个文件，自动生成 © 2026 暮雨
  python pdf_watermark.py -i novel.pdf

  # 指定完整水印文本
  python pdf_watermark.py -i novel.pdf -t "© 2026 暮雨 · 版权所有"

  # 批量处理目录
  python pdf_watermark.py -i ./pdfs/ -o ./output/

  # 自定义年份和作者
  python pdf_watermark.py -i novel.pdf --year 2025 --author "张三"

  # 调整位置和透明度
  python pdf_watermark.py -i novel.pdf --position center --opacity 0.15

  # 递归处理子目录
  python pdf_watermark.py -i ./pdfs/ --recursive
        """,
    )

    # 输入输出
    parser.add_argument("-i", "--input", required=True, help="输入 PDF 文件或目录路径")
    parser.add_argument("-o", "--output", default=None, help="输出路径（默认：输入目录）")

    # 水印内容
    content_group = parser.add_argument_group("水印内容")
    content_group.add_argument("-t", "--text", default=None, help="完整水印文本（优先级高于 --year/--author）")
    content_group.add_argument("--author", default=DEFAULT_AUTHOR, help=f"作者名（默认: {DEFAULT_AUTHOR}）")
    content_group.add_argument("--year", default=DEFAULT_YEAR, type=int, help="年份（默认: 当前年份）")

    # 外观
    appearance_group = parser.add_argument_group("外观设置")
    appearance_group.add_argument("--font", default=DEFAULT_FONT_FILE, help="字体文件路径（默认自动查找）")
    appearance_group.add_argument("--size", default=DEFAULT_FONT_SIZE, type=float, help=f"字号（默认: {DEFAULT_FONT_SIZE}）")
    appearance_group.add_argument("--opacity", default=DEFAULT_OPACITY, type=float,
                                   help=f"不透明度 0-1（默认: {DEFAULT_OPACITY}，越低越淡）")
    appearance_group.add_argument("--gray", default=DEFAULT_GRAY, type=float,
                                   help=f"灰度 0-1（默认: {DEFAULT_GRAY}）")

    # 位置
    position_group = parser.add_argument_group("位置设置")
    position_group.add_argument("--position", default=DEFAULT_POSITION,
                                choices=[POSITION_RIGHT, POSITION_CENTER, POSITION_LEFT],
                                help=f"水印位置（默认: {DEFAULT_POSITION}）")
    position_group.add_argument("--margin-x", default=DEFAULT_MARGIN_X, type=float,
                                help=f"水平边距/点（默认: {DEFAULT_MARGIN_X}）")
    position_group.add_argument("--margin-y", default=DEFAULT_MARGIN_Y, type=float,
                                help=f"垂直边距/点（默认: {DEFAULT_MARGIN_Y}）")

    # 批量处理
    batch_group = parser.add_argument_group("批量处理")
    batch_group.add_argument("--suffix", default=DEFAULT_SUFFIX,
                              help=f"输出文件后缀（默认: {DEFAULT_SUFFIX}）")
    batch_group.add_argument("--recursive", action="store_true", help="递归处理子目录")

    args = parser.parse_args()

    # 确定水印文本
    text = args.text
    if text is None:
        year = args.year if args.year is not None else datetime.now().year
        text = f"© {year} {args.author}"

    # 判断输入是文件还是目录
    if os.path.isfile(args.input):
        # 单个文件
        input_path = args.input
        if args.output:
            output_path = args.output
        else:
            name, ext = os.path.splitext(os.path.basename(input_path))
            output_path = os.path.join(
                os.path.dirname(input_path),
                f"{name}{args.suffix}{ext}",
            )

        print(f"处理文件: {os.path.basename(input_path)}")
        print(f"水印文本: {text}")
        success, msg = add_watermark_to_pdf(
            input_path,
            output_path,
            text=text,
            font_file=args.font,
            font_size=args.size,
            opacity=args.opacity,
            gray=args.gray,
            position=args.position,
            margin_x=args.margin_x,
            margin_y=args.margin_y,
        )
        if not success:
            print(f"失败: {msg}")
            sys.exit(1)

    elif os.path.isdir(args.input):
        # 批量处理
        batch_process(
            input_dir=args.input,
            output_dir=args.output,
            text=text,
            suffix=args.suffix,
            recursive=args.recursive,
            font_file=args.font,
            font_size=args.size,
            opacity=args.opacity,
            gray=args.gray,
            position=args.position,
            margin_x=args.margin_x,
            margin_y=args.margin_y,
        )

    else:
        print(f"错误: 路径不存在 {args.input}")
        sys.exit(1)


if __name__ == "__main__":
    main()
