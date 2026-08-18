#!/usr/bin/env python3
"""步骤5：直接跑一遍任务2（不经过 HTTP，便于看日志排查）。

    python scripts/05_test_task2.py [--effort-guard] [--effort-guard-threshold X]

需先完成 task2.json 现场标定，否则会安全返回 success=false。
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.service import build_runtime
from supcon.utils import setup_logging


def main():
    ap = argparse.ArgumentParser(description="任务2 直跑测试")
    ap.add_argument("--effort-guard", action="store_true", help="启用力矩绝对值上限急停")
    ap.add_argument("--effort-guard-threshold", type=float, default=None,
                    help="力矩绝对值上限(Nm)")
    args = ap.parse_args()

    cfg = load_config()
    if args.effort_guard and args.effort_guard_threshold is not None:
        cfg.safety.effort_guard_enabled = True
        cfg.safety.effort_guard_threshold = args.effort_guard_threshold

    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    arm, hand, camera, safety, runners = build_runtime(cfg)
    safety.start()
    try:
        ok, msg = runners["task2"].run()
    finally:
        safety.stop()
        camera.close()
    print(f"\n结果: success={ok} message={msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
