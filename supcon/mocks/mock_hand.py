#!/usr/bin/env python3
"""模拟 O10 灵巧手 HTTP 服务（默认端口 8088）。

没有真手时用它联调：
    python mocks/mock_hand.py --port 8088

附加调试接口（真机没有）：
    POST /_debug/object  {"present": true}   # 放一个"物体"到手里（抓取时会堵转）
    POST /_debug/object  {"present": false}  # 拿走物体
"""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RAD_RANGES = [
    (-0.03, 1.12), (-1.64, 0.05), (0.0, 0.84), (-0.16, 0.0), (0.0, 1.48),
    (0.0, 1.48), (0.0, 0.17), (0.0, 1.48), (0.0, 0.19), (0.0, 1.48),
]
JOINT_NAMES = ["thumb_roll", "thumb_abad", "thumb_mcp", "index_abad",
               "index_pip", "middle_pip", "ring_abad", "ring_pip",
               "pinky_abad", "pinky_pip"]
JOINT_NAMES_CN = ["拇指旋转", "拇指外展", "拇指弯曲", "食指侧摆", "食指弯曲",
                  "中指弯曲", "无名指侧摆", "无名指弯曲", "小指侧摆", "小指弯曲"]
PIP_JOINTS = {4, 5, 7, 9}   # 指关节索引：模拟"碰到物体"时在这些关节堵转
STALL_POS = 0.25


def rad_to_norm(rads):
    out = []
    for r, (lo, hi) in zip(rads, RAD_RANGES):
        span = hi - lo
        out.append(max(0.0, min(1.0, (r - lo) / span)) if span > 0 else 0.0)
    return out


class MockHandState:
    def __init__(self):
        self.position = [0.5] * 10
        self.joint_rad = [lo + 0.5 * (hi - lo) for lo, hi in RAD_RANGES]
        self.motor_position = [2048] * 10
        self.velocity = [0] * 10
        self.current = [120] * 10
        self.error_codes = [0] * 10
        self.object_present = False

    def apply_target(self, target_norm):
        """应用目标归一化位置；有物体且目标为"闭合"时模拟堵转。"""
        pos, errs, cur = [], [], []
        for i, t in enumerate(target_norm):
            t = max(0.0, min(1.0, float(t)))
            if self.object_present and i in PIP_JOINTS and t < 0.15:
                pos.append(STALL_POS)   # 到不了目标位置（碰到物体）
                errs.append(1)          # 堵转 bit0
                cur.append(800)         # 电流上升
            else:
                pos.append(t)
                errs.append(0)
                cur.append(120)
        self.position = pos
        self.error_codes = errs
        self.current = cur
        self.joint_rad = [lo + p * (hi - lo) for p, (lo, hi) in zip(pos, RAD_RANGES)]
        self.motor_position = [int(4096 * p) for p in pos]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    @property
    def state(self) -> MockHandState:
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

    def _status_payload(self) -> dict:
        s = self.state
        return {
            "connected": True, "hand_type": "right", "name": "omnihand_o10",
            "model": "OmniHand 2025", "sn": "MOCK0000000000",
            "hardware_ver": "1.0.0", "software_ver": "1.2.0", "dof": 10,
            "timestamp": time.time(),
            "position": list(s.position), "joint_rad": list(s.joint_rad),
            "motor_position": list(s.motor_position), "velocity": list(s.velocity),
            "current": list(s.current), "error_codes": list(s.error_codes),
            "joint_names": JOINT_NAMES, "joint_names_cn": JOINT_NAMES_CN,
        }

    def do_GET(self):
        s = self.state
        if self.path == "/api/status":
            return self._send(200, {"success": True, **self._status_payload()})
        if self.path == "/api/pose":
            return self._send(200, {"success": True, "position": list(s.position)})
        if self.path == "/api/pvc":
            return self._send(200, {"success": True,
                                    "position_rad": list(s.joint_rad),
                                    "velocity": list(s.velocity),
                                    "current": list(s.current)})
        if self.path == "/api/config":
            return self._send(200, {"success": True, "name": "omnihand_o10",
                                    "model": "OmniHand 2025",
                                    "sn": "MOCK0000000000", "hardware_ver": "1.0.0",
                                    "software_ver": "1.2.0", "voltage_mv": 24000,
                                    "dof": 10, "hand_type": "right",
                                    "hand_device_id": "mock"})
        if self.path == "/api/errors":
            details = ["正常" if c == 0 else f"错误码 {c}（堵转/过热等，见文档）"
                       for c in s.error_codes]
            return self._send(200, {"success": True,
                                    "error_codes": list(s.error_codes),
                                    "error_details": details})
        return self._send(404, {"success": False, "message": f"未知接口: {self.path}"})

    def do_POST(self):
        s = self.state
        body = self._read_json()
        if self.path == "/api/set_pos":
            pos = body.get("position") or []
            if len(pos) != 10:
                return self._send(400, {"success": False,
                                        "message": f"需要 10 个值 (0-1), 实际收到 {len(pos)}"})
            s.apply_target(pos)
            return self._send(200, {"success": True, "message": "位置设置成功",
                                    "target": [float(p) for p in pos],
                                    "joint_rad": list(s.joint_rad)})
        if self.path == "/api/set_pvc":
            rads = body.get("position_rad") or []
            if len(rads) != 10:
                return self._send(400, {"success": False,
                                        "message": f"需要 10 个弧度值, 实际收到 {len(rads)}"})
            norm = rad_to_norm(rads)
            s.apply_target(norm)
            return self._send(200, {"success": True, "message": "PVC 设置成功"})
        if self.path == "/api/set_motor":
            motor = body.get("motor") or []
            if len(motor) != 10:
                return self._send(400, {"success": False,
                                        "message": f"需要 10 个电机位置, 实际收到 {len(motor)}"})
            norm = [max(0.0, min(1.0, m / 4096.0)) for m in motor]
            s.apply_target(norm)
            return self._send(200, {"success": True, "message": "电机位置设置成功",
                                    "target": motor, "actual": motor})
        if self.path == "/_debug/object":
            s.object_present = bool(body.get("present", False))
            return self._send(200, {"success": True,
                                    "message": f"object_present={s.object_present}"})
        return self._send(404, {"success": False, "message": f"未知接口: {self.path}"})


class MockHandServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr):
        super().__init__(addr, Handler)
        self.state = MockHandState()


def main():
    ap = argparse.ArgumentParser(description="模拟 O10 灵巧手服务")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8088)
    a = ap.parse_args()
    srv = MockHandServer((a.host, a.port))
    print(f"mock 灵巧手已启动 http://{a.host}:{a.port}（Ctrl+C 停止）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
