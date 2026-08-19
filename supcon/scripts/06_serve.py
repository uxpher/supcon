#!/usr/bin/env python3
"""步骤6：启动竞赛软件对接服务。

    python scripts/06_serve.py [--config config.yaml] [--unsafe-free-path]
        [--effort-guard] [--effort-guard-threshold X]

启动后在竞赛操作软件里把 Base URL 填 http://127.0.0.1:5000 即可。
自测：curl http://127.0.0.1:5000/api/health
      curl -X POST http://127.0.0.1:5000/api/task1/execute -H "Content-Type: application/json" -d "{}"
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
    ap.add_argument("--unsafe-free-path", action="store_true",
                    help="危险：仅 Task1 使用 OMPL 自由路径并关闭软件安全监控；Task2/3 接口禁用")
    args = ap.parse_args()

    cfg = load_config(args.config)
    # 命令行显式双参数齐全才覆盖启用；否则尊重 config.yaml 的 effort_guard_enabled（默认 false）
    if args.effort_guard and args.effort_guard_threshold is not None:
        cfg.safety.effort_guard_enabled = True
        cfg.safety.effort_guard_threshold = args.effort_guard_threshold
    if args.unsafe_free_path:
        cfg.arm.allow_ompl_fallback = True
        cfg.arm.force_free_path = True
        cfg.task1.unsafe_free_path = True
        cfg.task1.unsafe_disable_safety_checks = True

    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    app = create_app(cfg)
    print(f"算法服务启动: http://{cfg.service.host}:{cfg.service.port}")
    print("竞赛软件 Base URL 填写: http://127.0.0.1:%d" % cfg.service.port)
    if cfg.safety.effort_guard_enabled:
        print("力矩绝对值上限急停: 启用（阈值 %.1f Nm）" % cfg.safety.effort_guard_threshold)
    else:
        print("力矩绝对值上限急停: 未启用（可在 config.yaml 或 --effort-guard 开启）")
    if args.unsafe_free_path:
        print("⚠️ Task1 不安全自由路径: 已启用；仅允许调用 /api/task1/execute，保持急停可用")
    uvicorn.run(app, host=cfg.service.host, port=cfg.service.port)


if __name__ == "__main__":
    main()
