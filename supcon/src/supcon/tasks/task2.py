"""任务 2：仅顶面数字的长方体，严格按 1→2→3→4 转运至指定台面。

数字识别：OCR 优先（PaddleOCR CPU），模板匹配（digit.py）兜底。
scene 可选字段 digit_mode：auto（默认，OCR 优先失败回退模板）/ ocr / template。
"""
from __future__ import annotations

import logging

from .common import PickPlaceRunner, load_scene
from ..vision.digit import DigitRecognizer
from ..vision.ocr import OcrRecognizer

log = logging.getLogger("task2")


class Task2Runner(PickPlaceRunner):
    def __init__(self, cfg, arm, hand, camera, safety, task_cfg):
        super().__init__(cfg, arm, hand, camera, safety, task_cfg,
                         cfg.arm.task2_safe_pose)

    def _recognize_digit(self, rgb, source, scene, ocr):
        """识别单个顶面数字。返回 (digit, score, method)。"""
        x, y, w, h = source["top_digit_roi"]
        crop = rgb[y:y + h, x:x + w]
        mode = scene.get("digit_mode", "auto")

        # 1) OCR 优先
        if mode in ("auto", "ocr") and ocr.available:
            r = ocr.recognize_digit(crop)
            if r:
                return r[0], r[1], "ocr"

        # 2) 模板匹配兜底
        if mode in ("auto", "template"):
            recognizer = DigitRecognizer(
                self.cfg.resolve(scene["digit_template_dir"]),
                scene.get("digit_min_score", 0.72),
            )
            digit, score = recognizer.recognize(crop)
            return digit, score, "template"

        raise RuntimeError(f"数字识别不可用（digit_mode={mode} 且无可用识别器）")

    def run(self) -> tuple[bool, str]:
        try:
            self.ready()
            scene = load_scene(self.cfg.resolve(self.task_cfg.scene_file))
            self.lift_z = (scene.get("observe_pose") or {}).get("z")
            sources = scene.get("sources") or []
            placements = scene.get("table_placements") or {}
            if len(sources) != 4 or set(placements) != {"1", "2", "3", "4"}:
                raise RuntimeError("task2.json 必须包含 4 个 sources 与指定台面的 1..4 放置位")
            self.move(scene["observe_pose"], "任务2观察位", self.task_cfg.observe_vel)
            rgb = self.camera.grab_rgb()
            ocr = OcrRecognizer()
            by_digit: dict[int, dict] = {}
            for source in sources:
                digit, score, method = self._recognize_digit(rgb, source, scene, ocr)
                if digit in by_digit:
                    raise RuntimeError(f"数字 {digit} 重复识别，拒绝按错误顺序操作")
                source = dict(source)
                source["digit"] = digit
                by_digit[digit] = source
                log.info("槽位 %s 顶面数字=%d score=%.3f (%s)",
                         source.get("id"), digit, score, method)
            if set(by_digit) != {1, 2, 3, 4}:
                raise RuntimeError(f"数字识别不完整：{sorted(by_digit)}")
            for digit in range(1, 5):
                source = by_digit[digit]
                grasp = source.get("hand_grasp") or scene.get("default_hand_grasp")
                if not grasp:
                    raise RuntimeError(f"数字 {digit} 未配置抓取手型")
                # destination 独立配置，确保放置位置和初始竖直姿态均可现场示教复现。
                self.pick_and_place(source, placements[str(digit)], grasp)
            self.retreat()
            return True, "task2 ok (1→2→3→4)"
        except Exception as exc:
            log.exception("任务2失败")
            self.retreat()
            return False, str(exc)[:200]
