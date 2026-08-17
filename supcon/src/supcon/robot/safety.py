"""后台安全监控线程。

持续轮询：
- 灵巧手：过流（error bit2）→ 立即开手 + 置急停标志；
- 机械臂：电机 fault / 无反馈 / 反馈超龄 → 置急停标志（可选失能，默认不动作）；
- 机械臂：力矩绝对值上限检测（可选，effort_guard_enabled）→ 任一关节 |effort| 超阈值 → 置急停标志。

主流程在每个动作之间调用 assert_ok() 检查标志，任何异常立即停止后续动作。
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger("safety")


class SafetyError(RuntimeError):
    """安全急停。"""


class SafetyMonitor(threading.Thread):
    def __init__(self, arm, hand, cfg, daemon: bool = True):
        super().__init__(daemon=daemon, name="safety-monitor")
        self.arm = arm
        self.hand = hand
        self.cfg = cfg
        self._stop = threading.Event()
        self._emergency = threading.Event()
        self._reason = ""
        self._lock = threading.Lock()

    # ---------- 主流程侧接口 ----------
    def stop(self) -> None:
        self._stop.set()

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    def is_emergency(self) -> bool:
        return self._emergency.is_set()

    def assert_ok(self) -> None:
        """主流程每个动作前调用；急停标志置位则抛错。"""
        if self._emergency.is_set():
            raise SafetyError(f"安全急停: {self.reason}")

    def trigger(self, reason: str) -> None:
        with self._lock:
            self._reason = reason
            self._emergency.set()
        log.error("⚠️ 安全急停: %s", reason)

    # ---------- 监控线程 ----------
    def _check_effort_limit(self) -> None:
        """力矩绝对值上限检测：任一关节 |effort| 超过阈值 → 急停。

        ⚠️ 判据是「力矩绝对值超上限」，不是相邻差值突变——差值法在 0.3s 轮询下
        既会误报正常加减速、又会漏报几十 ms 的碰撞尖峰，不可靠。
        现场标定：全速运动 + 正常抓取时，每关节 effort 的最大绝对值，
        把阈值设在「正常峰值之上、碰撞冲力之下」。
        """
        try:
            m = self.arm.motors()
            for name, j in m.items():
                effort = float(j.get("effort", 0.0))
                if abs(effort) > self.cfg.effort_guard_threshold:
                    self.trigger(
                        f"关节 {name} 力矩超限 {effort:.2f} Nm"
                        f"（阈值 {self.cfg.effort_guard_threshold:.1f}）")
                    break
        except Exception:
            pass

    def run(self) -> None:
        while not self._stop.wait(self.cfg.poll_interval_s):
            # 手：过流 → 开手 + 急停
            try:
                errs = self.hand.errors().get("error_codes") or []
                if any(c & 4 for c in errs):
                    self.trigger("灵巧手过流")
                    try:
                        self.hand.open_hand()
                    except Exception:
                        pass
                    continue
            except Exception:
                pass
            # 臂：电机故障
            try:
                ok, why = self.arm.healthy()
                if not ok:
                    self.trigger(f"机械臂电机异常: {why}")
                    if self.cfg.disable_arm_on_emergency:
                        try:
                            self.arm.disable()
                        except Exception:
                            pass
            except Exception:
                pass
            # 臂：力矩绝对值上限（可选）
            if self.cfg.effort_guard_enabled:
                self._check_effort_limit()
