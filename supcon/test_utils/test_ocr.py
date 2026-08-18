#!/usr/bin/env python3
"""OCR 测试：读取 test_utils/ocr/ 目录的图片，识别数字/汉字形状标签。

用法：
    把数字图（1-4）或汉字形状标签图（长方体/正六棱柱/三棱柱/圆柱体等）
    放进 test_utils/ocr/，然后：
    python test_utils/test_ocr.py

输出：每张图一行，报告「通用文本 + 数字 + 形状标签」。
调用的是 supcon 真实算法：OcrRecognizer.recognize / recognize_digit / recognize_shape_label。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import cv2
import numpy as np

from supcon.vision.ocr import OcrRecognizer

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}
OCR_DIR = pathlib.Path(__file__).parent / "ocr"

SHAPE_CN = {
    "block": "长方体",
    "hexagonal_prism": "正六棱柱",
    "triangular_prism": "三棱柱",
    "cylinder": "圆柱体",
}


def imread_rgb(p):
    """读图为 RGB（np.fromfile + imdecode，支持中文路径）。"""
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"无法读取图片（可能损坏/格式不支持）: {p.name}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def main():
    ocr = OcrRecognizer()
    files = sorted(p for p in OCR_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not files:
        print(f"[test_ocr] {OCR_DIR} 目录没有图片，请放入数字图或汉字标签图后重试")
        return
    print(f"=== OCR 识别（共 {len(files)} 张）===")
    for p in files:
        rgb = imread_rgb(p)
        texts = ocr.recognize(rgb)
        text_str = ", ".join(f"{t}({c:.2f})" for t, c in texts) or "(无)"
        # 按文本框 x 坐标从左到右返回所有 1-4 数字
        digits = ocr.recognize_digits(rgb)
        digit_str = ", ".join(str(d) for d in digits) or "无"
        shape = ocr.recognize_shape_label(rgb)
        shape_str = SHAPE_CN.get(shape[0], shape[0]) if shape else "无"
        print(f"{p.name}: 识别文本(左→右)=[{text_str}] | 数字顺序=[{digit_str}] | 形状标签={shape_str}")


if __name__ == "__main__":
    main()
