#!/usr/bin/env python3
"""步骤5：直接跑一遍任务1（不经过 HTTP，便于看日志排查）。

    python scripts/05_test_task1.py [--observe-only] [--effort-guard] [--effort-guard-threshold X]

完整任务取决于 config.yaml（camera.mode、base_url）。``--observe-only`` 不启动相机，
可在相机被占用时单独验证机械臂观察路径。
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.robot.arm import B9Client
from supcon.robot.hand import O10Client
from supcon.robot.safety import SafetyMonitor
from supcon.service import build_runtime
from supcon.tasks.task1 import Task1Runner
from supcon.utils import setup_logging


def main():
    ap = argparse.ArgumentParser(description="任务1 直跑测试")
    ap.add_argument("--observe-only", action="store_true",
                    help="只测试当前位置→安全位→观察位的差值路径；到观察位即停止")
    ap.add_argument("--unsafe-free-path", action="store_true",
                    help="危险：允许 OMPL 自由路径，跳过规划预览/软件安全监控；仍等待实际到位才拍照")
    ap.add_argument("--effort-guard", action="store_true", help="启用力矩绝对值上限急停")
    ap.add_argument("--effort-guard-threshold", type=float, default=None,
                    help="力矩绝对值上限(Nm)")
    args = ap.parse_args()

    cfg = load_config()
    if args.effort_guard and args.effort_guard_threshold is not None:
        cfg.safety.effort_guard_enabled = True
        cfg.safety.effort_guard_threshold = args.effort_guard_threshold
    if args.unsafe_free_path:
        cfg.arm.allow_ompl_fallback = True
        cfg.arm.force_free_path = True
        cfg.task1.unsafe_free_path = True
        cfg.task1.unsafe_disable_safety_checks = True

    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    if args.observe_only:
        # 此模式不读取图像、不识别灯，只需臂/手/安全监控；避免相机被其他
        # 进程占用时无法验证安全位→观察位的机械臂路径。
        arm = B9Client(cfg.arm)
        hand = O10Client(cfg.hand)
        camera = None
        safety = None if args.unsafe_free_path else SafetyMonitor(arm, hand, cfg.safety)
        runner = Task1Runner(cfg, arm, hand, camera, safety)
    else:
        arm, hand, camera, safety, runners = build_runtime(cfg)
        if args.unsafe_free_path:
            safety = None
            runner = Task1Runner(cfg, arm, hand, camera, safety)
        else:
            runner = runners["task1"]
    if safety is not None:
        safety.start()
    try:
        ok, msg = runner.run(observe_only=args.observe_only)
    finally:
        if safety is not None:
            safety.stop()
        if camera is not None:
            camera.close()
    print(f"\n结果: success={ok} message={msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
