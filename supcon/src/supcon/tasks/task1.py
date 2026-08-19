"""任务 1：亮灯识别后执行按钮按压或拨杆拨动。

安全约束：

* 正式任务在任何运动前校验全部面板位姿；
* 运行开始时若不在 ``task1_safe_pose``，仅在能读取完整末端位姿时才以分段
  笛卡尔直线自动回安全位；
* 安全位、观察位、开关接近位之间使用分段笛卡尔直线，不接受 OMPL 回退；
* 任何失败（尤其 OMPL、末端未到位、接触动作失败）都不自动撤离，避免在
  已经不确定的姿态上再次下发未知路径。
"""
from __future__ import annotations

import copy
import json
import logging
import math
import os
import time

from ..robot.arm import ArmError
from ..robot.hand import HandError
from ..vision.dump import DebugDump
from ..vision.lamp import LampDetector

log = logging.getLogger("task1")

_POSE_KEYS = ("x", "y", "z", "roll", "pitch", "yaw")
_XYZ_KEYS = ("x", "y", "z")
_RPY_KEYS = ("roll", "pitch", "yaw")


def load_panel(path: str) -> dict:
    """读取旧版 panel.json；新部署应使用 config.yaml 的 task1.panel。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到面板标定文件 {path}")
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


class Task1Runner:
    """任务 1 的显式状态机。

    ``observe_only=True`` 只验证当前位置→安全位→观察位路径，不需要相机、灯位或
    开关位姿，到达观察位后保持不动，供现场人员检查。
    """

    def __init__(self, cfg, arm, hand, camera, safety=None):
        self.cfg = cfg
        self.arm = arm
        self.hand = hand
        self.camera = camera
        self.safety = safety
        self.detector = LampDetector(cfg.task1)
        self.dump = DebugDump(cfg)
        self.panel: dict | None = None
        self.switch_id: int | None = None
        self.state = "init"
        self.motion_uncertain = False

    # ---------- 基础校验与诊断 ----------
    def _unsafe_free_path(self) -> bool:
        return bool(getattr(self.cfg.task1, "unsafe_free_path", False))

    def _check(self) -> None:
        if bool(getattr(self.cfg.task1, "unsafe_disable_safety_checks", False)):
            return
        if self.safety is not None:
            self.safety.assert_ok()

    @staticmethod
    def _angle_delta(start: float, target: float) -> float:
        """最短有符号角差，范围 [-pi, pi)。"""
        return (target - start + math.pi) % (2.0 * math.pi) - math.pi

    @classmethod
    def _pose_error(cls, actual: dict, expected: dict) -> tuple[float, float]:
        position = math.sqrt(sum((float(actual[key]) - float(expected[key])) ** 2
                                 for key in _XYZ_KEYS))
        orientation = max(abs(cls._angle_delta(float(actual[key]), float(expected[key])))
                          for key in _RPY_KEYS)
        return position, orientation

    @staticmethod
    def _pose(value, label: str) -> dict:
        if not isinstance(value, dict) or any(key not in value for key in _POSE_KEYS):
            raise RuntimeError(f"{label} 必须包含 x/y/z/roll/pitch/yaw")
        try:
            pose = {key: float(value[key]) for key in _POSE_KEYS}
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label} 包含非数值") from exc
        if not all(math.isfinite(item) for item in pose.values()):
            raise RuntimeError(f"{label} 包含非有限数")
        return pose

    def _current_pose(self, label: str) -> dict:
        """读取可用于规划的完整实际末端位姿；未知姿态时禁止自动恢复。"""
        return self._pose(self.arm.pose(), f"{label} 的实际末端位姿")

    def _read_pose(self, expected: dict, label: str) -> dict:
        """等待 /api/pose 反馈到位，兼容 B9 指令返回早于 TF 更新的情况。"""
        pos_tol = float(getattr(self.cfg.task1, "observe_pose_tolerance_m", 0.015))
        rpy_tol = float(getattr(self.cfg.task1, "observe_pose_tolerance_rad", 0.12))
        timeout_s = float(getattr(self.cfg.task1, "pose_settle_timeout_s", 5.0))
        poll_s = float(getattr(self.cfg.task1, "pose_settle_poll_s", 0.10))
        deadline = time.monotonic() + timeout_s
        actual = None
        position = orientation = float("inf")
        while True:
            self._check()
            actual = self._current_pose(f"{label} 后")
            position, orientation = self._pose_error(actual, expected)
            if position <= pos_tol and orientation <= rpy_tol:
                return actual
            if time.monotonic() >= deadline:
                break
            time.sleep(poll_s)
        self.motion_uncertain = True
        raise ArmError(
            f"{label} 等待 {timeout_s:.1f}s 后仍未到位："
            f"位置误差 {position * 1000:.1f} mm，姿态误差 {math.degrees(orientation):.1f}°，"
            f"实际位姿 {actual}")

    def _confirm_observe_ready(self, observe: dict) -> dict:
        """观察位拍照门槛：控制器空闲、连续稳定到位、静置后再次确认。"""
        idle_timeout = float(getattr(self.cfg.task1, "observe_idle_timeout_s", 10.0))
        if not self.arm.wait_idle(timeout_s=idle_timeout):
            self.motion_uncertain = True
            raise ArmError(f"观察位前等待控制器空闲超时（{idle_timeout:.1f}s）")

        samples_required = int(getattr(self.cfg.task1, "observe_stable_samples", 5))
        poll_s = float(getattr(self.cfg.task1, "observe_stable_poll_s", 0.20))
        drift_m = float(getattr(self.cfg.task1, "observe_stable_drift_m", 0.003))
        drift_rad = float(getattr(self.cfg.task1, "observe_stable_drift_rad", 0.03))
        timeout_s = float(getattr(self.cfg.task1, "pose_settle_timeout_s", 5.0))
        pos_tol = float(getattr(self.cfg.task1, "observe_pose_tolerance_m", 0.015))
        rpy_tol = float(getattr(self.cfg.task1, "observe_pose_tolerance_rad", 0.12))
        deadline = time.monotonic() + timeout_s
        stable_count = 0
        previous = None
        last = None

        while time.monotonic() < deadline:
            self._check()
            actual = self._current_pose("观察位拍照前")
            pos_error, rpy_error = self._pose_error(actual, observe)
            drift_ok = True
            if previous is not None:
                drift_pos, drift_rpy = self._pose_error(actual, previous)
                drift_ok = drift_pos <= drift_m and drift_rpy <= drift_rad
            if pos_error <= pos_tol and rpy_error <= rpy_tol and drift_ok:
                stable_count += 1
                if stable_count >= samples_required:
                    last = actual
                    break
            else:
                stable_count = 0
            previous = actual
            time.sleep(poll_s)

        if last is None:
            self.motion_uncertain = True
            raise ArmError(
                f"观察位在 {timeout_s:.1f}s 内未取得 {samples_required} 次连续稳定到位反馈；"
                f"最后实际位姿 {previous}")

        settle_s = float(getattr(self.cfg.task1, "observe_settle_s", 2.0))
        log.info("观察位已连续稳定 %d 次，拍照前静置 %.1fs", samples_required, settle_s)
        time.sleep(settle_s)
        return self._read_pose(observe, "观察位静置后确认")

    def _log_ompl_diagnostics(self, target: dict, label: str, velocity: float,
                              error: Exception) -> None:
        """输出 HTTP 客户端可见的 OMPL 上下文。

        碰撞对象、IK 求解或关节限位的内部原因不在 B9 HTTP 响应中；该信息需在
        同一时刻的 B9 / ROS / MoveIt 服务端日志中查找。
        """
        def query(method):
            try:
                return method()
            except Exception as exc:  # 诊断不能掩盖原始错误
                return {"query_error": str(exc)}

        actual = query(self.arm.pose)
        status = query(self.arm.status)
        controllers = query(self.arm.controllers)
        motors = query(self.arm.motors)
        if isinstance(motors, dict):
            motors = {
                name: {key: item.get(key) for key in
                       ("enabled", "fault", "has_feedback", "feedback_age", "effort")}
                for name, item in motors.items() if isinstance(item, dict)
            }
        pose_error = None
        if isinstance(actual, dict) and all(key in actual for key in _POSE_KEYS):
            try:
                pos, rpy = self._pose_error(actual, target)
                pose_error = {"position_mm": round(pos * 1000, 2),
                              "orientation_deg": round(math.degrees(rpy), 2)}
            except (TypeError, ValueError):
                pass
        log.error(
            "OMPL诊断 state=%s segment=%s raw=%s target=%s actual=%s error=%s "
            "request={mode:%s,target_key:%s,cartesian_linear:true,velocity:%.3f,eef_step:%.3f} "
            "status=%s controllers=%s motors=%s",
            self.state, label, error, target, actual, pose_error,
            self.cfg.arm.arm,
            getattr(self.cfg.arm, "target_pose_key", self.cfg.arm.pose_key),
            velocity, self.cfg.arm.eef_step, status, controllers, motors,
        )
        log.error("OMPL 根因须查 B9/ROS/MoveIt 服务端日志（碰撞、IK、关节限位不会由 HTTP 接口返回）。")

    # ---------- 配置校验 ----------
    def _validate_motion_config(self) -> tuple[dict, dict]:
        safe = self._pose(self.cfg.arm.task1_safe_pose, "arm.task1_safe_pose")
        observe = self._pose(self.cfg.arm.observe_pose, "arm.observe_pose")
        for key, fallback in (("observe_step_m", 0.010),
                              ("observe_step_rad", 0.052),
                              ("observe_velocity", 0.03),
                              ("approach_vel", 0.05),
                              ("fine_vel", 0.03),
                              ("observe_pose_tolerance_m", 0.015),
                              ("observe_pose_tolerance_rad", 0.12),
                              ("pose_settle_timeout_s", 5.0),
                              ("pose_settle_poll_s", 0.10),
                              ("observe_idle_timeout_s", 10.0),
                              ("observe_stable_poll_s", 0.20),
                              ("observe_stable_drift_m", 0.003),
                              ("observe_stable_drift_rad", 0.03),
                              ("observe_settle_s", 2.0)):
            value = float(getattr(self.cfg.task1, key, fallback))
            if not math.isfinite(value) or value <= 0:
                raise RuntimeError(f"task1.{key} 必须为正的有限数")
        max_segments = int(getattr(self.cfg.task1, "observe_max_segments", 80))
        if max_segments < 1:
            raise RuntimeError("task1.observe_max_segments 必须大于 0")
        if int(getattr(self.cfg.task1, "observe_stable_samples", 5)) < 1:
            raise RuntimeError("task1.observe_stable_samples 必须大于 0")
        if int(self.cfg.task1.confirm_frames) < 1:
            raise RuntimeError("task1.confirm_frames 必须大于 0")
        if int(self.cfg.task1.max_retry) < 0:
            raise RuntimeError("task1.max_retry 不能小于 0")
        for key in ("press_dwell_s", "frame_interval_s", "action_change_min"):
            value = float(getattr(self.cfg.task1, key))
            if not math.isfinite(value) or value < 0:
                raise RuntimeError(f"task1.{key} 必须为非负有限数")
        if int(self.cfg.task1.roi_radius) < 1:
            raise RuntimeError("task1.roi_radius 必须大于 0")
        h_min, h_max = int(self.cfg.task1.green_h_min), int(self.cfg.task1.green_h_max)
        if not (0 <= h_min <= h_max <= 179):
            raise RuntimeError("task1.green_h_min/green_h_max 必须满足 0 ≤ min ≤ max ≤ 179")
        for key in ("lamp_color_s_min", "lamp_on_v_min", "white_s_max"):
            value = int(getattr(self.cfg.task1, key))
            if not 0 <= value <= 255:
                raise RuntimeError(f"task1.{key} 必须在 0~255")
        red_low = int(self.cfg.task1.red_h_low_max)
        red_high = int(self.cfg.task1.red_h_high_min)
        if not (0 <= red_low <= 179 and 0 <= red_high <= 179):
            raise RuntimeError("task1.red_h_low_max/red_h_high_min 必须在 0~179")
        ratio = float(self.cfg.task1.lamp_on_ratio_min)
        if not math.isfinite(ratio) or not 0 < ratio <= 1:
            raise RuntimeError("task1.lamp_on_ratio_min 必须在 (0, 1]")
        if self.cfg.task1.action_verify not in {"motion_only", "lamp_change"}:
            raise RuntimeError(f"未知 task1.action_verify={self.cfg.task1.action_verify}")
        return safe, observe

    def _load_and_validate_panel(self) -> dict:
        if isinstance(self.cfg.task1.panel, dict):
            panel = copy.deepcopy(self.cfg.task1.panel)
        elif getattr(self.cfg.task1, "panel_file", ""):
            path = self.cfg.resolve(self.cfg.task1.panel_file)
            log.warning("使用已弃用的 task1.panel_file：%s", path)
            panel = load_panel(path)
        else:
            raise RuntimeError("缺少 config.yaml 的 task1.panel")

        lamps = panel.get("lamps")
        switches = panel.get("switches")
        if not isinstance(lamps, list) or len(lamps) != 3:
            raise RuntimeError("task1.panel.lamps 必须恰好包含 3 盏灯")
        if not isinstance(switches, list) or len(switches) != 3:
            raise RuntimeError("task1.panel.switches 必须恰好包含 3 个开关")

        switch_by_id = {}
        for switch in switches:
            if not isinstance(switch, dict) or switch.get("id") in switch_by_id:
                raise RuntimeError("task1.panel.switches 的 id 必须唯一")
            kind = switch.get("type")
            if kind == "button":
                required = ("approach_pose", "press_pose")
            elif kind == "toggle":
                required = ("approach_pose", "flick_start_pose", "flick_end_pose")
            else:
                raise RuntimeError(f"开关 {switch.get('id')} 的 type 必须为 button 或 toggle")
            for key in required:
                self._pose(switch.get(key), f"task1.panel.switches[{switch.get('id')}].{key}")
            switch_by_id[switch["id"]] = switch

        lamp_ids = set()
        for lamp in lamps:
            if not isinstance(lamp, dict) or lamp.get("id") in lamp_ids:
                raise RuntimeError("task1.panel.lamps 的 id 必须唯一")
            lamp_ids.add(lamp["id"])
            if lamp.get("switch_id") not in switch_by_id:
                raise RuntimeError(f"灯 {lamp.get('id')} 指向不存在的 switch_id")
            if str(lamp.get("color", "")).lower() not in {"green", "white", "red"}:
                raise RuntimeError(f"灯 {lamp.get('id')} 的 color 必须为 green/white/red")
            try:
                for key in ("cx", "cy"):
                    value = float(lamp[key])
                    if not math.isfinite(value):
                        raise ValueError(key)
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(f"灯 {lamp.get('id')} 的 cx/cy 必须为有限数") from exc
        baseline = panel.get("baseline_scores")
        if baseline is not None:
            if not isinstance(baseline, list) or len(baseline) != len(lamps):
                raise RuntimeError("task1.panel.baseline_scores 必须为与 lamps 等长的数值列表或 null")
            try:
                if not all(math.isfinite(float(score)) for score in baseline):
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise RuntimeError("task1.panel.baseline_scores 包含非有限数") from exc
        return panel

    # ---------- 安全运动 ----------
    def _ensure_ready_at_safe(self, safe: dict) -> dict:
        """使能并确认安全位；不在安全位时受控地分段回安全位。"""
        ok, reason = self.arm.healthy()
        if not ok:
            raise ArmError(f"机械臂不健康：{reason}")
        errors = self.hand.errors().get("error_codes") or []
        if any(int(code) != 0 for code in errors):
            raise HandError(f"灵巧手存在错误码：{errors}")
        self.arm.enable()
        if not self.arm.enabled_all():
            raise ArmError("机械臂未完全使能")
        self._set_hand(getattr(self.cfg.hand, "neutral_pose", self.cfg.hand.open_pose),
                       "中性转运姿态")
        actual = self._current_pose("起始位置确认")
        pos_tol = float(self.cfg.task1.observe_pose_tolerance_m)
        rpy_tol = float(self.cfg.task1.observe_pose_tolerance_rad)
        position, orientation = self._pose_error(actual, safe)
        if position <= pos_tol and orientation <= rpy_tol:
            log.info("设备就绪，已确认机械臂位于 Task1 安全位")
            return actual

        # 不从“未知”位置盲退：已读取完整 pose 才进入此分支；每个短段仍会
        # plan_only、执行、到位校验。任一段失败时异常上抛并停止，不继续恢复。
        log.warning("起始位置不在安全位（位置误差 %.1f mm，姿态误差 %.1f°），"
                    "开始分段回安全位", position * 1000, math.degrees(orientation))
        self.state = "recovering_safe"
        actual = self._move_linear(
            actual, safe, "当前位置→起始安全位", float(self.cfg.task1.observe_velocity))
        log.info("已自动回到 Task1 安全位")
        return actual

    def _move_segment(self, target: dict, velocity: float, label: str) -> dict:
        """执行一个短笛卡尔段；OMPL 或未到位后不再允许自动恢复。"""
        if self._unsafe_free_path():
            # 即使允许 OMPL 自由路径，也不能把“HTTP 指令返回”当成“已到位”：
            # 相机拍摄与下一步动作必须以真实六维末端反馈为准。
            log.warning("⚠️ 自由路径调试：%s，跳过 plan_only，保留实际到位等待", label)
            self.arm.goto_pose(target, vel=velocity, plan_only=False)
            return self._read_pose(target, label)
        self._check()
        log.info("Task1 %s → (%.3f, %.3f, %.3f), vel=%.3f",
                 label, target["x"], target["y"], target["z"], velocity)
        try:
            self.arm.goto_pose(target, vel=velocity, plan_only=True)
            self.arm.goto_pose(target, vel=velocity, plan_only=False)
        except ArmError as exc:
            if "OMPL" in str(exc):
                self.motion_uncertain = True
                self._log_ompl_diagnostics(target, label, velocity, exc)
            raise
        self._check()
        return self._read_pose(target, label)

    def _move_linear(self, start: dict, end: dict, label: str, velocity: float) -> dict:
        """将全局直线路径拆成独立短笛卡尔段，保留线性插值语义。"""
        start, end = self._pose(start, f"{label}.start"), self._pose(end, f"{label}.end")
        if self._unsafe_free_path():
            log.warning("⚠️ 自由路径调试：%s 直接请求终点，不做线性分段", label)
            return self._move_segment(end, velocity, label)
        step_m = float(getattr(self.cfg.task1, "observe_step_m", 0.010))
        step_rad = float(getattr(self.cfg.task1, "observe_step_rad", 0.052))
        max_segments = int(getattr(self.cfg.task1, "observe_max_segments", 80))
        distance = math.sqrt(sum((end[key] - start[key]) ** 2 for key in _XYZ_KEYS))
        angle_delta = {key: self._angle_delta(start[key], end[key]) for key in _RPY_KEYS}
        count = max(1, math.ceil(distance / step_m),
                    math.ceil(max(abs(value) for value in angle_delta.values()) / step_rad))
        if count > max_segments:
            raise RuntimeError(f"{label} 需要 {count} 个差值段，超过 observe_max_segments={max_segments}")
        log.info("Task1 %s：%d 段，距离 %.1f mm，最大姿态变化 %.1f°",
                 label, count, distance * 1000,
                 math.degrees(max(abs(value) for value in angle_delta.values())))
        actual = start
        for index in range(1, count + 1):
            ratio = index / count
            target = {
                "x": start["x"] + (end["x"] - start["x"]) * ratio,
                "y": start["y"] + (end["y"] - start["y"]) * ratio,
                "z": start["z"] + (end["z"] - start["z"]) * ratio,
                "roll": start["roll"] + angle_delta["roll"] * ratio,
                "pitch": start["pitch"] + angle_delta["pitch"] * ratio,
                "yaw": start["yaw"] + angle_delta["yaw"] * ratio,
            }
            if index == count:
                target = dict(end)  # 保留标定文件的最终角度表示
            actual = self._move_segment(target, velocity, f"{label} {index}/{count}")
        return actual

    def _set_hand(self, pose: list, label: str) -> None:
        if not isinstance(pose, list) or len(pose) != 10:
            raise HandError(f"{label} 必须是 10 维手型")
        self.hand.set_pos(pose)
        log.info("灵巧手 → %s", label)

    # ---------- 感知与动作 ----------
    def _detect_lit_switch(self) -> tuple[int, list[float]]:
        if self.camera is None or self.panel is None:
            raise RuntimeError("正式 Task1 缺少相机或面板配置")
        streak_id = None
        streak = 0
        for attempt in range(int(self.cfg.task1.max_retry) + 1):
            for _ in range(int(self.cfg.task1.confirm_frames)):
                self._check()
                rgb = self.camera.grab_rgb()
                self.dump.rgb(rgb, "color", "observe")
                index = self.detector.detect_lit_index(
                    rgb, self.panel["lamps"])
                if index is not None and index == streak_id:
                    streak += 1
                else:
                    streak_id, streak = index, 1 if index is not None else 0
                if streak >= int(self.cfg.task1.confirm_frames):
                    scores = self.detector.green_scores(rgb, self.panel["lamps"])
                    return index, scores
                time.sleep(float(self.cfg.task1.frame_interval_s))
            log.warning("亮灯识别第 %d 次未取得连续一致结果", attempt + 1)
        raise RuntimeError("亮灯识别不稳定；请检查 ROI、基线、曝光与面板观察位")

    def _operate_contact(self, switch: dict) -> dict:
        """从开关接近位执行短接触段，完成后回到同一接近位。"""
        approach = self._pose(switch["approach_pose"], f"开关 {switch['id']} 接近位")
        velocity = float(self.cfg.task1.fine_vel)
        if switch["type"] == "button":
            press = self._pose(switch["press_pose"], f"开关 {switch['id']} 按下位")
            at_press = self._move_linear(
                approach, press, f"开关 {switch['id']} 下压", velocity)
            time.sleep(float(self.cfg.task1.press_dwell_s))
            return self._move_linear(
                at_press, approach, f"开关 {switch['id']} 抬起", velocity)
        else:
            start = self._pose(switch["flick_start_pose"], f"开关 {switch['id']} 拨动起点")
            end = self._pose(switch["flick_end_pose"], f"开关 {switch['id']} 拨动终点")
            at_start = self._move_linear(
                approach, start, f"开关 {switch['id']}→拨动起点", velocity)
            # 拨杆终点的姿态变化可能很大；仍按示教的起止位姿连成直线，但
            # 分段发送，避免控制器将一个大段回退为不可控的 OMPL 轨迹。
            at_end = self._move_linear(
                at_start, end, f"开关 {switch['id']} 拨动", velocity)
            return self._move_linear(
                at_end, approach, f"开关 {switch['id']} 退回接近位", velocity)

    def _verify_action(self, lamp_index: int, before_scores: list[float]) -> None:
        mode = self.cfg.task1.action_verify
        if mode == "motion_only":
            log.info("Task1 动作验证：motion_only")
            return
        if mode != "lamp_change":
            raise RuntimeError(f"未知 task1.action_verify={mode}")
        if self.camera is None or self.panel is None:
            raise RuntimeError("lamp_change 验证缺少相机或面板配置")
        time.sleep(float(self.cfg.task1.frame_interval_s))
        after = self.detector.green_scores(self.camera.grab_rgb(), self.panel["lamps"])
        if abs(after[lamp_index] - before_scores[lamp_index]) < float(self.cfg.task1.action_change_min):
            raise RuntimeError("操作后目标灯状态未产生足够可见变化")

    # ---------- 状态机入口 ----------
    def run(self, observe_only: bool = False) -> tuple[bool, str]:
        """执行一次任务；失败后保持当前位置，交由现场人员确认恢复。"""
        started = time.monotonic()
        self.state = "preflight"
        self.motion_uncertain = False
        self.switch_id = None
        log.info("===== Task1 开始（模式：%s）=====" , "observe-only" if observe_only else "full")
        try:
            safe, observe = self._validate_motion_config()
            if not observe_only:
                self.panel = self._load_and_validate_panel()
            else:
                self.panel = None

            at_safe = self._ensure_ready_at_safe(safe)
            self.state = "safe"
            at_observe = self._move_linear(
                at_safe, observe, "安全位→观察位", float(self.cfg.task1.observe_velocity))
            self.state = "observe"
            at_observe = self._confirm_observe_ready(observe)

            if observe_only:
                log.warning("观察路径测试完成：机械臂保持在观察位，须由现场人员手动恢复")
                return True, "task1 observe route ok (arm remains at observe pose)"

            lamp_index, before_scores = self._detect_lit_switch()
            lamp = self.panel["lamps"][lamp_index]
            self.switch_id = lamp["switch_id"]
            switch = next(item for item in self.panel["switches"] if item["id"] == self.switch_id)
            approach = self._pose(switch["approach_pose"], f"开关 {self.switch_id} 接近位")

            self.state = "switch_approach"
            # 长距离转运全程保持中性手型；仅在末端已经到达开关接近位后才
            # 伸出点按手指，避免手指在途中扫到面板、支架或工装。
            at_approach = self._move_linear(
                at_observe, approach, f"观察位→开关 {self.switch_id} 接近位",
                float(self.cfg.task1.approach_vel))
            self._set_hand(self.cfg.hand.point_pose, "点按/拨杆姿态")
            at_approach = self._operate_contact(switch)

            # 接触动作已由 _operate_contact 的末段机械臂退回接近位完成；
            # 现在才收回手指，然后再做接近位→观察位的机械臂转运。
            self._set_hand(getattr(self.cfg.hand, "neutral_pose", self.cfg.hand.open_pose), "中性转运姿态")
            at_observe = self._move_linear(
                at_approach, observe, f"开关 {self.switch_id}→观察位",
                float(self.cfg.task1.approach_vel))
            self.state = "observe"
            at_observe = self._confirm_observe_ready(observe)
            self._verify_action(lamp_index, before_scores)
            self.state = "returning_safe"
            self._move_linear(at_observe, safe, "观察位→安全位", float(self.cfg.task1.observe_velocity))
            self.state = "safe"

            elapsed = time.monotonic() - started
            log.info("===== Task1 完成：switch=%s，耗时 %.1f s =====", self.switch_id, elapsed)
            return True, f"task1 ok (switch {self.switch_id}, {elapsed:.1f}s)"
        except Exception as exc:
            log.exception("Task1 失败：state=%s", self.state)
            if self.motion_uncertain:
                suffix = "运动状态不确定，禁止自动撤离；请现场确认姿态后手动恢复。"
            else:
                suffix = "为避免在故障状态下追加路径，程序未自动撤离；请现场确认姿态。"
            log.error("%s", suffix)
            return False, f"{exc}（{suffix}）"[:300]
