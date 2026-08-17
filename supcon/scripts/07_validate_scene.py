#!/usr/bin/env python3
"""校验 Task2/Task3 现场标定文件的结构与所有示教位姿的可达性。

示例：
  cp config/templates/task2.example.json config/runtime/task2.json
  # 填写真实 ROI、手型和位姿后：
  python scripts/07_validate_scene.py --task 2 --plan-only
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon_task2.config import load_config
from supcon_task2.robot.arm import B9Client
from supcon_task2.tasks.common import load_scene


def required(data: dict, keys: tuple[str, ...], label: str) -> list[dict]:
    poses = []
    for key in keys:
        if not data.get(key):
            raise ValueError(f"{label} 缺少 {key}")
        poses.append(data[key])
    return poses


def main() -> None:
    parser = argparse.ArgumentParser(description="Task2/3 现场标定文件预检")
    parser.add_argument("--task", choices=("2", "3"), required=True)
    parser.add_argument("--plan-only", action="store_true", help="同时请求 B9 仅规划校验所有位姿")
    args = parser.parse_args()
    cfg = load_config()
    task_cfg = cfg.task2 if args.task == "2" else cfg.task3
    scene = load_scene(cfg.resolve(task_cfg.scene_file))
    poses = []
    # 观察位：Task2 全局 1 个；Task3 每个源工位 + 每个目标槽各 1 个（无全局观察位）
    if args.task == "2":
        poses.extend(required(scene, ("observe_pose",), "scene"))
    sources = scene.get("sources") or []
    if len(sources) != 4:
        raise SystemExit("sources 必须恰好为 4 个")
    for source in sources:
        src_keys = ["approach_pose", "grasp_tcp_pose", "lift_pose"]
        if args.task == "3":
            src_keys = ["observe_pose"] + src_keys   # Task3 源工位自带观察位
        poses.extend(required(source, tuple(src_keys), f"source {source.get('id')}"))
        if args.task == "2" and len(source.get("top_digit_roi") or []) != 4:
            raise SystemExit(f"source {source.get('id')} 的 top_digit_roi 必须是 [x,y,w,h]")
        if args.task == "3" and len(source.get("roi") or []) != 4:
            raise SystemExit(f"source {source.get('id')} 的 roi 必须是 [x,y,w,h]")
    destinations = scene.get("table_placements" if args.task == "2" else "destinations") or {}
    if len(destinations) != 4:
        raise SystemExit("必须配置 4 个目标放置位/槽位")
    for name, destination in destinations.items():
        dest_keys = ["approach_pose", "place_pose", "retreat_pose"]
        if args.task == "3":
            dest_keys = ["observe_pose"] + dest_keys   # Task3 目标槽自带观察位
        poses.extend(required(destination, tuple(dest_keys), f"destination {name}"))
    print(f"✅ Task{args.task} 标定文件结构正确：{len(poses)} 个末端位姿")
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
