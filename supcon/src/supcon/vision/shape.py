"""任务 3 竖直几何体的轻量形状分类。

更新规则要求全部竖直摆放，因此只需从观察图的轮廓分辨截面，不实现旧规则中的 6-DOF 翻转。

- classify：单张图（一个几何体截面）→ 取最大轮廓分类；
- classify_all：全景图（多个几何体同框）→ 分割出多个、按 x 左→右分别分类。
"""
from __future__ import annotations

import cv2
import numpy as np


class ShapeError(RuntimeError):
    pass


class ShapeRecognizer:
    def __init__(self, min_area: int = 400):
        self.min_area = min_area

    def _mask_contours(self, rgb: np.ndarray) -> list:
        """饱和度分割，返回满足最小面积的轮廓列表。"""
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        # 道具通常比白色工装有更高饱和度/更低亮度；现场可改为配置好的 mask。
        # 以饱和度排除白色工装；不能限制 V，否则高亮彩色道具会被误删。
        mask = cv2.inRange(hsv, (0, 20, 0), (180, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return [c for c in cnts if cv2.contourArea(c) >= self.min_area]

    def _classify_contour(self, contour) -> tuple[str, float]:
        """单个轮廓 → (shape, confidence)。"""
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
            return "block", 0.8
        if 5 <= vertices <= 7:
            return "hexagonal_prism", 0.72
        raise ShapeError(f"无法分类轮廓：vertices={vertices}, circularity={circularity:.2f}")

    def classify(self, rgb_crop: np.ndarray) -> tuple[str, float]:
        """单张图（一个几何体截面）分类：取最大轮廓。"""
        cnts = self._mask_contours(rgb_crop)
        if not cnts:
            raise ShapeError("未找到有效几何体轮廓")
        contour = max(cnts, key=cv2.contourArea)
        return self._classify_contour(contour)

    def classify_all(self, rgb: np.ndarray, n: int = 4) -> list[tuple[str, float, tuple]]:
        """全景图分割：分割出 n 个几何体（按 x 左→右），分别分类。

        返回 [(shape, confidence, (x, y, w, h)), ...]，按左→右顺序。
        """
        cnts = self._mask_contours(rgb)
        if not cnts:
            return []
        # 按 x 从左到右排序
        cnts = sorted(cnts, key=lambda c: cv2.boundingRect(c)[0])
        cnts = cnts[:n]
        results = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            try:
                shape, conf = self._classify_contour(c)
            except ShapeError:
                shape, conf = "unknown", 0.0
            results.append((shape, conf, (x, y, w, h)))
        return results

    def segment_by_depth(self, depth: np.ndarray | None,
                         near_margin: float = 0.03) -> np.ndarray | None:
        """用深度图分割凸出桌面的几何体（几何体高 → 深度比桌面近）。

        depth: HxW float32（米），0=无效
        near_margin: 比桌面近多少米算几何体（米，现场按几何体高度调）
        返回：几何体二值 mask（几何体=255，背景=0）；无深度时返回 None
        """
        if depth is None:
            return None
        valid = depth[depth > 0]
        if valid.size == 0:
            return None
        table_depth = float(np.median(valid))  # 桌面深度（中位数，桌面占多数像素）
        near = (depth > 0) & (depth < table_depth - near_margin)
        mask = (near * 255).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        return mask

    def classify_all_by_depth(self, rgb: np.ndarray, depth: np.ndarray | None,
                              n: int = 4, near_margin: float = 0.03) -> list[tuple[str, float, tuple]]:
        """深度分割 + 彩色分类：用深度分割几何体，再用彩色截面分类（左→右）。

        深度图与彩色图尺寸不同时，先简单 resize 对齐（现场可改硬件对齐）。
        返回 [(shape, confidence, (x, y, w, h)), ...]；无深度时返回 []。
        """
        mask = self.segment_by_depth(depth, near_margin)
        if mask is None:
            return []
        if mask.shape[:2] != rgb.shape[:2]:
            mask = cv2.resize(mask, (rgb.shape[1], rgb.shape[0]),
                              interpolation=cv2.INTER_NEAREST)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = [c for c in cnts if cv2.contourArea(c) >= self.min_area]
        cnts = sorted(cnts, key=lambda c: cv2.boundingRect(c)[0])  # 左→右
        cnts = cnts[:n]
        results = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            crop = rgb[y:y + h, x:x + w]
            try:
                shape, conf = self.classify(crop)
            except ShapeError:
                shape, conf = "unknown", 0.0
            results.append((shape, conf, (x, y, w, h)))
        return results
