"""任务 3：竖直几何体按形状入对应槽位。

依据更新规则，物体均竖直摆放；本实现不执行旧规则中高风险的空中 6-DOF 翻转。
"""
from __future__ import annotations

import logging

from .common import PickPlaceRunner, load_scene
from ..vision.shape import ShapeRecognizer

log = logging.getLogger("task3")


class Task3Runner(PickPlaceRunner):
    def run(self) -> tuple[bool, str]:
        try:
            self.ready()
            scene = load_scene(self.cfg.resolve(self.task_cfg.scene_file))
            sources = scene.get("sources") or []
            destinations = scene.get("destinations") or {}
            if len(sources) != 4:
                raise RuntimeError("task3.json 必须包含 4 个源工位")
            self.move(scene["observe_pose"], "任务3观察位", self.task_cfg.observe_vel)
            rgb = self.camera.grab_rgb()
            recognizer = ShapeRecognizer(scene.get("min_contour_area", 400))
            planned: list[tuple[dict, str]] = []
            used_types: set[str] = set()
            for source in sources:
                x, y, w, h = source["roi"]
                inferred, confidence = recognizer.classify(rgb[y:y+h, x:x+w])
                shape = source.get("type_override") or inferred
                if shape in used_types:
                    raise RuntimeError(f"形状 {shape} 重复，拒绝猜测对应槽位")
                if shape not in destinations:
                    raise RuntimeError(f"未配置形状 {shape} 的目标槽位")
                used_types.add(shape)
                planned.append((source, shape))
                log.info("源工位 %s 分类=%s conf=%.3f", source.get("id"), shape, confidence)
            for source, shape in planned:
                grasp = source.get("hand_grasp") or scene.get("hand_grasps", {}).get(shape)
                if not grasp:
                    raise RuntimeError(f"形状 {shape} 未配置抓取手型")
                # 只允许竖直抓取/竖直放置；所有末端姿态由标定文件示教。
                self.pick_and_place(source, destinations[shape], grasp)
            self.retreat()
            return True, "task3 ok"
        except Exception as exc:
            log.exception("任务3失败")
            self.retreat()
            return False, str(exc)[:200]
