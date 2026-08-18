#!/usr/bin/env python3
"""形状识别测试：读取 test_utils/shape/ 目录的图片，分类几何体截面形状。

用法：
    python test_utils/test_shape.py                # 单图模式：每张图识别 1 个几何体
    python test_utils/test_shape.py --panorama     # 全景模式：每张图分割多个几何体，左→右分别识别

输出：每张图一行（全景模式每张图多个几何体分多行输出）。
调用的是 supcon 真实算法：ShapeRecognizer.classify / classify_all。
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import cv2
import numpy as np

from supcon.vision.shape import ShapeRecognizer, ShapeError

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}
SHAPE_DIR = pathlib.Path(__file__).parent / "shape"

SHAPE_CN = {
    "block": "长方体",
    "hexagonal_prism": "正六棱柱",
    "triangular_prism": "三棱柱",
    "cylinder": "圆柱体",
    "unknown": "未知",
}


def imread_rgb(p):
    """读图为 RGB（np.fromfile + imdecode，支持中文路径）。"""
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"无法读取图片（可能损坏/格式不支持）: {p.name}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--panorama", action="store_true", help="全景模式：一张图分割多个几何体分别识别")
    args = ap.parse_args()

    recognizer = ShapeRecognizer(min_area=400)
    files = sorted(p for p in SHAPE_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not files:
        print(f"[test_shape] {SHAPE_DIR} 目录没有图片，请放入几何体俯视图后重试")
        return

    mode = "全景分割" if args.panorama else "单图"
    print(f"=== 形状识别（{mode}，共 {len(files)} 张）===")
    for p in files:
        try:
            rgb = imread_rgb(p)
        except IOError as e:
            print(f"{p.name}: 识别失败 - {e}")
            continue

        if args.panorama:
            results = recognizer.classify_all(rgb, n=4)
            if not results:
                print(f"{p.name}: 未分割出几何体")
                continue
            for i, (shape, conf, (x, y, w, h)) in enumerate(results):
                print(f"{p.name}: [{i}] 形状={SHAPE_CN.get(shape, shape)}({shape}) "
                      f"置信度={conf:.3f} bbox=({x},{y},{w},{h})")
        else:
            try:
                shape, conf = recognizer.classify(rgb)
                print(f"{p.name}: 形状={SHAPE_CN.get(shape, shape)}({shape}) 置信度={conf:.3f}")
            except ShapeError as e:
                print(f"{p.name}: 识别失败 - {e}")


if __name__ == "__main__":
    main()
