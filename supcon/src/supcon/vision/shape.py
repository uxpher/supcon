"""任务 3 竖直几何体的轻量形状分类。

更新规则要求全部竖直摆放，因此只需从观察图的轮廓分辨截面，不实现旧规则中的 6-DOF 翻转。
"""
from __future__ import annotations

import cv2
import numpy as np


class ShapeError(RuntimeError):
    pass


class ShapeRecognizer:
    def __init__(self, min_area: int = 400):
        self.min_area = min_area

    def classify(self, rgb_crop: np.ndarray) -> tuple[str, float]:
        hsv = cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2HSV)
        # 道具通常比白色工装有更高饱和度/更低亮度；现场可改为配置好的 mask。
        # 以饱和度排除白色工装；不能限制 V，否则高亮彩色道具会被误删。
        mask = cv2.inRange(hsv, (0, 20, 0), (180, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = [c for c in cnts if cv2.contourArea(c) >= self.min_area]
        if not cnts:
            raise ShapeError("未找到有效几何体轮廓")
        contour = max(cnts, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        area = cv2.contourArea(contour)
        if perimeter <= 0 or area <= 0:
            raise ShapeError("几何体轮廓无效")
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        vertices = len(cv2.approxPolyDP(contour, 0.035 * perimeter, True))
        if circularity > 0.82:
            return "cylinder", min(1.0, circularity)
        if vertices == 3:
            return "triangular_prism", 0.85
        if vertices == 4:
            rect = cv2.minAreaRect(contour)
            w, h = rect[1]
            ratio = min(w, h) / max(w, h) if min(w, h) > 1e-6 else 0
            return ("cube" if ratio > 0.82 else "block"), 0.8
        if 5 <= vertices <= 7:
            return "polyhedron", 0.72
        raise ShapeError(f"无法分类轮廓：vertices={vertices}, circularity={circularity:.2f}")
