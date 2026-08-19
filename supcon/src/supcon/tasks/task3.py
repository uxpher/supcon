"""任务 3：RGB-D 定位桌面上任意位置的竖直木块，并按形状放入对应槽位。

不使用源物体的固定 XY 示教点。流程是：全局观察位检测 → 手眼变换到 B9
基座系 → 每个物体在预抓位复拍、按最近同形物体校正 → 竖直抓取/抬升/放置。
任何标定、深度、分类或规划不确定性都会在接触前失败退出，绝不猜测坐标。
"""
from __future__ import annotations

import json
import logging
import math
import os

import numpy as np

from .common import PickPlaceRunner, load_scene
from ..utils import matrix_to_pose, pose_to_matrix
from ..vision.handeye import camera_to_base, load_calibration
from ..vision.tabletop import TabletopDetector, TabletopObject

log = logging.getLogger("task3")

_SHAPES = ("block", "hexagonal_prism", "triangular_prism", "cylinder")
_POSE_KEYS = ("x", "y", "z", "roll", "pitch", "yaw")


class Task3Runner(PickPlaceRunner):
    def __init__(self, cfg, arm, hand, camera, safety, task_cfg):
        super().__init__(cfg, arm, hand, camera, safety, task_cfg,
                         cfg.arm.task3_safe_pose)

    @staticmethod
    def _require_pose(pose: dict | None, label: str) -> None:
        if not isinstance(pose, dict) or any(k not in pose for k in _POSE_KEYS):
            raise RuntimeError(f"{label} 必须是含 x/y/z/roll/pitch/yaw 的示教位姿")
        try:
            values = [float(pose[k]) for k in _POSE_KEYS]
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label} 包含非数值") from exc
        if not all(math.isfinite(v) for v in values):
            raise RuntimeError(f"{label} 包含非有限数")

    def _validate_scene(self, scene: dict) -> None:
        """在使能前校验全部人工标定字段，配置错误必须零运动失败。"""
        self._require_pose(scene.get("observe_pose"), "task3.observe_pose")
        destinations = scene.get("destinations")
        if not isinstance(destinations, dict) or set(destinations) != set(_SHAPES):
            raise RuntimeError(f"task3.destinations 必须且只能包含 {list(_SHAPES)}")
        for shape, destination in destinations.items():
            if not isinstance(destination, dict):
                raise RuntimeError(f"{shape} 槽位配置必须是对象")
            for key in ("approach_pose", "place_pose", "retreat_pose"):
                self._require_pose(destination.get(key), f"{shape}.{key}")
        grasps = scene.get("hand_grasps")
        if not isinstance(grasps, dict) or set(grasps) != set(_SHAPES):
            raise RuntimeError(f"task3.hand_grasps 必须且只能包含 {list(_SHAPES)}")
        for shape, grasp in grasps.items():
            if not isinstance(grasp, list) or len(grasp) != 10:
                raise RuntimeError(f"{shape} 的 hand_grasp 必须为已实测的 10 维手型")
        perception = scene.get("perception")
        if not isinstance(perception, dict):
            raise RuntimeError("task3 缺少 perception（桌面 ROI 与深度分割参数）")
        grasp_cfg = scene.get("grasp")
        if not isinstance(grasp_cfg, dict):
            raise RuntimeError("task3 缺少 grasp（俯抓姿态与安全高度）")
        rpy = grasp_cfg.get("rpy")
        if not isinstance(rpy, list) or len(rpy) != 3 or not all(np.isfinite(float(v)) for v in rpy):
            raise RuntimeError("grasp.rpy 必须为 3 个有限弧度值")
        for key in ("pregrasp_clearance_m", "grasp_top_offset_m", "lift_clearance_m",
                    "local_refine_max_xy_m", "min_shape_confidence"):
            if key not in grasp_cfg or not np.isfinite(float(grasp_cfg[key])):
                raise RuntimeError(f"grasp.{key} 必须为有限数值")
        if float(grasp_cfg["pregrasp_clearance_m"]) <= 0 or float(grasp_cfg["lift_clearance_m"]) <= 0:
            raise RuntimeError("预抓/抬升高度必须大于 0")
        if not -0.08 <= float(grasp_cfg["grasp_top_offset_m"]) <= 0.03:
            raise RuntimeError("grasp_top_offset_m 超出安全范围 [-0.08, 0.03] m")
        if not 0.0 < float(grasp_cfg["min_shape_confidence"]) <= 1.0:
            raise RuntimeError("min_shape_confidence 必须在 (0,1] 内")

    def _intrinsics(self, scene: dict) -> dict:
        """真机优先采用 SDK 内参；文件模式可在 task3.json 写入内参。"""
        intrinsics = getattr(self.camera, "intrinsics", None) or scene.get("intrinsics")
        if not intrinsics and self.cfg.camera.intrinsics_file:
            path = self.cfg.resolve(self.cfg.camera.intrinsics_file)
            try:
                with open(path, encoding="utf-8") as f:
                    intrinsics = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"无法读取相机内参 {path}: {exc}") from exc
        if not isinstance(intrinsics, dict):
            raise RuntimeError("缺少相机内参；真机请确认 SDK 可读内参，离线请在 task3.json 填 intrinsics")
        try:
            out = {k: float(intrinsics[k]) for k in ("fx", "fy", "cx", "cy")}
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("相机内参必须包含 fx/fy/cx/cy") from exc
        if out["fx"] <= 0 or out["fy"] <= 0:
            raise RuntimeError("相机内参 fx/fy 必须大于 0")
        return out

    def _observe(self, detector: TabletopDetector, intrinsics: dict,
                 calibration: dict, tag: str) -> list[tuple[TabletopObject, np.ndarray]]:
        """原子采集 RGB-D，并将物体顶部中心投到当前 B9 基座系。"""
        rgb, depth = self.camera.grab_rgbd()
        self.dump.rgb(rgb, "shape", tag)
        if depth is not None:
            self.dump.depth_vis(depth, tag)
        objects = detector.detect(rgb, depth, intrinsics)
        eef_pose = self.arm.pose()
        if not eef_pose:
            raise RuntimeError("无法读取当前末端位姿，拒绝将视觉坐标用于运动")
        result = []
        for obj in objects:
            base = camera_to_base(obj.top_camera, calibration["T_eef_camera"], eef_pose)
            result.append((obj, base))
        return result

    @staticmethod
    def _validate_detection(detected: list[tuple[TabletopObject, np.ndarray]], min_confidence: float) -> dict[str, np.ndarray]:
        if len(detected) != 4:
            raise RuntimeError(f"桌面必须检测到 4 个独立木块，实际为 {len(detected)}")
        positions: dict[str, np.ndarray] = {}
        for obj, base in detected:
            if obj.shape not in _SHAPES:
                raise RuntimeError("存在无法分类的木块，拒绝猜测")
            if obj.confidence < min_confidence:
                raise RuntimeError(f"{obj.shape} 分类置信度 {obj.confidence:.2f} 低于阈值 {min_confidence:.2f}")
            if obj.shape in positions:
                raise RuntimeError(f"检测到重复形状 {obj.shape}，拒绝猜测槽位")
            positions[obj.shape] = base
        if set(positions) != set(_SHAPES):
            raise RuntimeError("桌面木块形状必须恰好为长方体、六棱柱、三棱柱、圆柱各一个")
        return positions

    @staticmethod
    def _make_tcp_pose(base_top: np.ndarray, rpy: list, z_offset: float) -> dict:
        return {"x": float(base_top[0]), "y": float(base_top[1]), "z": float(base_top[2] + z_offset),
                "roll": float(rpy[0]), "pitch": float(rpy[1]), "yaw": float(rpy[2])}

    @staticmethod
    def _eef_pose_for_tcp(tcp_pose: dict, T_eef_tcp: np.ndarray) -> dict:
        """目标实际 TCP → B9 接口的末端位姿。

        标定文件中的 ``T_eef_tcp`` 约定为 TCP 坐标到 B9 末端坐标的变换，
        因而 ``T_base_eef = T_base_tcp · inv(T_eef_tcp)``。
        """
        return matrix_to_pose(pose_to_matrix(tcp_pose) @ np.linalg.inv(T_eef_tcp))

    def _grasp_poses(self, base_top: np.ndarray, grasp_cfg: dict,
                     calibration: dict) -> tuple[dict, dict, dict]:
        rpy = grasp_cfg["rpy"]
        pre_tcp = self._make_tcp_pose(base_top, rpy, float(grasp_cfg["pregrasp_clearance_m"]))
        grasp_tcp = self._make_tcp_pose(base_top, rpy, float(grasp_cfg["grasp_top_offset_m"]))
        lift_tcp = self._make_tcp_pose(base_top, rpy, float(grasp_cfg["lift_clearance_m"]))
        return tuple(self._eef_pose_for_tcp(p, calibration["T_eef_tcp"])
                     for p in (pre_tcp, grasp_tcp, lift_tcp))

    def _locally_refine(self, detector: TabletopDetector, intrinsics: dict,
                        calibration: dict, shape: str, expected_base: np.ndarray,
                        max_xy_error: float) -> np.ndarray:
        """在预抓高度复拍，仅接纳同形且接近全局观测的目标。"""
        candidates = [(obj, base) for obj, base in self._observe(detector, intrinsics, calibration,
                                                                  f"pregrasp_{shape}")
                      if obj.shape == shape]
        if not candidates:
            raise RuntimeError(f"预抓位复拍未找到 {shape}，可能被遮挡或识别错误")
        obj, refined = min(candidates, key=lambda x: float(np.linalg.norm(x[1][:2] - expected_base[:2])))
        error = float(np.linalg.norm(refined[:2] - expected_base[:2]))
        if error > max_xy_error:
            raise RuntimeError(f"{shape} 复拍位置偏差 {error * 1000:.1f} mm，超过 {max_xy_error * 1000:.1f} mm")
        log.info("%s 复拍定位：xy 修正 %.1f mm，置信度 %.2f", shape, error * 1000, obj.confidence)
        return refined

    def run(self) -> tuple[bool, str]:
        ready = False
        try:
            # 先校验配置和标定。任何错误发生在 ready() 前，避免默认安全位也被下发。
            scene = load_scene(self.cfg.resolve(self.task_cfg.scene_file))
            self._validate_scene(scene)
            calibration_file = scene.get("calibration_file")
            if not calibration_file:
                raise RuntimeError("task3 缺少 calibration_file")
            calibration_path = calibration_file if os.path.isabs(calibration_file) else self.cfg.resolve(calibration_file)
            calibration = load_calibration(calibration_path, require_tcp=True)
            if calibration is None:
                raise RuntimeError("手眼/TCP 标定文件不存在")
            intrinsics = self._intrinsics(scene)
            detector = TabletopDetector(scene["perception"])
            grasp_cfg = scene["grasp"]
            min_confidence = float(grasp_cfg["min_shape_confidence"])

            self.lift_z = float(scene["observe_pose"]["z"])
            self.ready()
            ready = True
            self.move(scene["observe_pose"], "Task3 全局观察位", self.task_cfg.observe_vel)
            initial = self._validate_detection(
                self._observe(detector, intrinsics, calibration, "global"), min_confidence)
            log.info("初始视觉定位（B9 基座系）: %s", {k: np.round(v, 4).tolist() for k, v in initial.items()})

            for shape in _SHAPES:
                destination = scene["destinations"][shape]
                pre, grasp, lift = self._grasp_poses(initial[shape], grasp_cfg, calibration)
                self.preflight([pre, grasp, lift, destination["approach_pose"],
                                destination["place_pose"], destination["retreat_pose"]])
                self.move(pre, f"{shape} 预抓位", self.task_cfg.observe_vel)
                refined = self._locally_refine(detector, intrinsics, calibration, shape, initial[shape],
                                                float(grasp_cfg["local_refine_max_xy_m"]))
                pre, grasp, lift = self._grasp_poses(refined, grasp_cfg, calibration)
                # 复拍后的微小校正也需先规划，随后才允许向下接触。
                self.preflight([pre, grasp, lift, destination["approach_pose"],
                                destination["place_pose"], destination["retreat_pose"]])
                self.move(pre, f"{shape} 校正预抓位", self.task_cfg.fine_vel)
                self.move(grasp, f"{shape} 竖直抓取位", self.task_cfg.fine_vel)
                if self.hand.close_with_verify(close_norm=scene["hand_grasps"][shape]) != "GRASPED":
                    self.hand.open_hand()
                    raise RuntimeError(f"{shape} 抓取验证失败：夹空")
                self.move(lift, f"{shape} 竖直抬升", self.task_cfg.fine_vel)
                self.move(destination["approach_pose"], f"{shape} 槽接近", self.task_cfg.observe_vel)
                self.move(destination["place_pose"], f"{shape} 槽放置", self.task_cfg.fine_vel)
                self.hand.open_hand()
                self.move(destination["retreat_pose"], f"{shape} 槽撤离", self.task_cfg.observe_vel)

            self.retreat()
            return True, "task3 ok (RGB-D dynamic pick/place)"
        except Exception as exc:
            log.exception("任务3失败")
            if ready:
                self.retreat()
            return False, str(exc)[:200]
