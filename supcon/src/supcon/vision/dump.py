"""调试落盘：任务执行时把相机帧 / 深度可视化图写入磁盘（默认关闭，仅排查用）。

目录约定（相对项目根，cfg.resolve 解析）：
    task1 拍的亮灯面板图   → {dump_dir}/color/
    task2 拍的顶面数字图   → {dump_dir}/ocr/
    task3 拍的几何体图     → {dump_dir}/shape/
    task3 深度可视化图     → {depth_vis_dir}/          （默认 supcon/img_vis/）

深度矩阵本身只在内存中处理（camera.grab_depth() 返回 H×W float32 米），
本模块只负责把它的伪彩可视化图落盘，方便事后肉眼排查。
"""
from __future__ import annotations

import logging
import os
import time

import cv2
import numpy as np

log = logging.getLogger("dump")


def depth_to_color(depth_m: np.ndarray) -> np.ndarray:
    """H×W float32 深度（米，0=无效）→ 伪彩 BGR 图。"""
    d = np.asarray(depth_m, dtype=np.float32)
    valid = d > 0
    out = np.zeros(d.shape, np.uint8)
    if valid.any():
        vals = d[valid]
        vmin = float(np.percentile(vals, 2))
        vmax = float(np.percentile(vals, 98))
        if vmax <= vmin:
            vmax = vmin + 1e-6
        norm = np.clip((vals - vmin) / (vmax - vmin), 0.0, 1.0)
        out[valid] = (norm * 255.0).astype(np.uint8)
    return cv2.applyColorMap(out, cv2.COLORMAP_JET)


def _save_bgr(img: np.ndarray, path: str) -> None:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        log.warning("编码图片失败: %s", path)
        return
    buf.tofile(path)  # ndarray.tofile 支持中文路径（cv2.imwrite 不支持）


class DebugDump:
    """按任务子目录顺序落盘。disabled 时所有方法都是空操作，几乎零开销。"""

    def __init__(self, cfg):
        self.enabled = bool(getattr(cfg, "debug", None)
                            and getattr(cfg.debug, "dump_enabled", False))
        if not self.enabled:
            return
        self.root = cfg.resolve(cfg.debug.dump_dir)
        self.depth_vis_dir = cfg.resolve(cfg.debug.depth_vis_dir)
        self._ts = time.strftime("%Y%m%d_%H%M%S")
        self._seq: dict[str, int] = {}

    def _next(self, subdir: str, name: str) -> str:
        base = os.path.join(self.root, subdir)
        os.makedirs(base, exist_ok=True)
        self._seq[subdir] = self._seq.get(subdir, 0) + 1
        return os.path.join(base, f"{self._ts}_{self._seq[subdir]:03d}_{name}.png")

    def rgb(self, rgb: np.ndarray, subdir: str, name: str) -> None:
        if not self.enabled:
            return
        path = self._next(subdir, name)
        _save_bgr(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), path)
        log.info("已落盘 RGB → %s", path)

    def depth_vis(self, depth_m: np.ndarray, name: str) -> None:
        if not self.enabled:
            return
        base = self.depth_vis_dir
        os.makedirs(base, exist_ok=True)
        self._seq["img_vis"] = self._seq.get("img_vis", 0) + 1
        path = os.path.join(base, f"{self._ts}_{self._seq['img_vis']:03d}_{name}.png")
        _save_bgr(depth_to_color(depth_m), path)
        log.info("已落盘深度可视化 → %s", path)
