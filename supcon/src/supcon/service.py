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

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

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

_TASK_FIELDS = ("task", "task_id", "taskId", "task_no", "taskNo", "task_name",
                "taskName", "task_type", "taskType")
_TASK_HEADERS = ("x-task", "x-task-id", "task", "task-id", "task_id", "taskid")


def _requested_task(payload: object, headers) -> str | None:
    """从赛题请求 JSON 字段或常见任务请求头解析 task1/task2。"""
    raw = None
    if isinstance(payload, dict):
        for field in _TASK_FIELDS:
            if payload.get(field) is not None:
                raw = payload[field]
                break
    if raw is None:
        for header in _TASK_HEADERS:
            if headers.get(header) is not None:
                raw = headers.get(header)
                break
    if raw is None:
        return None
    value = (str(raw).strip().lower().replace("_", "").replace("-", "")
             .replace(" ", ""))
    if value in {"1", "task1", "任务1", "任务一"}:
        return "task1"
    if value in {"2", "task2", "任务2", "任务二"}:
        return "task2"
    return None


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
    # 仅由 scripts/06_serve.py 的显式 unsafe 启动参数开启。不要让竞赛软件
    # 通过 HTTP 请求体或请求头切换该模式，避免一次普通调用意外关闭保护。
    task1_unsafe = bool(
        getattr(cfg.task1, "unsafe_free_path", False)
        and getattr(cfg.task1, "unsafe_disable_safety_checks", False)
        and getattr(cfg.arm, "force_free_path", False)
    )
    task2_unsafe = bool(
        getattr(cfg.task2, "unsafe_free_path", False)
        and getattr(cfg.task2, "unsafe_disable_safety_checks", False)
        and getattr(cfg.arm, "force_free_path", False)
    )
    if task1_unsafe != task2_unsafe:
        raise ValueError("统一 unsafe 服务必须同时启用 Task1 和 Task2")
    unsafe_mode = task1_unsafe  # 两项一致；命令行 --unsafe-free-path 同时设置。
    task1_runner = (Task1Runner(cfg, arm, hand, camera, safety=None)
                    if task1_unsafe else runners["task1"])
    task2_runner = (Task2Runner(cfg, arm, hand, camera, safety=None, task_cfg=cfg.task2)
                    if task2_unsafe else runners["task2"])

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if unsafe_mode:
            log.warning("⚠️ Task1/Task2 不安全自由路径服务已启动：软件安全监控不会启动；"
                        "仅可调用 Task1/Task2 接口")
        else:
            safety.start()
            log.info("安全监控线程已启动")
        yield
        if not unsafe_mode:
            safety.stop()
        camera.close()

    app = FastAPI(title="supcon-competition", lifespan=lifespan)

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

    def execute_task(task_name: str) -> dict:
        """所有 HTTP 入口共用的串行执行器。"""
        with lock:
            if task_name == "task1":
                ok, msg = task1_runner.run()
            elif task_name == "task2":
                ok, msg = task2_runner.run()
            else:
                return {"success": False, "message": f"不支持的任务 {task_name}"}
        return {"success": ok, "message": msg}

    @app.post("/api/task1/execute")
    def task1():
        """兼容原赛题 Task1 固定路径。"""
        return execute_task("task1")

    @app.post("/api/task2/execute")
    def task2():
        """兼容原赛题 Task2 固定路径。"""
        return execute_task("task2")

    @app.post("/api/execute")
    async def execute(request: Request):
        """统一入口：JSON 的 task/task_id/taskName 等字段或 X-Task-Id 请求头选任务。"""
        try:
            payload = await request.json()
        except ValueError:
            payload = {}
        task_name = _requested_task(payload, request.headers)
        if task_name is None:
            return {"success": False,
                    "message": "缺少或不支持任务字段；请传 task: 1/2（也支持 task_id/taskName 或 X-Task-Id）"}
        return await run_in_threadpool(execute_task, task_name)

    @app.post("/api/task3/execute")
    def task3():
        if unsafe_mode:
            return {"success": False, "message": "当前为 Task1/Task2 不安全服务，Task3 已禁用"}
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
