#!/usr/bin/env python3
"""步骤5：直接跑一遍任务1（不经过 HTTP，便于看日志排查）。

真机/模拟均可：完全取决于 config.yaml（camera.mode、base_url）。
    python scripts/05_test_task1.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon_task2.config import load_config
from supcon_task2.service import build_runtime
from supcon_task2.utils import setup_logging


def main():
    cfg = load_config()
    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    arm, hand, camera, safety, runners = build_runtime(cfg)
    safety.start()
    try:
        ok, msg = runners["task1"].run()
    finally:
        safety.stop()
        camera.close()
    print(f"\n结果: success={ok} message={msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
