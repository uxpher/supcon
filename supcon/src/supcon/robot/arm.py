"""FTArm B9 机械臂 HTTP 客户端（REST）。

依据《FTArm B9 机械臂HTTP-WS 接口文档》：
- 运动接口同步阻塞（服务器侧 60s 上限），本客户端默认 timeout=90s；
- message 含 "OMPL" = 直线已回退自由路径（轨迹不可控），本客户端按错误处理；
- 新请求抢占旧请求 → 上层必须串行调用，勿并发发运动指令。
"""
from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger("arm")


class ArmError(RuntimeError):
    """机械臂业务错误。"""


class B9Client:
    def __init__(self, cfg):
        """cfg: supcon.config.ArmConfig"""
        self.cfg = cfg
        self.base = cfg.base_url.rstrip("/")

    # ---------- 基础请求 ----------
    def _get(self, path: str, timeout: float = 5) -> dict:
        r = requests.get(f"{self.base}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict, timeout: float = 10) -> dict:
        r = requests.post(f"{self.base}{path}", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    # ---------- 查询 ----------
    def status(self) -> dict:
        return self._get("/api/status")

    def pose(self) -> dict | None:
        """末端位姿 {x,y,z,roll,pitch,yaw}；TF 未就绪时为 None。"""
        d = self._get("/api/pose")
        p = d.get("pose")
        if not p:
            log.warning("末端位姿暂不可用（系统刚启动 TF 未就绪）: %s", d)
        return p

    def motors(self) -> dict:
        return self._get("/api/motors")

    def controllers(self) -> dict:
        return self._get("/api/controllers")

    def healthy(self, max_feedback_age_s: float = 2.0) -> tuple[bool, str]:
        """电机健康检查（运动前必须通过）。返回 (是否健康, 原因)。

        ``feedback_age`` 是 HTTP 服务采样数据的年龄，不是底层驱动的硬实时
        心跳；在运动或服务负载较高时 0.1--0.5 s 属于正常抖动。因此默认只把
        持续超过 2 s 的陈旧反馈视为不健康。安全线程还会做连续确认。
        """
        try:
            m = self.motors()
        except Exception as e:
            return False, f"motors 接口不可达: {e}"
        if not m:
            return False, "motors 无数据（服务未就绪）"
        for name, j in m.items():
            if j.get("fault") != 0:
                return False, f"{name} fault={j.get('fault')}"
            if j.get("has_feedback") != 1:
                return False, f"{name} 无反馈"
            if float(j.get("feedback_age", float("inf"))) >= max_feedback_age_s:
                return False, f"{name} 反馈超龄 {j.get('feedback_age')}"
        return True, "ok"

    def enabled_all(self) -> bool:
        try:
            m = self.motors()
        except Exception:
            return False
        return bool(m) and all(j.get("enabled") == 1 for j in m.values())

    # ---------- 控制 ----------
    def _side_key(self) -> str:
        """使能/失能响应里的嵌套键：right_arm → right。"""
        return self.cfg.pose_key

    def enable(self) -> None:
        d = self._post("/api/enable", {})
        inner = d.get(self._side_key(), d)
        if not inner.get("success"):
            raise ArmError(f"使能失败: {inner}")
        log.info("电机已使能: %s", inner.get("message"))

    def disable(self) -> None:
        """软急停。⚠️ 失能瞬间手臂会因重力下坠，务必先回低位并有人托扶。"""
        d = self._post("/api/disable", {})
        inner = d.get(self._side_key(), d)
        if not inner.get("success"):
            raise ArmError(f"失能失败: {inner}")
        log.warning("电机已失能（手臂可能下坠！）")

    def line_to(self, x: float | None = None, y: float | None = None,
                z: float | None = None, roll: float | None = None,
                pitch: float | None = None, yaw: float | None = None,
                pose: dict | None = None, vel: float | None = None,
                plan_only: bool = False, timeout: float | None = None) -> dict:
        """末端直线运动到目标位姿（cartesian_linear=true）。

        pose 参数（dict）优先；否则用 x/y/z + 缺省姿态。
        plan_only=True 只规划不执行（安全预览）。
        """
        if pose:
            target = dict(pose)
        else:
            r, p, yw = self.cfg.default_rpy
            target = {
                "x": x, "y": y, "z": z,
                "roll": r if roll is None else roll,
                "pitch": p if pitch is None else pitch,
                "yaw": yw if yaw is None else yaw,
            }
        payload = {
            "mode": self.cfg.arm,
            self.cfg.pose_key: target,
            "cartesian_linear": True,
            "velocity_scaling": vel if vel is not None else self.cfg.velocity_fast,
            "acceleration_scaling": self.cfg.acceleration_scaling,
            "cartesian_eef_step": self.cfg.eef_step,
            "plan_only": plan_only,
        }
        try:
            d = self._post("/api/end_effector", payload,
                           timeout=timeout or self.cfg.timeout)
        except requests.exceptions.Timeout as e:
            raise ArmError("运动超时（服务器 60s 上限，请提速或改用 WebSocket）") from e
        if not d.get("success"):
            raise ArmError(f"运动失败: {d.get('message')}")
        msg = d.get("message", "")
        if not plan_only and "OMPL" in msg:
            raise ArmError(f"直线已回退自由路径(OMPL)，轨迹不可控: {msg}")
        if not plan_only:
            time.sleep(self.cfg.action_gap_s)   # 相邻动作间隔：到位后静置，防残余振动/给拍照留稳定时间
        return d

    def goto_pose(self, pose: dict, vel: float | None = None,
                  plan_only: bool = False, timeout: float | None = None) -> dict:
        return self.line_to(pose=pose, vel=vel, plan_only=plan_only, timeout=timeout)

    def move_joints(self, joints: list, vel: float | None = None,
                    plan_only: bool = False) -> dict:
        """7 关节运动（备用）。joints 顺序见文档 §5.2。"""
        payload = {
            "mode": self.cfg.arm,
            f"{self.cfg.pose_key}_joints": list(joints),
            "velocity_scaling": vel if vel is not None else 0.2,
            "acceleration_scaling": 0.1,
            "plan_only": plan_only,
        }
        d = self._post("/api/joints", payload, timeout=120)
        if not d.get("success"):
            raise ArmError(f"关节运动失败: {d.get('message')}")
        return d

    def cancel(self) -> dict:
        """复位「运动中」软标记。⚠️ 不真正中断已执行轨迹。"""
        return self._post("/api/cancel", {})

    def teach_mode(self, enable: bool) -> dict:
        return self._post("/api/teach_mode", {"enable": enable})

    def wait_idle(self, timeout_s: float = 10.0) -> bool:
        """等待 moving 软标记清零。"""
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                if not self.status().get("moving"):
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False
