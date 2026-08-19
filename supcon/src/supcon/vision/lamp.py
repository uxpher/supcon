"""亮灯检测。

思路（确定性规则，无需训练模型）：
- 面板固定，3 盏灯在图像中的位置预先标定（config.yaml 的 task1.panel.lamps[].cx/cy）；
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
        """cfg: supcon.config.Task1Config"""
        self.margin = cfg.lamp_margin      # 亮灯须超过次亮的最小差值
        self.abs_min = cfg.lamp_abs_min    # 亮度绝对下限
        self.roi = cfg.roi_radius          # ROI 半径（像素）
        self.diff_max_dist = cfg.diff_max_dist  # 做差判定最大匹配距离（最大判定误差，px）

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
        """标定用：找全图最亮的 n 个连通块中心，按 x 升序返回。

        注意：仅适用于深色背景面板。白底面板会把整块背景当成一个亮斑，
        请改用做差法（calibrate_by_diff / detect_lit_index_by_diff）。
        """
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

    # ---------- 做差法（白底面板，需 origin 全灭基准帧） ----------
    @staticmethod
    def _gray(rgb: np.ndarray) -> np.ndarray:
        if rgb.ndim == 3:
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        return rgb

    @staticmethod
    def diff_blobs(live_rgb, origin_rgb, thresh: int = 40,
                   min_area: int = 25) -> list[tuple[float, float]]:
        """整帧做差：|live - origin| 的灰度差二值化，返回亮斑中心（面积降序）。

        白底面板下背景在做差后被抵消，只有状态变化处（亮灯/反光）残留，
        因此不受背景亮度影响，也不要求灯位等间距。

        前提：live 与 origin 必须像素级对齐（同视角、同分辨率、锁定曝光/白平衡）。
        """
        d = cv2.absdiff(LampDetector._gray(live_rgb), LampDetector._gray(origin_rgb))
        _, bw = cv2.threshold(d, thresh, 255, cv2.THRESH_BINARY)
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pts = []
        for c in sorted(cnts, key=cv2.contourArea, reverse=True):
            if cv2.contourArea(c) < min_area:
                continue
            m = cv2.moments(c)
            if m["m00"] <= 0:
                continue
            pts.append((float(m["m10"] / m["m00"]), float(m["m01"] / m["m00"])))
        return pts

    @staticmethod
    def calibrate_by_diff(origin_rgb, lit_rgbs, n: int = 3, thresh: int = 40,
                          eps: float = 40.0, y_tol: float | None = None) -> list[tuple[float, float]]:
        """做差累积标定灯位：每张亮灯帧取最大亮斑中心，聚类成 n 个灯位（左→右）。

        origin_rgb: 全灭基准帧；lit_rgbs: 覆盖各灯位的亮灯帧（可重复、可乱序，
        但必须覆盖到每一盏灯至少一次）。返回按 x 升序的 n 个 (cx, cy)。

        聚类半径 eps 应小于相邻灯位间距的一半（灯位不等距也不受影响，因为
        用的是"实测亮斑中心"，而非假设 x/4、x/2、3x/4）。
        3 盏灯应在同一水平排：若标出的灯位 y 坐标离散过大（y_tol），说明做差
        聚类到了背景噪声（通常是像素未对齐），直接报错而不是返回错误灯位。
        """
        pts = []
        for rgb in lit_rgbs:
            blobs = LampDetector.diff_blobs(rgb, origin_rgb, thresh=thresh)
            if blobs:
                pts.append(blobs[0])  # 最大亮斑 = 该帧亮灯位置
        if not pts:
            raise RuntimeError(
                "做差后未找到任何亮斑：请确认 origin 与亮灯帧像素对齐、曝光/白平衡一致")
        clusters: list[list] = []
        for p in pts:
            best = None
            for cl in clusters:
                c = np.mean(cl, axis=0)
                if np.hypot(p[0] - c[0], p[1] - c[1]) < eps:
                    best = cl
                    break
            if best is not None:
                best.append(p)
            else:
                clusters.append([p])
        centers = sorted(tuple(np.mean(cl, axis=0)) for cl in clusters)
        if len(centers) < n:
            raise RuntimeError(
                f"做差只聚类出 {len(centers)} 个灯位（需要 {n}）："
                f"可能有灯从未单独亮起，请补充覆盖该灯位的亮灯帧")
        centers = centers[:n]
        # 灯位应近似水平一排：y 离散过大概率是聚类到了噪声（对齐失败）。
        if y_tol is None:
            y_tol = 0.12 * float(origin_rgb.shape[0])
        ys = [c[1] for c in centers]
        spread = max(ys) - min(ys)
        if spread > y_tol:
            raise RuntimeError(
                f"标定出的 {n} 个灯位 y 离散过大（{spread:.0f}px > {y_tol:.0f}px）："
                f"疑似像素未对齐（origin 与亮灯帧非同一视角/分辨率），灯位不可信")
        return centers

    def detect_lit_index_by_diff(self, live_rgb, origin_rgb, lamps,
                                 thresh: int = 40,
                                 max_dist: float | None = None) -> int | None:
        """整帧做差找到唯一亮斑，匹配最近的 lamp 中心 → 返回 lamps 下标（无则 None）。

        与 ROI 基线法互补：不依赖 ROI 定位精度，适合做兜底复核。
        max_dist（最大判定误差）默认取 config task1.diff_max_dist。
        """
        if max_dist is None:
            max_dist = self.diff_max_dist
        blobs = LampDetector.diff_blobs(live_rgb, origin_rgb, thresh=thresh)
        if not blobs:
            return None
        cx, cy = blobs[0]
        best_i, best_d = None, float("inf")
        for i, l in enumerate(lamps):
            d = np.hypot(cx - float(l["cx"]), cy - float(l["cy"]))
            if d < best_d:
                best_d, best_i = d, i
        if best_i is None or best_d > max_dist:
            return None
        return best_i
