#!/usr/bin/env python3
"""在真机运行前校验 Task2/3 场景文件，并可仅规划静态示教位姿。

Task3 的抓取位不是固定示教点：它将在运行时从 RGB-D 计算，并由任务代码
在每次接触前 plan_only。因此本脚本只预检观察位、目标槽位和标定文件。
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.robot.arm import B9Client
from supcon.tasks.common import load_scene
from supcon.tasks.task3 import Task3Runner
from supcon.vision.handeye import load_calibration


def required(data: dict, keys: tuple[str, ...], label: str) -> list[dict]:
    poses = []
    for key in keys:
        if not data.get(key):
            raise ValueError(f"{label} 缺少 {key}")
        poses.append(data[key])
    return poses


def validate_task2(scene: dict) -> list[dict]:
    poses = required(scene, ("observe_pose",), "scene")
    sources = scene.get("sources") or {}
    if set(sources) != {"left", "midleft", "midright", "right"}:
        raise ValueError("Task2 sources 必须为 left/midleft/midright/right")
    for name, source in sources.items():
        poses.extend(required(source, ("approach_pose", "grasp_tcp_pose", "lift_pose"), f"source {name}"))
    destinations = scene.get("table_placements") or {}
    if set(destinations) != {"1", "2", "3", "4"}:
        raise ValueError("Task2 table_placements 必须为 1..4")
    for name, destination in destinations.items():
        poses.extend(required(destination, ("approach_pose", "place_pose", "retreat_pose"), f"destination {name}"))
    return poses


def validate_task3(cfg, task_cfg, scene: dict) -> list[dict]:
    # 复用运行时同一套静态配置检查，确保预检结果等价于任务启动前检查。
    Task3Runner(cfg, None, None, None, None, task_cfg)._validate_scene(scene)
    calibration_file = scene["calibration_file"]
    calibration_path = calibration_file if pathlib.Path(calibration_file).is_absolute() else cfg.resolve(calibration_file)
    if load_calibration(calibration_path, require_tcp=True) is None:
        raise ValueError(f"Task3 手眼/TCP 标定文件不存在: {calibration_path}")
    poses = [scene["observe_pose"]]
    for destination in scene["destinations"].values():
        poses.extend(required(destination, ("approach_pose", "place_pose", "retreat_pose"), "destination"))
    return poses


def main() -> None:
    parser = argparse.ArgumentParser(description="Task2/Task3 现场标定文件预检")
    parser.add_argument("--task", choices=("2", "3"), required=True)
    parser.add_argument("--plan-only", action="store_true", help="同时请求 B9 仅规划静态示教位姿")
    args = parser.parse_args()
    cfg = load_config()
    task_cfg = cfg.task2 if args.task == "2" else cfg.task3
    scene = load_scene(cfg.resolve(task_cfg.scene_file))
    poses = validate_task2(scene) if args.task == "2" else validate_task3(cfg, task_cfg, scene)
    print(f"✅ Task{args.task} 场景结构正确：{len(poses)} 个静态示教位姿")
    if args.task == "3":
        print("   动态预抓/抓取/抬升位将在 RGB-D 检测后由任务逐个 plan_only。")
    if args.plan_only:
        arm = B9Client(cfg.arm)
        ok, why = arm.healthy()
        if not ok:
            raise SystemExit(f"机械臂不健康：{why}")
        arm.enable()
        for index, pose in enumerate(poses, 1):
            arm.goto_pose(pose, vel=task_cfg.fine_vel, plan_only=True)
            print(f"  {index:02d}/{len(poses)} ✅ 可规划")


if __name__ == "__main__":
    main()
