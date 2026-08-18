#!/usr/bin/env python3
"""步骤6：启动竞赛软件对接服务。

    python scripts/06_serve.py [--config config.yaml] [--effort-guard] [--effort-guard-threshold X]

启动后在竞赛操作软件里把 Base URL 填 http://127.0.0.1:5000 即可。
自测：curl http://127.0.0.1:5000/api/health
      curl -X POST http://127.0.0.1:5000/api/task1/execute
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import uvicorn

from supcon.config import load_config
from supcon.service import create_app
from supcon.utils import setup_logging


def main():
    ap = argparse.ArgumentParser(description="启动竞赛软件对接服务")
    ap.add_argument("--config", default=None,
                    help="config.yaml 路径（默认项目 config/config.yaml）")
    ap.add_argument("--effort-guard", action="store_true",
                    help="启用力矩绝对值上限急停")
    ap.add_argument("--effort-guard-threshold", type=float, default=None,
                    help="力矩绝对值上限(Nm)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    # 命令行显式双参数齐全才覆盖启用；否则尊重 config.yaml 的 effort_guard_enabled（默认 false）
    if args.effort_guard and args.effort_guard_threshold is not None:
        cfg.safety.effort_guard_enabled = True
        cfg.safety.effort_guard_threshold = args.effort_guard_threshold

    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    app = create_app(cfg)
    print(f"算法服务启动: http://{cfg.service.host}:{cfg.service.port}")
    print("竞赛软件 Base URL 填写: http://127.0.0.1:%d" % cfg.service.port)
    if cfg.safety.effort_guard_enabled:
        print("力矩绝对值上限急停: 启用（阈值 %.1f Nm）" % cfg.safety.effort_guard_threshold)
    else:
        print("力矩绝对值上限急停: 未启用（可在 config.yaml 或 --effort-guard 开启）")
    uvicorn.run(app, host=cfg.service.host, port=cfg.service.port)


if __name__ == "__main__":
    main()
