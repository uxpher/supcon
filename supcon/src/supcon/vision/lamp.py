"""Task1 指示灯检测（HSV 直接阈值，无需熄灯基线）。

面板固定后只需标定三盏灯的 ROI。每个 ROI 中满足绿色 Hue、饱和度和亮度
三个阈值的像素占比超过 ``green_ratio_min``，即判为亮灯。白色未亮灯的饱和度
接近零，不能通过该判据；三个 ROI 中必须恰好有一个通过，否则安全地判为不确定。
"""
from __future__ import annotations

import logging

import cv2
import numpy as np

log = logging.getLogger("lamp")


class LampDetector:
    def __init__(self, cfg):
        """cfg: supcon.config.Task1Config"""
        self.roi = cfg.roi_radius          # ROI 半径（像素）
        self.green_h_min = cfg.green_h_min
        self.green_h_max = cfg.green_h_max
        self.green_s_min = cfg.green_s_min
        self.green_v_min = cfg.green_v_min
        self.green_ratio_min = cfg.green_ratio_min
        self.diff_max_dist = cfg.diff_max_dist  # 做差判定最大匹配距离（最大判定误差，px）

    @staticmethod
    def scores(rgb: np.ndarray, lamps: list, default_radius: int) -> list[float]:
        """返回每个灯 ROI 的 HSV-V 均值（仅供标定诊断/兼容旧基线工具）。"""
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

    def green_scores(self, rgb: np.ndarray, lamps: list) -> list[float]:
        """返回每盏灯 ROI 中通过 HSV 绿色阈值的像素占比（范围 0~1）。"""
        if not lamps:
            return []
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        h, w = hsv.shape[:2]
        green = ((hsv[..., 0] >= self.green_h_min) &
                 (hsv[..., 0] <= self.green_h_max) &
                 (hsv[..., 1] >= self.green_s_min) &
                 (hsv[..., 2] >= self.green_v_min))
        ratios = []
        for lamp in lamps:
            cx, cy = int(lamp["cx"]), int(lamp["cy"])
            radius = int(lamp.get("roi_radius", self.roi))
            y0, y1 = max(0, cy - radius), min(h, cy + radius)
            x0, x1 = max(0, cx - radius), min(w, cx + radius)
            roi = green[y0:y1, x0:x1]
            ratios.append(float(roi.mean()) if roi.size else 0.0)
        return ratios

    def detect_lit_index(self, rgb: np.ndarray, lamps: list,
                         baseline: list[float] | None = None) -> int | None:
        """返回唯一亮灯的列表下标；``baseline`` 仅为旧调用兼容，已不参与判定。"""
        if not lamps:
            log.warning("面板文件里没有灯位")
            return None
        scores = self.green_scores(rgb, lamps)
        candidates = [index for index, score in enumerate(scores)
                      if score >= self.green_ratio_min]
        if not candidates:
            log.warning("无亮灯：绿色像素占比=%s，阈值=%.3f",
                        [round(score, 3) for score in scores], self.green_ratio_min)
            return None
        if len(candidates) != 1:
            log.warning("无法唯一判定亮灯：候选=%s，绿色像素占比=%s，阈值=%.3f",
                        candidates, [round(score, 3) for score in scores], self.green_ratio_min)
            return None
        index = candidates[0]
        log.info("灯 ROI 绿色像素占比=%s（H=%d~%d,S>=%d,V>=%d）→ 亮灯=#%d",
                 [round(score, 3) for score in scores],
                 self.green_h_min, self.green_h_max, self.green_s_min,
                 self.green_v_min, index)
        return index

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
