#!/usr/bin/env python3
"""步骤2：把机械臂当前位置写入面板标定文件（开关位姿示教）。

用法：
  # 1) 在网页控制面板 http://<臂IP>:8087/ 手动把臂摆到目标位置
  #    （例如：指尖悬在开关0正上方）→ 记录 approach_pose：
  python scripts/02_record_pose.py --switch 0 --key approach_pose

  # 2) 继续手动摆到"按钮压到底"的位置 → 记录 press_pose：
  python scripts/02_record_pose.py --switch 0 --key press_pose

  # 3) 拨动开关：拨动起点/终点/上方
  python scripts/02_record_pose.py --switch 2 --key flick_start_pose
  python scripts/02_record_pose.py --switch 2 --key flick_end_pose
  python scripts/02_record_pose.py --switch 2 --key approach_pose

  # 其它命令：
  python scripts/02_record_pose.py --list                # 查看已记录内容
  python scripts/02_record_pose.py --verify              # plan_only 校验所有位姿是否可直线到达
  python scripts/02_record_pose.py --goto 0.275 -0.2 0.5 # 直线移动到某处（自动使能）
  python scripts/02_record_pose.py --where               # 打印当前末端位姿（抄进 config.yaml 用）
  python scripts/02_record_pose.py --to-safe             # 回安全位
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon_task2.config import load_config
from supcon_task2.robot.arm import ArmError, B9Client
from supcon_task2.tasks.task1 import load_panel
from supcon_task2.utils import setup_logging

POSE_KEYS = ("approach_pose", "press_pose", "flick_start_pose", "flick_end_pose")


def save_panel(cfg, panel):
    with open(cfg.resolve(cfg.task1.panel_file), "w", encoding="utf-8") as f:
        json.dump(panel, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="开关位姿示教/记录")
    ap.add_argument("--switch", type=int, help="开关编号 0/1/2")
    ap.add_argument("--key", choices=POSE_KEYS, help="要写入的位姿字段")
    ap.add_argument("--goto", nargs="+", type=float,
                    help="直线移动到 x y z [roll pitch yaw]（先使能）")
    ap.add_argument("--to-safe", action="store_true", help="回安全位")
    ap.add_argument("--where", action="store_true", help="打印当前末端位姿")
    ap.add_argument("--list", action="store_true", help="查看面板文件内容")
    ap.add_argument("--verify", action="store_true", help="plan_only 校验全部已记录位姿")
    a = ap.parse_args()

    cfg = load_config()
    setup_logging("INFO", None)
    arm = B9Client(cfg.arm)
    panel = load_panel(cfg.resolve(cfg.task1.panel_file))

    if a.goto:
        ok, why = arm.healthy()
        if not ok:
            sys.exit(f"机械臂电机异常: {why}")
        arm.enable()
        xyz = a.goto
        pose = {"x": xyz[0], "y": xyz[1], "z": xyz[2],
                "roll": cfg.arm.default_rpy[0], "pitch": cfg.arm.default_rpy[1],
                "yaw": cfg.arm.default_rpy[2]}
        if len(xyz) >= 6:
            pose.update(roll=xyz[3], pitch=xyz[4], yaw=xyz[5])
        arm.goto_pose(pose, vel=0.1, plan_only=True)
        arm.goto_pose(pose, vel=0.1)
        print("已到达:", arm.pose())
        return

    if a.where:
        pose = arm.pose()
        if not pose:
            sys.exit("取不到末端位姿（TF 未就绪），稍后重试")
        print(f"当前末端位姿:\n  x={pose['x']:.4f}  y={pose['y']:.4f}  z={pose['z']:.4f}\n"
              f"  roll={pose['roll']:.4f}  pitch={pose['pitch']:.4f}  yaw={pose['yaw']:.4f}")
        print("（可把以上数值填入 config.yaml 的 observe_pose / safe_pose）")
        return

    if a.to_safe:
        arm.goto_pose(cfg.arm.safe_pose, vel=0.1)
        print("已回安全位:", arm.pose())
        return

    if a.list:
        print(json.dumps(panel, ensure_ascii=False, indent=2))
        return

    if a.verify:
        for sw in panel["switches"]:
            for k in POSE_KEYS:
                p = sw.get(k)
                if not p:
                    continue
                try:
                    arm.goto_pose(p, plan_only=True)
                    print(f"开关{sw['id']}.{k}: ✅ 可达")
                except ArmError as e:
                    print(f"开关{sw['id']}.{k}: ⚠️ {e}")
        return

    if a.switch is None or a.key is None:
        ap.error("需要 --switch 和 --key（或使用 --list/--verify/--goto/--to-safe）")

    pose = arm.pose()
    if not pose:
        sys.exit("取不到末端位姿（TF 未就绪），稍后重试")
    sw = panel["switches"][a.switch]
    sw[a.key] = pose
    save_panel(cfg, panel)
    print(f"已记录 开关{a.switch}.{a.key} = {pose}")


if __name__ == "__main__":
    main()
