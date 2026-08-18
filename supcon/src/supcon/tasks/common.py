"""任务 2/3 的共用、校准文件驱动抓放流程。"""
from __future__ import annotations

import json
import logging
import os

from ..robot.arm import ArmError
from ..robot.hand import HandError
from ..vision.dump import DebugDump

log = logging.getLogger("tasks.common")


def load_scene(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺少现场标定文件 {path}；请从对应 .example.json 复制并完成示教")
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


class PickPlaceRunner:
    def __init__(self, cfg, arm, hand, camera, safety, task_cfg, safe_pose=None):
        self.cfg, self.arm, self.hand, self.camera, self.safety = cfg, arm, hand, camera, safety
        self.task_cfg = task_cfg
        self.safe_pose = safe_pose or cfg.arm.task1_safe_pose
        self.lift_z = None   # 撤离抬升高度；任务 run 里设为观察位 z（高于物体）
        self.dump = DebugDump(cfg)

    def check(self) -> None:
        if self.safety is not None:
            self.safety.assert_ok()

    def ready(self) -> None:
        ok, why = self.arm.healthy()
        if not ok:
            raise ArmError(f"机械臂异常：{why}")
        if not self.hand.status().get("connected"):
            raise HandError("灵巧手未连接")
        errors = self.hand.errors().get("error_codes") or []
        if any(code != 0 for code in errors):
            raise HandError(f"灵巧手存在错误码：{errors}")
        self.arm.enable()
        if not self.arm.enabled_all():
            raise ArmError("机械臂未完全使能")
        self.arm.goto_pose(self.safe_pose, vel=self.cfg.arm.velocity_slow,
                           plan_only=self.task_cfg.preflight)
        self.arm.goto_pose(self.safe_pose, vel=self.cfg.arm.velocity_slow)
        self.hand.open_hand()

    def move(self, pose: dict, label: str, velocity: float | None = None) -> None:
        self.check()
        self.arm.goto_pose(pose, vel=velocity or self.task_cfg.fine_vel)
        self.check()
        log.info("到达 %s", label)

    def preflight(self, poses: list[dict]) -> None:
        if not self.task_cfg.preflight:
            return
        for pose in poses:
            self.arm.goto_pose(pose, vel=self.task_cfg.fine_vel, plan_only=True)

    def pick_and_place(self, source: dict, destination: dict, grasp_pose: list[float]) -> None:
        required_source = ("approach_pose", "grasp_tcp_pose", "lift_pose")
        required_destination = ("approach_pose", "place_pose", "retreat_pose")
        for key in required_source:
            if not source.get(key):
                raise RuntimeError(f"源工位缺少 {key}")
        for key in required_destination:
            if not destination.get(key):
                raise RuntimeError(f"目标工位缺少 {key}")
        self.preflight([source[k] for k in required_source] + [destination[k] for k in required_destination])
        self.move(source["approach_pose"], "源工位接近", self.task_cfg.observe_vel)
        self.move(source["grasp_tcp_pose"], "抓取位")
        result = self.hand.close_with_verify(close_norm=grasp_pose)
        if result != "GRASPED":
            self.hand.open_hand()
            raise RuntimeError("抓取验证失败：夹空")
        self.move(source["lift_pose"], "抬升", self.task_cfg.fine_vel)
        self.move(destination["approach_pose"], "目标工位接近", self.task_cfg.observe_vel)
        self.move(destination["place_pose"], "放置位")
        self.hand.open_hand()
        self.move(destination["retreat_pose"], "目标工位撤离")

    def _lift_to_safe_z(self) -> None:
        """垂直抬升到「观察位高度」（保持 xy/姿态），避免从低位直接横向拉出碰撞。

        观察位是正上方示教的、z 天然高于下方物体，用它做抬升目标比 safe_pose.z 更可靠。
        抬升目标 = max(观察位 z, 当前 z)，保证不下坠。
        """
        try:
            cur = self.arm.pose()
            if not cur:
                return
            target_z = self.lift_z or self.safe_pose.get("z", 0.48)
            safe_z = max(float(target_z), float(cur.get("z", 0.48)))
            lift = {"x": cur["x"], "y": cur["y"], "z": safe_z,
                    "roll": cur["roll"], "pitch": cur["pitch"], "yaw": cur["yaw"]}
            self.arm.goto_pose(lift, vel=self.cfg.arm.velocity_slow)
        except Exception as exc:
            log.warning("垂直抬升失败，尝试直接返回安全位: %s", exc)

    def retreat(self) -> None:
        try:
            self.hand.open_hand()
            self._lift_to_safe_z()
            self.arm.goto_pose(self.safe_pose, vel=self.cfg.arm.velocity_slow)
        except Exception as exc:
            log.error("安全撤离失败：%s", exc)
