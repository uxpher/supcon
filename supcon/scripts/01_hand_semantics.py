#!/usr/bin/env python3
"""步骤1：实测 O10 灵巧手 0/1 张开/闭合语义。

官方文档 §3.1 注释与 §4.6 示例对"张手/握拳"的 0/1 描述互相矛盾。
上机第一件事就是跑这个脚本：发 0 和 1，看 joint_rad 靠近上界还是下界，
据此修改 config.yaml 里的 hand.open_pose / close_pose / point_pose。

判据：joint_rad 靠近弧度范围上界 = 弯曲/闭合；靠近下界 = 伸展/张开。
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.robot.hand import JOINT_NAMES, RAD_RANGES, O10Client
from supcon.utils import setup_logging


def main():
    cfg = load_config()
    setup_logging("INFO", None)
    hand = O10Client(cfg.hand)

    s = hand.status()
    print(f"连接状态: connected={s.get('connected')} "
          f"hand_type={s.get('hand_type')} dof={s.get('dof')}")

    for value in (1, 0):
        print(f"\n>>> 发送 set_pos([{value}]*10) ...")
        hand.set_pos([value] * 10)
        time.sleep(0.8)
        st = hand.status()
        rad = st.get("joint_rad") or []
        print(f"    joint_rad = {[round(r, 3) for r in rad]}")
        for i, (lo, hi) in enumerate(RAD_RANGES):
            if i >= len(rad):
                continue
            r = rad[i]
            if r > lo + 0.9 * (hi - lo):
                side = "闭合侧（靠近上界）"
            elif r < lo + 0.1 * (hi - lo):
                side = "张开侧（靠近下界）"
            else:
                side = "中间"
            print(f"    [{i}] {JOINT_NAMES[i]:<14} rad={r:+.3f}  → {side}")

    print("\n========== 结论 ==========")
    print("若 value=1 时指关节靠近上界 → 1=弯曲(握拳)、0=伸展(张手)；反之相反。")
    print("据此修改 config.yaml：")
    print("  hand.open_pose   ← 让手指完全张开的向量")
    print("  hand.close_pose  ← 让手指完全闭合的向量")
    print("  hand.point_pose  ← 食指伸直、其余收拢的点按姿态")


if __name__ == "__main__":
    main()
