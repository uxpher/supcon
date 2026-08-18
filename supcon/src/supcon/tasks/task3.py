"""任务 3：竖直几何体按形状入对应槽位。

形状确定优先级（从高到低）：
    1) type_override —— 人工预设（最稳，现场确认后直接填）
    2) OCR —— 识别源工位外侧汉字标签（label_roi，如「三棱柱」「圆柱」）
    3) 轮廓分类 —— shape.py（传统 CV 算法兜底，信息不明确时保留）

观察位设计（解决中心俯视的斜视角变形）：
    - 抓取端 4 个观察位：每个源工位正上方一个（sources[i].observe_pose），逐个拍照识别形状；
    - 放置端 4 个观察位：每个目标槽正上方一个（destinations[shape].observe_pose），放置前观察；
    - 维护 placed 集合：某形状槽已放过则跳过观察（防御性，正常每种形状唯一）。

依据更新规则，物体均竖直摆放；本实现不执行旧规则中高风险的空中 6-DOF 翻转。
"""
from __future__ import annotations

import logging

from .common import PickPlaceRunner, load_scene
from ..vision.shape import ShapeRecognizer
from ..vision.ocr import OcrRecognizer

log = logging.getLogger("task3")


class Task3Runner(PickPlaceRunner):
    def __init__(self, cfg, arm, hand, camera, safety, task_cfg):
        super().__init__(cfg, arm, hand, camera, safety, task_cfg,
                         cfg.arm.task3_safe_pose)

    def _classify_source(self, rgb, source, ocr, shape_recognizer):
        """返回 (shape, confidence, method)。"""
        # 1) 人工预设优先
        override = source.get("type_override")
        if override:
            return override, 1.0, "override"

        # 2) OCR 识别源工位外侧汉字标签（label_roi 为可选字段）
        label_roi = source.get("label_roi")
        if label_roi and ocr.available:
            lx, ly, lw, lh = label_roi
            r = ocr.recognize_shape_label(rgb[ly:ly + lh, lx:lx + lw])
            if r:
                return r[0], r[1], "ocr"

        # 3) 轮廓分类兜底
        x, y, w, h = source["roi"]
        shape, confidence = shape_recognizer.classify(rgb[y:y + h, x:x + w])
        return shape, confidence, "shape"

    def run(self) -> tuple[bool, str]:
        try:
            self.ready()
            scene = load_scene(self.cfg.resolve(self.task_cfg.scene_file))
            sources = scene.get("sources") or []
            destinations = scene.get("destinations") or {}
            if len(sources) != 4:
                raise RuntimeError("task3.json 必须包含 4 个源工位")
            # 撤离抬升高度 = 所有观察位（抓取端+放置端）的最大 z，高于所有柱体/槽位
            obs_zs = []
            for s in sources:
                z = (s.get("observe_pose") or {}).get("z")
                if z:
                    obs_zs.append(float(z))
            for d in destinations.values():
                z = (d.get("observe_pose") or {}).get("z")
                if z:
                    obs_zs.append(float(z))
            self.lift_z = max(obs_zs) if obs_zs else None
            ocr = OcrRecognizer()
            shape_recognizer = ShapeRecognizer(scene.get("min_contour_area", 400))

            # ===== 阶段 1：识别（抓取端 4 个观察位，逐个正上方拍照）=====
            planned: list[tuple[dict, str]] = []
            used_types: set[str] = set()
            for source in sources:
                self.move(source["observe_pose"], f"源工位 {source.get('id')} 观察位",
                          self.task_cfg.observe_vel)
                rgb = self.camera.grab_rgb()
                self.dump.rgb(rgb, "shape", f"src{source.get('id')}")
                # 深度矩阵在内存中处理（grab_depth → H×W float32 米），并把伪彩图落盘排查。
                depth = self.camera.grab_depth()
                if depth is not None:
                    self.dump.depth_vis(depth, f"src{source.get('id')}")
                shape, confidence, method = self._classify_source(
                    rgb, source, ocr, shape_recognizer)
                if shape in used_types:
                    raise RuntimeError(f"形状 {shape} 重复，拒绝猜测对应槽位")
                if shape not in destinations:
                    raise RuntimeError(f"未配置形状 {shape} 的目标槽位")
                used_types.add(shape)
                planned.append((source, shape))
                log.info("源工位 %s 分类=%s conf=%.3f (%s)",
                         source.get("id"), shape, confidence, method)

            # ===== 阶段 2：抓取放置（维护 placed，放置前观察目标槽）=====
            placed: set[str] = set()
            for source, shape in planned:
                grasp = source.get("hand_grasp") or scene.get("hand_grasps", {}).get(shape)
                if not grasp:
                    raise RuntimeError(f"形状 {shape} 未配置抓取手型")
                dest = destinations[shape]
                # 抓取
                self.move(source["approach_pose"], "源工位接近", self.task_cfg.observe_vel)
                self.move(source["grasp_tcp_pose"], "抓取位")
                result = self.hand.close_with_verify(close_norm=grasp)
                if result != "GRASPED":
                    self.hand.open_hand()
                    raise RuntimeError("抓取验证失败：夹空")
                self.move(source["lift_pose"], "抬升", self.task_cfg.fine_vel)
                # 放置：槽位未放过时先到放置观察位（正上方）
                if shape not in placed:
                    self.move(dest["observe_pose"], f"{shape} 槽观察位",
                              self.task_cfg.observe_vel)
                self.move(dest["approach_pose"], "目标槽接近", self.task_cfg.observe_vel)
                self.move(dest["place_pose"], "放置位")
                self.hand.open_hand()
                self.move(dest["retreat_pose"], "目标槽撤离")
                placed.add(shape)

            self.retreat()
            return True, "task3 ok"
        except Exception as exc:
            log.exception("任务3失败")
            self.retreat()
            return False, str(exc)[:200]
