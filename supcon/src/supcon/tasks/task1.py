"""任务1：拨按开关（视觉定位）。

竞赛软件每次点击按钮 → POST /api/task1/execute → 本执行器跑一遍完整流程：
  1) 准备：臂电机健康 → 使能 → 手摆出食指按压姿态
  2) 去观察位拍照，检测哪盏灯亮（ROI 亮度比较）
  3) 查 config.yaml 的 task1.panel 得到该灯下方开关的示教位姿
  4) 按钮 = 垂直下压；拨动开关 = 沿示教方向拨动
  5) 退回安全位，返回 (success, message)

设计要点：
- 视觉只回答「哪盏灯亮」，开关动作位姿全部真机示教（scripts/02_record_pose.py），
  因此任务1不依赖手眼标定，新手也能稳定完成；
- 每个位姿先 plan_only 预览、执行后检查 OMPL（回退非直线 = 危险）；
- 每步之间检查后台安全监控标志；
- 任务接口被连续调用 3 次，每次独立执行、无状态记忆。
"""
from __future__ import annotations

import json
import logging
import os
import copy
import time

from ..robot.arm import ArmError
from ..robot.hand import HandError
from ..vision.dump import DebugDump
from ..vision.lamp import LampDetector

log = logging.getLogger("task1")


