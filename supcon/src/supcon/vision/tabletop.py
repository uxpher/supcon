"""RGB-D 桌面分割与竖直几何体检测（Task3）。

不假定木块的初始 XY 位置。输入必须是已对齐的 RGB / 深度帧；输出对象
中心仍在相机坐标系，调用者再通过手眼外参变换至 B9 基座坐标系。
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np


class TabletopError(RuntimeError):
    pass


@dataclass
class TabletopObject:
    pixel: tuple[float, float]
    top_camera: np.ndarray
    height_m: float
    shape: str
    confidence: float
    yaw_camera: float | None
    area_px: float


class TabletopDetector:
    """通过桌面平面 RANSAC + 高度阈值获得桌面上的独立物体。"""

    def __init__(self, cfg: dict):
        self.workspace_roi = cfg.get("workspace_roi")  # [x, y, w, h]，None=整帧
        self.min_depth_m = float(cfg.get("min_depth_m", 0.15))
        self.max_depth_m = float(cfg.get("max_depth_m", 1.50))
        self.plane_threshold_m = float(cfg.get("plane_threshold_m", 0.006))
        self.min_object_height_m = float(cfg.get("min_object_height_m", 0.012))
        self.max_object_height_m = float(cfg.get("max_object_height_m", 0.160))
        self.min_component_area_px = int(cfg.get("min_component_area_px", 500))
        self.max_component_area_px = int(cfg.get("max_component_area_px", 50000))
        self.ransac_iterations = int(cfg.get("ransac_iterations", 160))
        self.min_plane_inlier_ratio = float(cfg.get("min_plane_inlier_ratio", 0.35))

    @staticmethod
    def _roi_mask(shape: tuple[int, int], roi: list | None) -> np.ndarray:
        h, w = shape
        mask = np.zeros((h, w), np.uint8)
        if roi is None:
            mask[:] = 1
            return mask
        if not isinstance(roi, (list, tuple)) or len(roi) != 4:
            raise TabletopError("workspace_roi 必须为 [x,y,w,h]")
        x, y, rw, rh = (int(v) for v in roi)
        x0, x1 = max(0, x), min(w, x + rw)
        y0, y1 = max(0, y), min(h, y + rh)
        if x1 <= x0 or y1 <= y0:
            raise TabletopError("workspace_roi 不在图像范围内")
        mask[y0:y1, x0:x1] = 1
        return mask

    @staticmethod
    def _points_from_depth(depth: np.ndarray, intrinsics: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        h, w = depth.shape
        fx, fy = float(intrinsics["fx"]), float(intrinsics["fy"])
        cx, cy = float(intrinsics["cx"]), float(intrinsics["cy"])
        if fx <= 0 or fy <= 0:
            raise TabletopError("相机内参 fx/fy 必须大于 0")
        yy, xx = np.indices((h, w), dtype=np.float32)
        x = (xx - cx) * depth / fx
        y = (yy - cy) * depth / fy
        return x, y, depth

    def _fit_table_plane(self, points: np.ndarray) -> tuple[np.ndarray, float]:
        if len(points) < 1000:
            raise TabletopError("有效深度点不足，无法拟合桌面")
        rng = np.random.default_rng(42)
        sample = points
        if len(points) > 12000:
            sample = points[rng.choice(len(points), 12000, replace=False)]
        best_normal, best_d, best_count = None, None, 0
        for _ in range(self.ransac_iterations):
            p = sample[rng.choice(len(sample), 3, replace=False)]
            normal = np.cross(p[1] - p[0], p[2] - p[0])
            norm = float(np.linalg.norm(normal))
            if norm < 1e-8:
                continue
            normal = normal / norm
            d = -float(normal @ p[0])
            count = int(np.count_nonzero(np.abs(sample @ normal + d) < self.plane_threshold_m))
            if count > best_count:
                best_normal, best_d, best_count = normal, d, count
        if best_normal is None or best_count < len(sample) * self.min_plane_inlier_ratio:
            raise TabletopError("桌面平面拟合失败：平面内点比例过低")
        # 用全量内点最小二乘细化平面；法向指向相机（camera z 的负方向）。
        distances = np.abs(points @ best_normal + best_d)
        inliers = points[distances < self.plane_threshold_m]
        center = inliers.mean(axis=0)
        _, _, vh = np.linalg.svd(inliers - center, full_matrices=False)
        normal = vh[-1]
        normal = normal / np.linalg.norm(normal)
        if normal[2] > 0:
            normal = -normal
        d = -float(normal @ center)
        return normal, d

    @staticmethod
    def _classify_contour(contour: np.ndarray) -> tuple[str, float, float | None]:
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        if area <= 0 or perimeter <= 0:
            return "unknown", 0.0, None
        circularity = 4.0 * math.pi * area / (perimeter * perimeter)
        vertices = len(cv2.approxPolyDP(contour, 0.025 * perimeter, True))
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        edges = np.roll(box, -1, axis=0) - box
        edge = edges[int(np.argmax(np.sum(edges * edges, axis=1)))]
        yaw = math.atan2(float(edge[1]), float(edge[0]))
        if circularity >= 0.84:
            return "cylinder", min(1.0, circularity), None
        if vertices == 3:
            return "triangular_prism", 0.88, yaw
        if vertices == 4:
            return "block", 0.84, yaw
        if vertices == 6:
            return "hexagonal_prism", 0.86, yaw
        # 透视、深度毛边会让六边形多/少一个近似顶点；可作为候选，
        # 但默认 Task3 阈值会拒绝该低置信结果，避免误放槽位。
        if vertices in (5, 7):
            return "hexagonal_prism", 0.70, yaw
        return "unknown", 0.0, yaw

    def detect(self, rgb: np.ndarray, depth_m: np.ndarray, intrinsics: dict) -> list[TabletopObject]:
        if depth_m is None:
            raise TabletopError("Task3 动态抓取需要 Gemini335 深度流")
        if rgb.shape[:2] != depth_m.shape:
            raise TabletopError(f"RGB/深度尺寸不一致：{rgb.shape[:2]} vs {depth_m.shape}")
        depth = np.asarray(depth_m, dtype=np.float32)
        roi = self._roi_mask(depth.shape, self.workspace_roi).astype(bool)
        valid = roi & np.isfinite(depth) & (depth >= self.min_depth_m) & (depth <= self.max_depth_m)
        x, y, z = self._points_from_depth(depth, intrinsics)
        points = np.column_stack((x[valid], y[valid], z[valid]))
        normal, d = self._fit_table_plane(points)
        height = normal[0] * x + normal[1] * y + normal[2] * z + d
        object_mask = valid & (height >= self.min_object_height_m) & (height <= self.max_object_height_m)
        mask_u8 = object_mask.astype(np.uint8) * 255
        kernel = np.ones((3, 3), np.uint8)
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel)
        mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        objects: list[TabletopObject] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if not self.min_component_area_px <= area <= self.max_component_area_px:
                continue
            component = np.zeros(depth.shape, np.uint8)
            cv2.drawContours(component, [contour], -1, 1, thickness=-1)
            selected = (component.astype(bool) & object_mask)
            if np.count_nonzero(selected) < 20:
                continue
            # 取物体最高 25% 点的中位数，避免把侧壁/阴影带入抓取中心。
            hvals = height[selected]
            cutoff = float(np.percentile(hvals, 75))
            top = selected & (height >= cutoff)
            top_point = np.array([np.median(x[top]), np.median(y[top]), np.median(z[top])], dtype=float)
            moments = cv2.moments(contour)
            if moments["m00"] <= 0:
                continue
            pixel = (float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"]))
            shape, confidence, yaw = self._classify_contour(contour)
            objects.append(TabletopObject(pixel, top_point, float(np.percentile(hvals, 90)),
                                          shape, confidence, yaw, area))
        objects.sort(key=lambda o: o.pixel[0])
        return objects
