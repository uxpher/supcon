"""任务 2/3 的共用、校准文件驱动抓放流程。"""
from __future__ import annotations

import json
import logging
import os

from ..robot.arm import ArmError
from ..robot.hand import HandError

log = logging.getLogger("tasks.common")


def load_scene(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺少现场标定文件 {path}；请从对应 .example.json 复制并完成示教")
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


class PickPlaceRunner:
    def __init__(self, cfg, arm, hand, camera, safety, task_cfg):
        self.cfg, self.arm, self.hand, self.camera, self.safety = cfg, arm, hand, camera, safety
        self.task_cfg = task_cfg

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
        self.arm.goto_pose(self.cfg.arm.safe_pose, vel=self.cfg.arm.velocity_slow,
                           plan_only=self.task_cfg.preflight)
        self.arm.goto_pose(self.cfg.arm.safe_pose, vel=self.cfg.arm.velocity_slow)
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

    def retreat(self) -> None:
        try:
            self.hand.open_hand()
            self.arm.goto_pose(self.cfg.arm.safe_pose, vel=self.cfg.arm.velocity_slow)
        except Exception as exc:
            log.error("安全撤离失败：%s", exc)