def load_panel(path: str) -> dict:
    """读取面板标定文件。"""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"找不到面板标定文件 {path}，请先运行 scripts/03_calibrate_panel.py")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Task1Runner:
    def __init__(self, cfg, arm, hand, camera, safety=None):
        """cfg: AppConfig；arm/hand/camera: 客户端实例；safety: SafetyMonitor 或 None。"""
        self.cfg = cfg
        self.arm = arm
        self.hand = hand
        self.camera = camera
        self.safety = safety
        self.detector = LampDetector(cfg.task1)
        self.dump = DebugDump(cfg)
        self.panel = None
        self.switch_id = None

    # ---------- 基础动作 ----------
    def _check(self) -> None:
        if self.safety is not None:
            self.safety.assert_ok()

    def _move(self, pose: dict, vel: float, what: str = "", preview: bool = False):
        """直线运动一步：先安全检查，可选先预览，执行后检查 OMPL。"""
        self._check()
        log.info("运动 → %s (%.3f, %.3f, %.3f) vel=%.2f",
                 what, pose["x"], pose["y"], pose["z"], vel)
        if preview:
            self.arm.goto_pose(pose, vel=vel, plan_only=True)
            log.info("预览通过: %s", what)
        self.arm.goto_pose(pose, vel=vel, plan_only=False)
        self._check()

    # ---------- 流程步骤 ----------
    def _ensure_ready(self) -> None:
        """设备准备：臂健康 → 使能 → 手摆点按姿态。"""
        ok, why = self.arm.healthy()
        if not ok:
            raise ArmError(f"机械臂电机异常: {why}")
        self.arm.enable()
        if not self.arm.enabled_all():
            raise ArmError("电机未全部使能")
        errs = self.hand.errors().get("error_codes") or []
        # 堵转亦可能是上一轮遗留异常；仅允许全 0 状态进入正式任务。
        if any(c != 0 for c in errs):
            raise HandError(f"灵巧手存在严重错误码: {errs}")
        log.info("设备就绪（臂已使能）")

    def _load_and_validate_panel(self) -> dict:
        """读取并验证 config.yaml 中的 task1.panel（兼容旧 panel_file）。"""
        if isinstance(self.cfg.task1.panel, dict):
            panel = copy.deepcopy(self.cfg.task1.panel)
        elif self.cfg.task1.panel_file:
            log.warning("正在使用已弃用的 task1.panel_file；请迁移到 config.yaml 的 task1.panel")
            panel = load_panel(self.cfg.resolve(self.cfg.task1.panel_file))
        else:
            raise RuntimeError("缺少 config.yaml 中的 task1.panel")
        lamps = panel.get("lamps") or []
        switches = panel.get("switches") or []
        if len(lamps) != 3 or len(switches) != 3:
            raise RuntimeError("task1.panel 必须包含 3 盏灯与 3 个开关")
        switch_by_id = {sw.get("id"): sw for sw in switches}
        if len(switch_by_id) != 3:
            raise RuntimeError("task1.panel 的 switch id 必须唯一")
        for lamp in lamps:
            if "switch_id" not in lamp:
                raise RuntimeError("每个 lamp 必须显式配置 switch_id，禁止按左右顺序隐式映射")
            if lamp["switch_id"] not in switch_by_id:
                raise RuntimeError(f"lamp {lamp.get('id')} 指向不存在的 switch_id")
        # 所有动作路径必须在使能、回安全位、观察位之前完整可用。否则模板中的
        # null 位姿会导致机械臂先移动、再在真正操作前失败，不适合现场安全调试。
        pose_keys = ("x", "y", "z", "roll", "pitch", "yaw")
        for sw in switches:
            kind = sw.get("type")
            required = (("approach_pose", "press_pose") if kind == "button" else
                        ("approach_pose", "flick_start_pose", "flick_end_pose") if kind == "toggle" else ())
            if not required:
                raise RuntimeError(f"开关 {sw.get('id')} 的 type 必须为 button 或 toggle")
            for key in required:
                pose = sw.get(key)
                if not isinstance(pose, dict) or any(k not in pose for k in pose_keys):
                    raise RuntimeError(f"开关 {sw.get('id')} 缺少完整示教位姿 {key}")
                try:
                    [float(pose[k]) for k in pose_keys]
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(f"开关 {sw.get('id')}.{key} 包含非数值") from exc
        return panel

    def _detect_consistent_lamp(self, panel: dict) -> int:
        """连续多帧一致才认定亮灯，降低自动曝光和反光造成的误判。"""
        result = None
        streak = 0
        before = None
        for attempt in range(self.cfg.task1.max_retry + 1):
            for _ in range(self.cfg.task1.confirm_frames):
                rgb = self.camera.grab_rgb()
                self.dump.rgb(rgb, "color", "observe")
                idx = self.detector.detect_lit_index(
                    rgb, panel["lamps"], baseline=panel.get("baseline_scores"))
                if idx is not None and idx == result:
                    streak += 1
                else:
                    result, streak = idx, 1 if idx is not None else 0
                if streak >= self.cfg.task1.confirm_frames:
                    return result
                time.sleep(self.cfg.task1.frame_interval_s)
            log.warning("第 %d 次亮灯检测未取得连续一致结果", attempt + 1)
        raise RuntimeError("连续多帧未能稳定识别亮灯，请检查 ROI/基线/相机曝光")

    def _detect_lit_switch(self, panel: dict) -> tuple[int, list[float]]:
        """去观察位拍照，检测亮灯，记录对应开关编号。"""
        self._move(self.cfg.arm.observe_pose, self.cfg.task1.approach_vel,
                   what="观察位", preview=self.cfg.task1.preview_first_move)
        idx = self._detect_consistent_lamp(panel)
        scores = self.detector.scores(self.camera.grab_rgb(), panel["lamps"], self.cfg.task1.roi_radius)
        return idx, scores

    def _operate(self, sw: dict) -> None:
        """按示教位姿完成按压/拨动。"""
        ap = sw.get("approach_pose")
        if not ap:
            raise RuntimeError(
                f"开关 {sw['id']} 未示教 approach_pose，先运行 scripts/02_record_pose.py")
        vel = self.cfg.task1.fine_vel
        self._move(ap, self.cfg.task1.approach_vel, what="开关上方")

        if sw.get("type") == "button":
            pp = sw.get("press_pose")
            if not pp:
                raise RuntimeError(f"按钮开关 {sw['id']} 未示教 press_pose")
            self._move(pp, vel, what="下压")
            log.info("保持按压 %.1fs", self.cfg.task1.press_dwell_s)
            time.sleep(self.cfg.task1.press_dwell_s)
            self._move(ap, vel, what="抬起")

        elif sw.get("type") == "toggle":
            fs = sw.get("flick_start_pose")
            fe = sw.get("flick_end_pose")
            if not fs or not fe:
                raise RuntimeError(
                    f"拨动开关 {sw['id']} 未示教 flick_start_pose / flick_end_pose")
            self._move(fs, vel, what="拨动起点")
            self._move(fe, vel, what="拨动终点")
            self._move(ap, vel, what="退回开关上方")

        else:
            raise RuntimeError(f"未知开关类型: {sw.get('type')}")

    def _verify_action(self, panel: dict, lamp_index: int, before_scores: list[float]) -> None:
        """按现场确认的可观测规则复核动作；未知规则时只记录 motion_only。"""
        mode = self.cfg.task1.action_verify
        if mode == "motion_only":
            log.warning("Task1 当前仅验证轨迹完成；现场确认灯状态规则后应启用 lamp_change")
            return
        if mode != "lamp_change":
            raise RuntimeError(f"未知 task1.action_verify={mode}")
        time.sleep(self.cfg.task1.frame_interval_s)
        after = self.detector.scores(self.camera.grab_rgb(), panel["lamps"], self.cfg.task1.roi_radius)
        if abs(after[lamp_index] - before_scores[lamp_index]) < self.cfg.task1.action_change_min:
            raise RuntimeError("操作后目标灯状态未产生足够可见变化")

    def _lift_to_safe_z(self) -> None:
        """垂直抬升到「观察位高度」（保持 xy/姿态），避免从低位直接横向拉出碰撞。

        观察位是正上方示教的、z 天然高于面板/开关，用它做抬升目标更可靠。
        """
        try:
            cur = self.arm.pose()
            if not cur:
                return
            target_z = self.cfg.arm.observe_pose.get("z", 0.48)
            safe_z = max(float(target_z), float(cur.get("z", 0.48)))
            lift = {"x": cur["x"], "y": cur["y"], "z": safe_z,
                    "roll": cur["roll"], "pitch": cur["pitch"], "yaw": cur["yaw"]}
            self.arm.goto_pose(lift, vel=self.cfg.arm.velocity_slow)
        except Exception as e:
            log.warning("垂直抬升失败，尝试直接返回安全位: %s", e)

    def _retreat(self) -> None:
        """退回安全位：先垂直抬升，再横向返回（尽力而为，失败只记日志）。"""
        try:
            self._lift_to_safe_z()
            self._move(self.cfg.arm.task1_safe_pose, self.cfg.arm.velocity_fast,
                       what="安全位")
        except Exception as e:
            log.error("退回安全位失败: %s", e)

    # ---------- 总入口 ----------
    def run(self) -> tuple[bool, str]:
        """执行一次完整任务1。返回 (success, message)。"""
        t0 = time.time()
        ready = False
        log.info("===== 任务1 开始 =====")
        try:
            self.panel = self._load_and_validate_panel()
            # 配置（尤其是模板中的 null 示教位姿）必须在任何真机动作前失败。
            self._ensure_ready()
            ready = True
            # 未知起始位置时先以当前手型退到安全位，再在净空处伸出食指。
            self._move(self.cfg.arm.task1_safe_pose, self.cfg.arm.velocity_slow,
                       what="起始安全位", preview=self.cfg.task1.preview_first_move)
            self.hand.point_pose()
            lamp_index, before_scores = self._detect_lit_switch(self.panel)
            lamp = self.panel["lamps"][lamp_index]
            self.switch_id = lamp["switch_id"]
            sw = next(sw for sw in self.panel["switches"] if sw["id"] == self.switch_id)
            log.info("亮灯 #%s → 操作开关 #%s（%s）",
                     lamp.get("id", lamp_index), sw["id"], sw["type"])
            self._operate(sw)
            self._verify_action(self.panel, lamp_index, before_scores)
            self._retreat()
            dt = time.time() - t0
            log.info("===== 任务1 完成，耗时 %.1fs =====", dt)
            return True, f"task1 ok (switch {self.switch_id}, {dt:.1f}s)"
        except Exception as e:
            log.exception("任务1失败")
            if ready:
                self._retreat()
            return False, str(e)[:200]
