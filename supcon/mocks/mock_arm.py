#!/usr/bin/env python3
"""模拟 FTArm B9 机械臂 HTTP 服务（默认端口 8087）。

没有真机时用它联调：
    python mocks/mock_arm.py --port 8087 [--seconds-per-meter 1.0]

接口与真机《FTArm B9 机械臂HTTP-WS 接口文档》保持一致（REST 部分）。
"""
import argparse
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_POSE = {"x": 0.275, "y": -0.16, "z": 0.48,
                "roll": -3.141, "pitch": -1.552, "yaw": 3.141}
JOINT_NAMES = ["shoulder_pitch", "shoulder_roll", "shoulder_yaw",
               "elbow_roll", "elbow_yaw", "wrist_pitch", "wrist_yaw"]


class MockArmState:
    def __init__(self, seconds_per_meter: float = 1.0):
        self.pose = dict(DEFAULT_POSE)
        self.enabled = False
        self.seconds_per_meter = seconds_per_meter
        self._lock = threading.Lock()

    def distance(self, target: dict) -> float:
        return math.sqrt(sum((target.get(k, 0.0) - self.pose.get(k, 0.0)) ** 2
                             for k in "xyz"))

    def move_to(self, target: dict, vel: float) -> None:
        """模拟运动：按距离 × 速度系数睡眠，然后更新位姿。"""
        with self._lock:
            d = self.distance(target)
            t = d * self.seconds_per_meter / max(vel or 0.12, 0.05)
            time.sleep(t)
            for k in self.pose:
                self.pose[k] = target.get(k, self.pose[k])


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # 静默，避免刷屏

    @property
    def state(self) -> MockArmState:
        return self.server.state

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def do_GET(self):
        s = self.state
        if self.path == "/api/status":
            return self._send(200, {
                "timestamp": time.time(), "moving": False,
                "moveit_available": True,
                "right_joints": {n: 0.0 for n in JOINT_NAMES},
                "right_pose": None})
        if self.path == "/api/pose":
            return self._send(200, {"arm": "right", "pose": dict(s.pose)})
        if self.path == "/api/motors":
            joints = {n: {"position": 0.0, "velocity": 0.0, "effort": 0.0,
                          "motor_error": 0, "fault": 0, "has_feedback": 1,
                          "feedback_age": 0.001,
                          "enabled": 1 if s.enabled else 0}
                      for n in JOINT_NAMES}
            return self._send(200, joints)
        if self.path == "/api/controllers":
            return self._send(200, {"joint_state_available": True, "active": False})
        return self._send(404, {"success": False, "message": f"未知接口: {self.path}"})

    def do_POST(self):
        s = self.state
        body = self._read_json()
        if self.path == "/api/enable":
            s.enabled = True
            return self._send(200, {"right": {"success": True,
                                              "message": "7 motors enabled"}})
        if self.path == "/api/disable":
            s.enabled = False
            return self._send(200, {"right": {"success": True,
                                              "message": "7 motors disabled"}})
        if self.path == "/api/end_effector":
            target = body.get("right") or body.get("left") or {}
            vel = float(body.get("velocity_scaling", 0.12))
            if body.get("plan_only"):
                return self._send(200, {"success": True,
                                        "message": "Planning succeeded for right_arm"})
            try:
                s.move_to(target, vel)
                return self._send(200, {"success": True,
                                        "message": "Cartesian execution finished for right_arm"})
            except Exception as e:
                return self._send(400, {"success": False, "message": str(e)})
        if self.path == "/api/joints":
            return self._send(200, {"success": True, "message": "Joint motion executed"})
        if self.path == "/api/cancel":
            return self._send(200, {"success": True, "message": "Cancel requested"})
        if self.path == "/api/control_mode":
            return self._send(200, {"right": {"success": True,
                                              "message": "mode set to pos_vel"}})
        if self.path == "/api/teach":
            return self._send(200, {"success": True, "message": "Trajectory saved",
                                    "trajectory_id": "mock"})
        if self.path == "/api/teach_mode":
            return self._send(200, {"success": True})
        if self.path == "/api/playback":
            return self._send(200, {"success": True, "message": "Playback complete"})
        return self._send(404, {"success": False, "message": f"未知接口: {self.path}"})


class MockArmServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, seconds_per_meter: float = 1.0):
        super().__init__(addr, Handler)
        self.state = MockArmState(seconds_per_meter)


def main():
    ap = argparse.ArgumentParser(description="模拟 FTArm B9 机械臂服务")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8087)
    ap.add_argument("--seconds-per-meter", type=float, default=1.0,
                    help="每米运动模拟耗时（秒），调小=动得快")
    a = ap.parse_args()
    srv = MockArmServer((a.host, a.port), a.seconds_per_meter)
    print(f"mock 机械臂已启动 http://{a.host}:{a.port}（Ctrl+C 停止）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
