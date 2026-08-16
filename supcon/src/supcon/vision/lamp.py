"""亮灯检测。

思路（确定性规则，无需训练模型）：
- 面板固定，3 盏灯在图像中的位置预先标定（panel.json lamps[].cx/cy）；
- 运行时对每盏灯的 ROI 算平均亮度（HSV 的 V 通道），
  最亮且明显超过次亮者 = 亮灯；否则判定"无亮灯"。
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

log = logging.getLogger("lamp")


class LampDetector:
    def __init__(self, cfg):
        """cfg: supcon_task2.config.Task1Config"""
        self.margin = cfg.lamp_margin      # 亮灯须超过次亮的最小差值
        self.abs_min = cfg.lamp_abs_min    # 亮度绝对下限
        self.roi = cfg.roi_radius          # ROI 半径（像素）

    @staticmethod
    def scores(rgb: np.ndarray, lamps: list, default_radius: int) -> list[float]:
        """返回每个灯 ROI 的 HSV-V 均值；调用方可与现场基线做差。"""
        if not lamps:
            return []
        v = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[..., 2]
        h, w = v.shape
        scores = []
        for l in lamps:
            cx, cy = int(l["cx"]), int(l["cy"])
            r = int(l.get("roi_radius", default_radius))
            y0, y1 = max(0, cy - r), min(h, cy + r)
            x0, x1 = max(0, cx - r), min(w, cx + r)
            roi = v[y0:y1, x0:x1]
            scores.append(float(roi.mean()) if roi.size else 0.0)

        return scores

    def detect_lit_index(self, rgb: np.ndarray, lamps: list,
                         baseline: list[float] | None = None) -> int | None:
        """返回 lamps 列表下标。提供 baseline 时按亮度增量判定。"""
        raw = self.scores(rgb, lamps, self.roi)
        if not raw:
            log.warning("面板文件里没有灯位")
            return None
        scores = raw
        if baseline is not None:
            if len(baseline) != len(raw):
                raise ValueError("亮灯基线长度与 lamps 不一致")
            scores = [value - base for value, base in zip(raw, baseline)]
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        best = order[0]
        second = order[1] if len(order) > 1 else None
        if scores[best] < self.abs_min:
            log.warning("无亮灯：最亮 ROI=%.1f < 阈值 %.1f（亮度: %s）",
                        scores[best], self.abs_min,
                        [round(s, 1) for s in scores])
            return None
        if second is not None and scores[best] - scores[second] < self.margin:
            log.warning("无法区分亮灯：最亮=%.1f 次亮=%.1f 差值<%.1f",
                        scores[best], scores[second], self.margin)
            return None
        log.info("灯 ROI 原始亮度=%s 判定分数=%s → 亮灯 = #%d",
                 [round(s, 1) for s in raw], [round(s, 1) for s in scores], best)
        return best

    @staticmethod
    def find_bright_blobs(rgb: np.ndarray, n: int = 3,
                          thresh: int = 150) -> list[tuple[float, float]]:
        """标定用：找全图最亮的 n 个连通块中心，按 x 升序返回。"""
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        _, bw = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:n]
        pts = []
        for c in cnts:
            m = cv2.moments(c)
            if m["m00"] <= 0:
                continue
            pts.append((float(m["m10"] / m["m00"]), float(m["m01"] / m["m00"])))
        pts.sort(key=lambda p: p[0])
        return pts
