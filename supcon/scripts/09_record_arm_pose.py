#!/usr/bin/env python3
"""步骤 9：机械臂 安全位 / 观察位 记录（只写待核验文件，不改正式配置）。

3 个任务的安全位**各自独立**（防止直线移动时碰撞），观察位也各自独立。
只写 check_pos/机械臂_安全位观察位_待核验.json，**绝不改 config.yaml / task2.json / task3.json**。

待核验文件字段：
  task1_safe_pose / task2_safe_pose / task3_safe_pose     ← 3 个任务各自安全位
  task1_observe_pose / task2_observe_pose / task3_observe_pose ← 3 个任务各自观察位

摆位方式（B9 有 teach_mode 拖动）：网页面板/teach_mode 手动摆到位 → 记录。

用法：
  python 09_record_arm_pose.py --where                        # 打印当前末端位姿
  python 09_record_arm_pose.py --task 1 --key safe_pose       # Task1 安全位
  python 09_record_arm_pose.py --task 2 --key safe_pose       # Task2 安全位
  python 09_record_arm_pose.py --task 3 --key safe_pose       # Task3 安全位
  python 09_record_arm_pose.py --task 1 --key observe_pose    # Task1 观察位
  python 09_record_arm_pose.py --task 2 --key observe_pose    # Task2 观察位
  python 09_record_arm_pose.py --task 3 --key observe_pose    # Task3 观察位
  python 09_record_arm_pose.py --show                         # 查看待核验文件
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

HOME_FILE = "check_pos/机械臂_安全位观察位_待核验.json"
TASKS = ("1", "2", "3")


def _empty() -> dict:
    return {
        "_comment": (
            "机械臂 安全位/观察位 待核验（x/y/z/roll/pitch/yaw，米/弧度，B9 base 系）。"
            "task1/2/3_safe_pose=各任务独立安全位（防直线移动碰撞）；"
            "task1/2/3_observe_pose=各任务观察位。"
            "审核后手动填入 config.yaml 的 arm.*_safe_pose / arm.*_observe_pose 或 task2.json/task3.json 的 observe_pose。"
            "本文件不改动任何正式配置。"
        ),
        **{f"task{t}_safe_pose": None for t in TASKS},
        **{f"task{t}_observe_pose": None for t in TASKS},
    }


def _load(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = _empty()
    data.setdefault("_comment", _empty()["_comment"])
    for t in TASKS:
        data.setdefault(f"task{t}_safe_pose", None)
        data.setdefault(f"task{t}_observe_pose", None)
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
    ap = argparse.ArgumentParser(description="机械臂 安全位/观察位 记录（只写待核验文件）")
    ap.add_argument("--where", action="store_true", help="打印当前末端位姿")
    ap.add_argument("--key", choices=("safe_pose", "observe_pose"), help="记录哪种位姿")
    ap.add_argument("--task", choices=TASKS, help="任务编号 1/2/3")
    ap.add_argument("--show", action="store_true", help="查看待核验文件")
    a = ap.parse_args()

    cfg = load_config()
    setup_logging("INFO", None)
    arm = B9Client(cfg.arm)

    if a.where:
        _print_pose(_current_pose(arm))
        return

    if a.show:
        p = cfg.resolve(HOME_FILE)
        print(json.dumps(_load(p), ensure_ascii=False, indent=2))
        print(f"\n（待核验文件位置: {p}）")
        return

    if not a.key or not a.task:
        ap.error("需要 --task 1|2|3 和 --key safe_pose|observe_pose（或 --where / --show）")

    pose = _current_pose(arm)
    field = f"task{a.task}_{a.key}"
    p = cfg.resolve(HOME_FILE)
    data = _load(p)
    data[field] = pose
    _save(p, data)
    print(f"已记录 {field}:")
    _print_pose(pose)
    print(f"→ 已写入待核验文件: {p}")
    print("→ 未改动任何正式配置，审核后请手动填入")


if __name__ == "__main__":
    main()
