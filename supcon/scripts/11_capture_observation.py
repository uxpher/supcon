#!/usr/bin/env python3
"""在观察位采集 RGB-D 并保存到 image/，不执行抓取。

默认不驱动机械臂：请先用示教器将机械臂摆到观察位，再运行本脚本。
只有显式传入 --move 才会以“任务安全位 → 观察位”的顺序移动，适合已完成
安全位示教和直线规划确认后的现场调试。

示例：
  # 已人工摆到 Task3 观察位，只拍照（推荐首次使用）
  python scripts/11_capture_observation.py --task 3

  # 已确认路径安全，自动移动到 Task3 观察位再拍照
  python scripts/11_capture_observation.py --task 3 --move

输出（默认 image/）：
  task3_YYYYmmdd_HHMMSS_rgb.png       RGB 原图
  task3_YYYYmmdd_HHMMSS_depth_vis.png 深度伪彩图（若相机有深度）
  task3_YYYYmmdd_HHMMSS_depth.npy     原始深度矩阵 float32，单位米
  task3_YYYYmmdd_HHMMSS_meta.json     采集时间、相机内参、末端位姿
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.robot.arm import ArmError, B9Client
from supcon.tasks.common import scene_from_task_config
from supcon.utils import setup_logging
from supcon.vision.camera import make_camera
from supcon.vision.dump import depth_to_color


def _save_png(path: str, bgr: np.ndarray) -> None:
    """以 tofile 保存，兼容 Windows 中文目录。"""
    ok, data = cv2.imencode(".png", bgr)
    if not ok:
        raise RuntimeError(f"PNG 编码失败: {path}")
    data.tofile(path)


def _observe_pose(cfg, task: str) -> dict:
    if task == "1":
        return dict(cfg.arm.observe_pose)
    task_cfg = cfg.task2 if task == "2" else cfg.task3
    scene = scene_from_task_config(cfg, task_cfg, task)
    pose = scene.get("observe_pose")
    if not isinstance(pose, dict):
        raise RuntimeError(f"Task{task} 场景文件缺少 observe_pose，拒绝自动移动")
    required = ("x", "y", "z", "roll", "pitch", "yaw")
    if any(key not in pose for key in required):
        raise RuntimeError(f"Task{task}.observe_pose 不完整，拒绝自动移动")
    return dict(pose)


def _move_to_observation(cfg, task: str) -> dict:
    """显式 --move 时才调用；每一段先规划、后执行。"""
    arm = B9Client(cfg.arm)
    ok, reason = arm.healthy()
    if not ok:
        raise ArmError(f"机械臂不健康: {reason}")
    safe_pose = dict(getattr(cfg.arm, f"task{task}_safe_pose"))
    observe_pose = _observe_pose(cfg, task)
    arm.enable()
    if not arm.enabled_all():
        raise ArmError("机械臂未完全使能")
    # 必须在每一真实段的当前起点重新 plan_only，不能用批量终点预检代替。
    arm.goto_pose(safe_pose, vel=cfg.arm.velocity_slow, plan_only=True)
    arm.goto_pose(safe_pose, vel=cfg.arm.velocity_slow)
    arm.goto_pose(observe_pose, vel=cfg.arm.velocity_slow, plan_only=True)
    arm.goto_pose(observe_pose, vel=cfg.arm.velocity_slow)
    return arm.pose() or observe_pose


def main() -> None:
    parser = argparse.ArgumentParser(description="在观察位保存 RGB、深度矩阵和深度伪彩图")
    parser.add_argument("--task", choices=("1", "2", "3"), default="3", help="观察位所属任务，默认 3")
    parser.add_argument("--move", action="store_true", help="先移动：安全位 → 观察位（默认不移动）")
    parser.add_argument("--output-dir", default="image", help="输出目录，相对项目根目录，默认 image")
    args = parser.parse_args()

    cfg = load_config()
    setup_logging(cfg.logging.get("level", "INFO"), None)
    output_dir = cfg.resolve(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    pose = _move_to_observation(cfg, args.task) if args.move else None

    camera = make_camera(cfg.camera)
    try:
        rgb, depth = camera.grab_rgbd()
    finally:
        camera.close()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = os.path.join(output_dir, f"task{args.task}_{stamp}")
    rgb_path = f"{prefix}_rgb.png"
    _save_png(rgb_path, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    saved = [rgb_path]
    if depth is not None:
        depth = np.asarray(depth, dtype=np.float32)
        depth_path = f"{prefix}_depth.npy"
        np.save(depth_path, depth)
        depth_vis_path = f"{prefix}_depth_vis.png"
        _save_png(depth_vis_path, depth_to_color(depth))
        saved.extend((depth_path, depth_vis_path))

    metadata = {
        "timestamp": stamp,
        "task": int(args.task),
        "moved_by_script": bool(args.move),
        "eef_pose": pose,
        "camera_mode": cfg.camera.mode,
        "rgb_shape": list(rgb.shape),
        "depth_shape": list(depth.shape) if depth is not None else None,
        "depth_unit": "m" if depth is not None else None,
        "intrinsics": getattr(camera, "intrinsics", None),
    }
    metadata_path = f"{prefix}_meta.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    saved.append(metadata_path)
    print("采集完成：")
    for path in saved:
        print(f"  {path}")
    if not args.move:
        print("注：本次未移动机械臂；请确认拍摄时机械臂已位于目标观察位。")


if __name__ == "__main__":
    main()
