"""通用工具：日志、姿态矩阵运算。"""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime

import numpy as np


def now_text() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """初始化日志：控制台 + 可选文件。"""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format=fmt, force=True)
    if log_file:
        d = os.path.dirname(log_file)
        if d:
            os.makedirs(d, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(fmt))
        logging.getLogger().addHandler(fh)


def rpy_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """XYZ 固定轴欧拉角 → 3x3 旋转矩阵：R = Rz(yaw)·Ry(pitch)·Rx(roll)。

    与 FTArm B9 文档「姿态 roll/pitch/yaw = rad（XYZ 固定轴欧拉角）」一致。
    """
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def pose_to_matrix(pose: dict) -> np.ndarray:
    """{x,y,z,roll,pitch,yaw} → 4x4 齐次变换矩阵（世界系下的末端位姿）。"""
    T = np.eye(4)
    T[:3, :3] = rpy_to_matrix(pose["roll"], pose["pitch"], pose["yaw"])
    T[:3, 3] = [pose["x"], pose["y"], pose["z"]]
    return T
