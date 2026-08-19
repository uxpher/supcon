"""任务 2：仅顶面数字的长方体，严格按 1→2→3→4 转运至指定台面。

数字识别：整图送入 PaddleOCR（OCR 按文本框 x 坐标左→右排序），
得到 4 个数字后按方位 left→midleft→midright→right 一一对应，
不需要 ROI/模板匹配。
"""
from __future__ import annotations

import logging

from .common import PickPlaceRunner, scene_from_task_config
from ..vision.ocr import OcrRecognizer

log = logging.getLogger("task2")

_POSITIONS = ("left", "midleft", "midright", "right")
_POSE_KEYS = ("x", "y", "z", "roll", "pitch", "yaw")


class Task2Runner(PickPlaceRunner):
    def __init__(self, cfg, arm, hand, camera, safety, task_cfg):
        super().__init__(cfg, arm, hand, camera, safety, task_cfg,
                         cfg.arm.task2_safe_pose)

    def _recognize_position_to_digit(self, rgb, ocr) -> dict[str, int]:
        """整图 OCR → 4 个数字（左→右）→ 映射到方位 {方位: 数字}。"""
        digits = ocr.recognize_digits(rgb)
        if len(digits) != 4 or set(digits) != {1, 2, 3, 4}:
            raise RuntimeError(
                f"OCR 未识别出 1-4 四个数字（得到 {digits}），"
                f"请检查观察位视角/光照，或确认数字均完整位于顶面")
        return dict(zip(_POSITIONS, digits))

    @staticmethod
    def _require_pose(pose: dict | None, label: str) -> None:
        if not isinstance(pose, dict) or any(key not in pose for key in _POSE_KEYS):
            raise RuntimeError(f"{label} 必须是含 x/y/z/roll/pitch/yaw 的完整示教位姿")
        try:
            [float(pose[key]) for key in _POSE_KEYS]
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label} 包含非数值") from exc

    def _validate_scene(self, scene: dict) -> None:
        """在使能前拒绝未完成的场景模板，保证零运动失败。"""
        self._require_pose(scene.get("observe_pose"), "task2.scene.observe_pose")
        sources = scene.get("sources") or {}
        placements = scene.get("table_placements") or {}
        if set(sources) != set(_POSITIONS):
            raise RuntimeError("task2.scene 的 sources 必须包含 left/midleft/midright/right 四个方位")
        if set(placements) != {"1", "2", "3", "4"}:
            raise RuntimeError("task2.scene 必须包含指定台面的 1..4 放置位")
        default_grasp = scene.get("default_hand_grasp")
        if not isinstance(default_grasp, list) or len(default_grasp) != 10:
            raise RuntimeError("task2.scene.default_hand_grasp 必须为已实测的 10 维手型")
        for name, source in sources.items():
            if not isinstance(source, dict):
                raise RuntimeError(f"task2.scene.sources.{name} 必须是对象")
            for key in ("approach_pose", "grasp_tcp_pose", "lift_pose"):
                self._require_pose(source.get(key), f"task2.scene.sources.{name}.{key}")
            grasp = source.get("hand_grasp")
            if grasp is not None and (not isinstance(grasp, list) or len(grasp) != 10):
                raise RuntimeError(f"task2.scene.sources.{name}.hand_grasp 必须为 10 维或 null")
        for name, destination in placements.items():
            if not isinstance(destination, dict):
                raise RuntimeError(f"task2.scene.table_placements.{name} 必须是对象")
            for key in ("approach_pose", "place_pose", "retreat_pose"):
                self._require_pose(destination.get(key), f"task2.scene.table_placements.{name}.{key}")

    def run(self) -> tuple[bool, str]:
        ready = False
        try:
            # 先加载、检查内联配置；避免缺标定时 ready() 把真机移动到安全位。
            scene = scene_from_task_config(self.cfg, self.task_cfg, "2")
            self._validate_scene(scene)
            self.lift_z = (scene.get("observe_pose") or {}).get("z")
            sources = scene.get("sources") or {}
            placements = scene.get("table_placements") or {}
            self.ready()
            ready = True
            self.move(scene["observe_pose"], "任务2观察位", self.task_cfg.observe_vel)
            rgb = self.camera.grab_rgb()
            self.dump.rgb(rgb, "ocr", "observe")
            # 识别阶段：整图 OCR，左→右 → 方位
            ocr = OcrRecognizer()
            position_to_digit = self._recognize_position_to_digit(rgb, ocr)
            log.info("方位→数字映射: %s", position_to_digit)
            # 抓取阶段：按 1→2→3→4 顺序，查方位
            for digit in range(1, 5):
                position = next(p for p, d in position_to_digit.items() if d == digit)
                source = sources[position]
                grasp = source.get("hand_grasp") or scene.get("default_hand_grasp")
                if not grasp:
                    raise RuntimeError(f"数字 {digit}（方位 {position}）未配置抓取手型")
                log.info("抓取数字 %d → 方位 %s", digit, position)
                self.pick_and_place(source, placements[str(digit)], grasp)
            self.retreat()
            return True, "task2 ok (1→2→3→4)"
        except Exception as exc:
            log.exception("任务2失败")
            if ready:
                self.retreat()
            return False, str(exc)[:200]
