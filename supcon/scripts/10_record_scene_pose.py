#!/usr/bin/env python3
"""步骤 10：Task2 源/目标动作位、Task3 目标槽位记录 → 写待核验文件。

只写 check_pos/Task{2|3}_场景位姿_待核验.json，**不改 config.yaml**，审核后手动填入 task2.scene / task3.scene。
（安全位/观察位由 09_record_arm_pose.py 记录，本脚本只管「抓取/放置」动作位。）

待核验文件字段：
  Task2 sources.{left|midleft|midright|right}.approach_pose / grasp_tcp_pose / lift_pose   ← 源槽位三段（观察位走全局 observe_pose）
  Task2 table_placements.{1|2|3|4}.approach_pose / place_pose / retreat_pose               ← 台面放置三段
  Task3 observe_pose 由 09_record_arm_pose.py 记录；动态抓取位由 RGB-D 在运行时计算
  Task3 destinations.{形状}.approach_pose / place_pose / retreat_pose                         ← 目标槽三段

摆位方式：网页面板/teach_mode 手动摆到位 → 记录。

用法：
  python 10_record_scene_pose.py --task 2 --where
  python 10_record_scene_pose.py --task 2 --source left --key approach_pose
  python 10_record_scene_pose.py --task 2 --source left --key grasp_tcp_pose
  python 10_record_scene_pose.py --task 2 --source left --key lift_pose
  python 10_record_scene_pose.py --task 2 --dest 1 --key place_pose        # Task2 台面放置位
  python 10_record_scene_pose.py --task 3 --dest block --key place_pose    # Task3 形状槽放置位
  python 10_record_scene_pose.py --task 2 --show
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.robot.arm import B9Client
from supcon.utils import setup_logging

SCENE_FILES = {"2": "check_pos/Task2_场景位姿_待核验.json",
               "3": "check_pos/Task3_场景位姿_待核验.json"}
TASK2_DEST_NAMES = ("1", "2", "3", "4")
TASK3_DEST_NAMES = ("block", "hexagonal_prism", "triangular_prism", "cylinder")
# Task3 没有固定源工位，只有全局桌面观察位和目标槽位。
TASK2_SOURCE_NAMES = ("left", "midleft", "midright", "right")


def _source_names(task: str) -> tuple:
    return TASK2_SOURCE_NAMES if task == "2" else ()


def _source_keys(task: str) -> tuple:
    """Task2 源工位的三段动作位；Task3 没有固定源工位。"""
    if task == "2":
        return ("approach_pose", "grasp_tcp_pose", "lift_pose")
    return ()


def _dest_keys(task: str) -> tuple:
    """目标放置位需示教的三段动作位。"""
    return ("approach_pose", "place_pose", "retreat_pose")


def _empty(task: str) -> dict:
    dest_key = "table_placements" if task == "2" else "destinations"
    dest_names = TASK2_DEST_NAMES if task == "2" else TASK3_DEST_NAMES
    data = {
        "_comment": (
            f"Task{task} 场景动作位待核验（机械臂末端 x/y/z/roll/pitch/yaw，米/弧度，B9 base 系）。"
            f"{dest_key}.*=目标放置位（approach_pose / place_pose / retreat_pose）。"
            f"审核后手动填入 task{task}.json。本文件不改动任何正式配置。"
        ),
        dest_key: {n: {k: None for k in _dest_keys(task)} for n in dest_names},
    }
    if task == "2":
        data["sources"] = {n: {k: None for k in _source_keys(task)} for n in _source_names(task)}
    else:
        data["_comment"] += " Task3 源物体由 RGB-D 动态定位，勿填写固定抓取坐标。"
    return data


def _load(path: str, task: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = _empty(task)
    data.setdefault("_comment", _empty(task)["_comment"])
    if task == "2":
        data.setdefault("sources", {n: {k: None for k in _source_keys(task)} for n in _source_names(task)})
    dest_key = "table_placements" if task == "2" else "destinations"
    dest_names = TASK2_DEST_NAMES if task == "2" else TASK3_DEST_NAMES
    data.setdefault(dest_key, {n: {k: None for k in _dest_keys(task)} for n in dest_names})
    return data


def _save(path: str, data: dict) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _current_pose(arm) -> dict:
    pose = arm.pose()
    if not pose:
        sys.exit("取不到末端位姿（TF 未就绪），稍后重试")
    return {k: float(pose[k]) for k in ("x", "y", "z", "roll", "pitch", "yaw")}


def _print_pose(pose):
    print(f"当前末端位姿: x={pose['x']:.4f} y={pose['y']:.4f} z={pose['z']:.4f} "
          f"roll={pose['roll']:.4f} pitch={pose['pitch']:.4f} yaw={pose['yaw']:.4f}")


def main():
    ap = argparse.ArgumentParser(description="Task2/3 场景动作位记录（只写待核验文件）")
    ap.add_argument("--task", choices=("2", "3"), required=True)
    ap.add_argument("--where", action="store_true", help="打印当前末端位姿")
    ap.add_argument("--key", help="Task2: approach_pose/grasp_tcp_pose/lift_pose；目标槽: approach_pose/place_pose/retreat_pose")
    ap.add_argument("--source", type=str, help="仅 Task2 源工位：left/midleft/midright/right")
    ap.add_argument("--dest", type=str, help="目标放置位 key：Task2 数字 1-4；Task3 形状名")
    ap.add_argument("--show", action="store_true", help="查看待核验文件")
    a = ap.parse_args()

    cfg = load_config()
    setup_logging("INFO", None)
    arm = B9Client(cfg.arm)
    task = a.task

    if a.where:
        _print_pose(_current_pose(arm))
        return

    if a.show:
        p = cfg.resolve(SCENE_FILES[task])
        print(json.dumps(_load(p, task), ensure_ascii=False, indent=2))
        print(f"\n（待核验文件位置: {p}）")
        return

    if not a.key:
        ap.error("需要 --key（或 --where / --show）")

    pose = _current_pose(arm)
    p = cfg.resolve(SCENE_FILES[task])
    data = _load(p, task)
    dest_key = "table_placements" if task == "2" else "destinations"

    if a.source is not None:
        if task != "2":
            ap.error("Task3 源物体位置不固定，不接受 --source；请只记录目标槽位 --dest")
        if a.key not in _source_keys(task):
            ap.error(f"--source 只支持 {_source_keys(task)}")
        if a.source not in data["sources"]:
            ap.error(f"Task2 没有源 key「{a.source}」，合法值：{list(data['sources'])}")
        data["sources"][a.source][a.key] = pose
        where = f"sources.{a.source}.{a.key}"
    elif a.dest is not None:
        if a.key not in _dest_keys(task):
            ap.error(f"--dest 只支持 {_dest_keys(task)}")
        if a.dest not in data[dest_key]:
            ap.error(f"Task{task} 没有目标 key「{a.dest}」，合法值：{list(data[dest_key])}")
        data[dest_key][a.dest][a.key] = pose
        where = f"{dest_key}.{a.dest}.{a.key}"
    else:
        ap.error("源工位用 --source N；目标用 --dest NAME")

    _save(p, data)
    print(f"已记录 Task{task}.{where}:")
    _print_pose(pose)
    print(f"→ 已写入待核验文件: {p}")
    print(f"→ 未改动 task{task}.json，审核后请手动填入")


if __name__ == "__main__":
    main()
