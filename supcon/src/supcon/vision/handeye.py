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


def _as_transform(value, name: str) -> np.ndarray:
    """读取并严格校验刚体变换，拒绝不完整/错误方向的标定文件。"""
    T = np.asarray(value, dtype=float)
    if T.shape != (4, 4) or not np.all(np.isfinite(T)):
        raise ValueError(f"{name} 必须是元素有限的 4x4 矩阵")
    if not np.allclose(T[3], [0, 0, 0, 1], atol=1e-6):
        raise ValueError(f"{name} 最后一行必须为 [0,0,0,1]")
    R = T[:3, :3]
    if not np.allclose(R.T @ R, np.eye(3), atol=2e-3) or not np.isclose(np.linalg.det(R), 1.0, atol=2e-3):
        raise ValueError(f"{name} 的旋转部分不是有效旋转矩阵")
    return T


def load_calibration(path: str, require_tcp: bool = False) -> dict | None:
    """读取 calibration.json。

    ``T_eef_camera`` 表示相机坐标到 B9 末端坐标；Task3 动态抓取还必须
    有 ``T_eef_tcp``（实际抓取 TCP 到 B9 末端的固定变换），否则不能把
    视觉目标安全地下发为末端位姿。
    """
    if not path or not os.path.exists(path):
        log.warning("手眼标定文件不存在: %s", path)
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if "T_eef_camera" not in d:
        raise ValueError("标定文件缺少 T_eef_camera")
    d["T_eef_camera"] = _as_transform(d["T_eef_camera"], "T_eef_camera")
    if require_tcp:
        if "T_eef_tcp" not in d:
            raise ValueError("Task3 标定文件缺少 T_eef_tcp（实际抓取 TCP 外参）")
        d["T_eef_tcp"] = _as_transform(d["T_eef_tcp"], "T_eef_tcp")
    elif "T_eef_tcp" in d:
        d["T_eef_tcp"] = _as_transform(d["T_eef_tcp"], "T_eef_tcp")
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


def camera_to_base(points_camera: np.ndarray, T_eef_camera: np.ndarray,
                   eef_pose: dict) -> np.ndarray:
    """相机系 3D 点（N×3 或 3）转换至 B9 基座系。"""
    p = np.asarray(points_camera, dtype=float)
    one = p.ndim == 1
    p = p.reshape(1, 3) if one else p
    if p.ndim != 2 or p.shape[1] != 3:
        raise ValueError("points_camera 必须为 3 或 N×3")
    h = np.column_stack((p, np.ones(len(p))))
    T_base_camera = pose_to_matrix(eef_pose) @ _as_transform(T_eef_camera, "T_eef_camera")
    result = (T_base_camera @ h.T).T[:, :3]
    return result[0] if one else result
