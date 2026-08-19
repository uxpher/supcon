#!/usr/bin/env python3
"""步骤5：直接跑一遍任务2（不经过 HTTP，便于看日志排查）。

    python scripts/05_test_task2.py [--unsafe-free-path]
        [--effort-guard] [--effort-guard-threshold X]

需先完成 config.yaml 的 task2.scene 现场标定，否则会安全返回 success=false。
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.service import build_runtime
from supcon.tasks.task2 import Task2Runner
from supcon.utils import setup_logging


def main():
    ap = argparse.ArgumentParser(description="任务2 直跑测试")
    ap.add_argument("--effort-guard", action="store_true", help="启用力矩绝对值上限急停")
    ap.add_argument("--effort-guard-threshold", type=float, default=None,
                    help="力矩绝对值上限(Nm)")
    ap.add_argument("--unsafe-free-path", action="store_true",
                    help="危险：Task2 使用 OMPL 自由路径，跳过 plan_only 与软件安全监控")
    args = ap.parse_args()

    cfg = load_config()
    if args.effort_guard and args.effort_guard_threshold is not None:
        cfg.safety.effort_guard_enabled = True
        cfg.safety.effort_guard_threshold = args.effort_guard_threshold
    if args.unsafe_free_path:
        cfg.arm.allow_ompl_fallback = True
        cfg.arm.force_free_path = True
        cfg.task2.unsafe_free_path = True
        cfg.task2.unsafe_disable_safety_checks = True

    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    arm, hand, camera, safety, runners = build_runtime(cfg)
    if args.unsafe_free_path:
        safety = None
        runner = Task2Runner(cfg, arm, hand, camera, safety, cfg.task2)
    else:
        runner = runners["task2"]
    if safety is not None:
        safety.start()
    try:
        ok, msg = runner.run()
    finally:
        if safety is not None:
            safety.stop()
        camera.close()
    print(f"\n结果: success={ok} message={msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
