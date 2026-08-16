#!/usr/bin/env python3
"""步骤6：启动竞赛软件对接服务。

    python scripts/06_serve.py [config.yaml路径]

启动后在竞赛操作软件里把 Base URL 填 http://127.0.0.1:5000 即可。
自测：curl http://127.0.0.1:5000/api/health
      curl -X POST http://127.0.0.1:5000/api/task1/execute
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import uvicorn

from supcon_task2.config import load_config
from supcon_task2.service import create_app
from supcon_task2.utils import setup_logging


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config(path)
    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    app = create_app(cfg)
    print(f"算法服务启动: http://{cfg.service.host}:{cfg.service.port}")
    print("竞赛软件 Base URL 填写: http://127.0.0.1:%d" % cfg.service.port)
    uvicorn.run(app, host=cfg.service.host, port=cfg.service.port)


if __name__ == "__main__":
    main()
