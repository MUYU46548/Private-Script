# PDF 页眉水印工具

为 PDF 文件添加版权信息水印，轻量、免费、批量处理。

## 功能

- 自动生成水印文本：`© {年份} {作者}`
- 支持自定义年份（默认当前年份）、作者名
- 支持自定义完整水印文本（覆盖自动生成）
- 支持三种位置：右上角（默认）、居中、左上角
- 支持调节字号、透明度、灰度
- 支持批量处理目录下所有 PDF（可递归）
- 自动查找系统中文字体（黑体/微软雅黑/楷体）

## 依赖

```
pip install PyMuPDF
```

## 使用方法

### 完整路径批量处理（推荐）

直接复制！

```bash
py E:\CODE\CangKu\Python_Workspace\pdf-watermark\pdf_watermark.py -i "E:\图书馆\编辑室\710\已完成"
```

用`py`绕过烦人的虚拟环境，一次成功。

### 单个文件（自动生成 © 2026 暮雨）
```bash
python pdf_watermark.py -i novel.pdf
```

### 自定义完整水印文本
```bash
python pdf_watermark.py -i novel.pdf -t "© 2026 暮雨 · 版权所有"
```

### 指定年份和作者
```bash
python pdf_watermark.py -i novel.pdf --year 2025 --author "张三"
```

### 批量处理目录
```bash
python pdf_watermark.py -i ./pdfs/ -o ./output/
```

### 调整位置和透明度
```bash
python pdf_watermark.py -i novel.pdf --position center --opacity 0.15
```

### 递归处理子目录
```bash
python pdf_watermark.py -i ./pdfs/ --recursive
```

## 参数说明

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `-i, --input` | 必填 | 输入 PDF 文件或目录路径 |
| `-o, --output` | 与输入相同 | 输出路径 |
| `-t, --text` | 自动生成 | 完整水印文本 |
| `--author` | 暮雨 | 作者名 |
| `--year` | 当前年份 | 年份 |
| `--font` | 自动查找 | 字体文件路径 |
| `--size` | 9 | 字号 |
| `--opacity` | 0.2 | 不透明度（0=全透明，1=不透明） |
| `--gray` | 0.6 | 灰度（0=黑，1=白） |
| `--position` | right | 位置：right/center/left |
| `--margin-x` | 40 | 水平边距（点） |
| `--margin-y` | 25 | 垂直边距（点） |
| `--suffix` | _watermarked | 输出文件后缀 |
| `--recursive` | false | 递归处理子目录 |

## 输出文件命名

- 单个文件：`原名_watermarked.pdf`
- 批量处理：保留原文件名 + 后缀
- 递归处理：保留目录结构

## 推荐参数

针对小说 PDF 加水印的推荐配置：

```bash
python pdf_watermark.py -i novel.pdf --opacity 0.2 --size 9 --position right
```

效果：右上角显示淡灰色 `© 2026 暮雨`，肉眼可辨认，不遮挡正文，不影响 OCR 识别。

## 技术说明

- 水印位于页眉区域，不覆盖正文文字
- 低透明度设计，AI 训练数据提取时可被版面分析过滤
- 使用 PyMuPDF 的 overlay 模式，水印在文字顶层但视觉上不明显
