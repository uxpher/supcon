"""O10 灵巧手 HTTP 客户端（REST）。

依据《O10 灵巧手远程控制 API 参考手册》：
- 10 自由度，归一化位置 0-1 控制（set_pos 推荐主用）；
- ⚠️ O10 无触觉传感器：抓取验证只能靠 电流 + 堵转(error bit0) + 位置；
- ⚠️ 归一化 0/1 张开/闭合语义官方文档存在矛盾（§3.1 注释 vs §4.6 示例），
  预设手型必须先跑 scripts/01_hand_semantics.py 实测；
- 过流(error bit2)必须立即开手停止，防止伤手。
"""
from __future__ import annotations

import logging
import threading
import time

import requests

log = logging.getLogger("hand")

# 10 关节弧度范围（右手，官方文档 §3.1）
RAD_RANGES = [
    (-0.03, 1.12), (-1.64, 0.05), (0.0, 0.84), (-0.16, 0.0), (0.0, 1.48),
    (0.0, 1.48), (0.0, 0.17), (0.0, 1.48), (0.0, 0.19), (0.0, 1.48),
]

JOINT_NAMES = [
    "thumb_roll", "thumb_abad", "thumb_mcp", "index_abad", "index_pip",
    "middle_pip", "ring_abad", "ring_pip", "pinky_abad", "pinky_pip",
]


def norm_to_rad(norms: list) -> list:
    return [lo + float(n) * (hi - lo) for n, (lo, hi) in zip(norms, RAD_RANGES)]


def rad_to_norm(rads: list) -> list:
    out = []
    for r, (lo, hi) in zip(rads, RAD_RANGES):
        span = hi - lo
        out.append(max(0.0, min(1.0, (r - lo) / span)) if span > 0 else 0.0)
    return out


class HandError(RuntimeError):
    """灵巧手业务错误。"""


class O10Client:
    def __init__(self, cfg):
        """cfg: supcon.config.HandConfig"""
        self.cfg = cfg
        self.base = cfg.base_url.rstrip("/")

    def _get(self, path: str, timeout: float = 5) -> dict:
        r = requests.get(f"{self.base}{path}", timeout=timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: dict, timeout: float = 15) -> dict:
        r = requests.post(f"{self.base}{path}", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    # ---------- 查询 ----------
    def status(self) -> dict:
        return self._get("/api/status")

    def errors(self) -> dict:
        return self._get("/api/errors")

    def overcurrent(self) -> bool:
        """是否存在过流（bit2，值 4）。"""
        try:
            errs = self.errors().get("error_codes") or []
        except Exception:
            return False
        return any(c & 4 for c in errs)

    # ---------- 控制 ----------
    def set_pos(self, pos10: list) -> dict:
        """归一化位置控制（0-1 × 10），阻塞到完成。"""
        if len(pos10) != 10 or any(not (0.0 <= float(p) <= 1.0) for p in pos10):
            raise HandError(f"位置向量非法: {pos10}")
        d = self._post("/api/set_pos", {"position": [float(p) for p in pos10]})
        if not d.get("success"):
            raise HandError(f"set_pos 失败: {d.get('message')}")
        return d

    def set_pvc(self, rad10: list, torque: list | int | None = None) -> dict:
        """弧度控制 + 可选电流限流（mA，0-1000）。torque 非零 = 位置+电流混合控制。"""
        payload = {"position_rad": [float(r) for r in rad10]}
        if torque is not None:
            if isinstance(torque, int):
                torque = [torque] * 10
            payload["torque"] = [int(t) for t in torque]
        d = self._post("/api/set_pvc", payload)
        if not d.get("success"):
            raise HandError(f"set_pvc 失败: {d.get('message')}")
        return d

    # ---------- 预设手型 ----------
    def open_hand(self) -> None:
        """张手（预设值以 01 脚本实测为准）。"""
        self.set_pos(self.cfg.open_pose)
        log.info("灵巧手 → 张手")

    def point_pose(self) -> None:
        """食指伸直的点按姿态（任务1 用）。"""
        self.set_pos(self.cfg.point_pose)
        log.info("灵巧手 → 点按姿态")

    def neutral_hand(self) -> None:
        """收拢至已示教的中性转运手型（避免 Task1 长距离移动时伸指）。"""
        self.set_pos(self.cfg.neutral_pose)
        log.info("灵巧手 → 中性转运姿态")

    # ---------- 抓取验证（Task2/3 用，无触觉版） ----------
    def close_with_verify(self, close_norm: list | None = None,
                          torque: int | None = None) -> str:
        """限流闭合 + 堵转/电流/位置判据。返回 "GRASPED" / "EMPTY"。

        原理（技术方案 §6）：手指碰到物体 → 到不了目标闭合位置 → 电机堵转
        （error bit0 置位）+ 电流上升 + 位置停在中间。过流则立即开手并抛错。
        """
        target = list(close_norm) if close_norm else list(self.cfg.close_pose)
        rad = norm_to_rad(target)
        torque = torque if torque is not None else self.cfg.torque_ma
        command_done = threading.Event()
        command_error: list[Exception] = []

        def _send() -> None:
            try:
                self.set_pvc(rad, torque=torque)
            except Exception as e:
                command_error.append(e)
            finally:
                command_done.set()

        # 后台发闭合指令，主线程轮询状态做闭环判断
        threading.Thread(target=_send, daemon=True).start()
        v = self.cfg.verify
        t0 = time.time()
        streak = 0
        prev = None
        latest = None
        while time.time() - t0 < v.timeout_s:
            if command_done.is_set() and command_error:
                raise HandError(f"闭合指令失败: {command_error[0]}") from command_error[0]
            try:
                latest = self.status()
            except Exception:
                time.sleep(v.poll_interval)
                continue
            pos = latest.get("position") or []
            errs = latest.get("error_codes") or []
            if any(c & 4 for c in errs):          # 过流 → 立即开手
                self.open_hand()
                raise HandError("过流！已紧急开手")
            stalled = sum(1 for c in errs if c & 1)
            moved = 1.0
            if prev and prev.get("position") and pos:
                moved = max(abs(a - b) for a, b in zip(pos, prev["position"]))
            if stalled > 0 and moved < v.moved_tol:
                streak += 1
            else:
                streak = 0
            if streak >= v.settle_frames:
                break
            prev = latest
            time.sleep(v.poll_interval)

        if command_done.is_set() and command_error:
            raise HandError(f"闭合指令失败: {command_error[0]}") from command_error[0]
        s = latest or self.status()
        pos = s.get("position") or []
        errs = s.get("error_codes") or []
        near_full = all(abs(p - t) < v.near_full_tol for p, t in zip(pos, target))
        stalled = sum(1 for c in errs if c & 1)
        if near_full and stalled == 0:
            log.info("抓取判定: EMPTY（夹空）")
            return "EMPTY"
        log.info("抓取判定: GRASPED（有堵转/未完全闭合）")
        return "GRASPED"
