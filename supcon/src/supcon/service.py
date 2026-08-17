"""竞赛软件对接 HTTP 服务（FastAPI）。

接口契约（《算法与竞赛操作软件对接及说明文档》）：
  GET  /api/health        → {"success": true, "message": "ready"}
  POST /api/task1/execute → 请求体空 {}，同步执行完整任务后返回，只认 success
任务 1/2/3 均由现场标定文件驱动；缺少标定文件时对应任务安全返回 success=false。
"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import AppConfig
from .robot.arm import B9Client
from .robot.hand import O10Client
from .robot.safety import SafetyMonitor
from .tasks.task1 import Task1Runner
from .tasks.task2 import Task2Runner
from .tasks.task3 import Task3Runner
from .utils import setup_logging
from .vision.camera import make_camera

log = logging.getLogger("service")


def build_runtime(cfg: AppConfig):
    """构造全部运行时组件（臂/手/相机/安全监控/任务执行器）。"""
    arm = B9Client(cfg.arm)
    hand = O10Client(cfg.hand)
    camera = make_camera(cfg.camera)
    safety = SafetyMonitor(arm, hand, cfg.safety)
    runners = {
        "task1": Task1Runner(cfg, arm, hand, camera, safety),
        "task2": Task2Runner(cfg, arm, hand, camera, safety, cfg.task2),
        "task3": Task3Runner(cfg, arm, hand, camera, safety, cfg.task3),
    }
    return arm, hand, camera, safety, runners


def create_app(cfg: AppConfig) -> FastAPI:
    setup_logging(cfg.logging.get("level", "INFO"), cfg.resolve(cfg.logging.get("file", "")))
    arm, hand, camera, safety, runners = build_runtime(cfg)
    lock = threading.Lock()  # 任务接口串行化：竞赛软件不会并发调，但保险起见

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        safety.start()
        log.info("安全监控线程已启动")
        yield
        safety.stop()
        camera.close()

    app = FastAPI(title="supcon-task2", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        """健康检查。服务进程活着就返回 success=true；message 附带设备连通性提示。"""
        failures = []
        try:
            if not arm.healthy()[0]:
                failures.append("arm not healthy")
        except Exception:
            failures.append("arm unreachable")
        try:
            if not hand.status().get("connected"):
                failures.append("hand not connected")
        except Exception:
            failures.append("hand unreachable")
        return {"success": not failures, "message": "ready" if not failures else "; ".join(failures)}

    @app.post("/api/task1/execute")
    def task1():
        """任务1入口：同步执行完整流程后返回。"""
        with lock:
            ok, msg = runners["task1"].run()
        return {"success": ok, "message": msg}

    @app.post("/api/task2/execute")
    def task2():
        with lock:
            ok, msg = runners["task2"].run()
        return {"success": ok, "message": msg}

    @app.post("/api/task3/execute")
    def task3():
        with lock:
            ok, msg = runners["task3"].run()
        return {"success": ok, "message": msg}

    @app.get("/debug/state")
    def state():
        """调试用：查看当前臂/手状态。"""
        try:
            pose = arm.pose()
        except Exception as e:
            pose = {"error": str(e)}
        try:
            hand_status = hand.status()
        except Exception as e:
            hand_status = {"error": str(e)}
        return {"arm_pose": pose, "hand": hand_status,
                "safety_emergency": safety.is_emergency(),
                "safety_reason": safety.reason}

    return app
