"""任务 2：仅顶面数字的长方体，严格按 1→2→3→4 转运至指定台面。"""
from __future__ import annotations

import logging

from .common import PickPlaceRunner, load_scene
from ..vision.digit import DigitRecognizer

log = logging.getLogger("task2")


class Task2Runner(PickPlaceRunner):
    def run(self) -> tuple[bool, str]:
        try:
            self.ready()
            scene = load_scene(self.cfg.resolve(self.task_cfg.scene_file))
            sources = scene.get("sources") or []
            placements = scene.get("table_placements") or {}
            if len(sources) != 4 or set(placements) != {"1", "2", "3", "4"}:
                raise RuntimeError("task2.json 必须包含 4 个 sources 与指定台面的 1..4 放置位")
            self.move(scene["observe_pose"], "任务2观察位", self.task_cfg.observe_vel)
            rgb = self.camera.grab_rgb()
            recognizer = DigitRecognizer(self.cfg.resolve(scene["digit_template_dir"]), scene.get("digit_min_score", 0.72))
            by_digit: dict[int, dict] = {}
            for source in sources:
                x, y, w, h = source["top_digit_roi"]
                digit, score = recognizer.recognize(rgb[y:y+h, x:x+w])
                if digit in by_digit:
                    raise RuntimeError(f"数字 {digit} 重复识别，拒绝按错误顺序操作")
                source = dict(source)
                source["digit"] = digit
                by_digit[digit] = source
                log.info("槽位 %s 顶面数字=%d score=%.3f", source.get("id"), digit, score)
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
