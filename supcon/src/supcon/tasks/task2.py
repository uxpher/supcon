"""任务 2：仅顶面数字的长方体，严格按 1→2→3→4 转运至指定台面。

数字识别：整图送入 PaddleOCR（OCR 按文本框 x 坐标左→右排序），
得到 4 个数字后按方位 left→midleft→midright→right 一一对应，
不需要 ROI/模板匹配。
"""
from __future__ import annotations

import logging

from .common import PickPlaceRunner, load_scene
from ..vision.ocr import OcrRecognizer

log = logging.getLogger("task2")

_POSITIONS = ("left", "midleft", "midright", "right")


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

    def run(self) -> tuple[bool, str]:
        ready = False
        try:
            # 先加载、检查现场文件；避免缺标定时 ready() 把真机移动到安全位。
            scene = load_scene(self.cfg.resolve(self.task_cfg.scene_file))
            self.lift_z = (scene.get("observe_pose") or {}).get("z")
            sources = scene.get("sources") or {}
            placements = scene.get("table_placements") or {}
            if set(sources) != set(_POSITIONS):
                raise RuntimeError("task2.json 的 sources 必须包含 left/midleft/midright/right 四个方位")
            if set(placements) != {"1", "2", "3", "4"}:
                raise RuntimeError("task2.json 必须包含指定台面的 1..4 放置位")
            if not scene.get("observe_pose"):
                raise RuntimeError("task2.json 缺少 observe_pose")
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
