"""手眼标定结果读写与像素→Base 坐标变换。

⚠️ 任务1 不需要手眼标定（开关位姿直接示教记录），本模块为 Task2/3 预留。
变换关系：T_world_camera = T_world_eef · T_eef_camera
          P_world = T_world_camera · P_camera
"""
from __future__ import annotations

import json
import logging
import os

import numpy as np

from ..utils import pose_to_matrix

log = logging.getLogger("handeye")


def load_calibration(path: str) -> dict | None:
    """读取 calibration.json。结构：{"T_eef_camera": [[...4x4...]], "note": ...}"""
    if not path or not os.path.exists(path):
        log.warning("手眼标定文件不存在: %s", path)
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    d["T_eef_camera"] = np.asarray(d["T_eef_camera"], dtype=float)
    return d


def save_calibration(path: str, T_eef_camera: np.ndarray, note: str = "") -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    data = {"T_eef_camera": np.asarray(T_eef_camera, dtype=float).tolist(),
            "note": note}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("手眼标定已保存: %s", path)


def pixel_to_base(px: tuple[float, float], depth_m: float,
                  intrinsics: dict, T_eef_camera: np.ndarray,
                  eef_pose: dict) -> np.ndarray:
    """像素点 + 深度 → Base 系 3D 坐标。

    px: (u, v)；depth_m: 该像素深度（米）；intrinsics: fx/fy/cx/cy；
    T_eef_camera: 4x4 手眼矩阵；eef_pose: 当前末端位姿 dict。
    """
    fx = intrinsics["fx"]
    fy = intrinsics["fy"]
    cx = intrinsics["cx"]
    cy = intrinsics["cy"]
    x = (px[0] - cx) * depth_m / fx
    y = (px[1] - cy) * depth_m / fy
    p_cam = np.array([x, y, depth_m, 1.0])
    T_base_eef = pose_to_matrix(eef_pose)
    p_base = T_base_eef @ np.asarray(T_eef_camera, dtype=float) @ p_cam
    return p_base[:3]
