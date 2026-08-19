#!/usr/bin/env python3
"""离线冒烟测试：mock 机械臂 + mock 灵巧手 + 模拟相机，全流程跑一遍任务1。

不需要任何真实硬件。运行：
    python tests/smoke_mock.py
"""
import pathlib
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from mocks.mock_arm import MockArmServer
from mocks.mock_hand import MockHandServer
from supcon.config import load_config
from supcon.robot.arm import B9Client
from supcon.robot.hand import O10Client
from supcon.tasks.task1 import Task1Runner
from supcon.utils import setup_logging
from supcon.vision.camera import MockCamera


def main():
    setup_logging("INFO", None)
    arm_srv = MockArmServer(("127.0.0.1", 18087), seconds_per_meter=0.0)
    hand_srv = MockHandServer(("127.0.0.1", 18088))
    threading.Thread(target=arm_srv.serve_forever, daemon=True).start()
    threading.Thread(target=hand_srv.serve_forever, daemon=True).start()

    cfg = load_config()
    cfg.arm.base_url = "http://127.0.0.1:18087"
    cfg.hand.base_url = "http://127.0.0.1:18088"
    cfg.task1.press_dwell_s = 0.01
    cfg.task1.max_retry = 1

    lamps = [{"id": 0, "switch_id": 2, "cx": 150, "cy": 240, "roi_radius": 18},
             {"id": 1, "switch_id": 0, "cx": 320, "cy": 240, "roi_radius": 18},
             {"id": 2, "switch_id": 1, "cx": 490, "cy": 240, "roi_radius": 18}]

    def pose(z, y=-0.16):
        return {"x": 0.275, "y": y, "z": z,
                "roll": -3.141, "pitch": -1.552, "yaw": 3.141}

    panel = {
        "lamps": lamps,
        "switches": [
            {"id": 0, "type": "button",
             "approach_pose": pose(0.50), "press_pose": pose(0.46)},
            {"id": 1, "type": "button",
             "approach_pose": pose(0.50), "press_pose": pose(0.46)},
            {"id": 2, "type": "toggle",
             "approach_pose": pose(0.50),
             "flick_start_pose": pose(0.46, y=-0.18),
             "flick_end_pose": pose(0.46, y=-0.14)},
        ],
    }
    cfg.task1.panel = panel

    arm = B9Client(cfg.arm)
    hand = O10Client(cfg.hand)
    camera = MockCamera(lamps=lamps, lit_index=1)
    runner = Task1Runner(cfg, arm, hand, camera, safety=None)

    ok, msg = runner.run()
    print(f"冒烟测试结果: success={ok} message={msg}")

    arm_srv.shutdown()
    hand_srv.shutdown()
    assert ok, msg
    assert "switch 0" in msg, "必须按 lamp.switch_id 映射，而非数组下标"
    print("✅ 全流程跑通：观察 → 检测亮灯 → 按压/拨动 → 回安全位")


if __name__ == "__main__":
    main()
