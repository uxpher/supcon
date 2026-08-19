"""不依赖真机/网络的 Task3 RGB-D 几何回归测试。"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from supcon.utils import matrix_to_pose, pose_to_matrix
from supcon.vision.handeye import camera_to_base
from supcon.vision.tabletop import TabletopDetector


def test_pose_matrix_round_trip():
    pose = {"x": 0.2, "y": -0.1, "z": 0.3, "roll": -0.2, "pitch": 0.3, "yaw": -0.4}
    restored = matrix_to_pose(pose_to_matrix(pose))
    for key, value in pose.items():
        assert abs(restored[key] - value) < 1e-8


def test_camera_to_base_identity_extrinsic():
    pose = {"x": 0.2, "y": -0.1, "z": 0.3, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    assert np.allclose(camera_to_base(np.array([0.1, 0.2, 0.3]), np.eye(4), pose),
                       [0.3, 0.1, 0.6])


def test_tabletop_detects_four_expected_shapes():
    h, w = 480, 640
    depth = np.full((h, w), 1.0, dtype=np.float32)
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    # 平面深度 1m；四个顶面比桌面近 70mm，模拟正上方 RGB-D 观察。
    cv2.rectangle(depth, (70, 80), (145, 155), 0.93, -1)
    cv2.circle(depth, (250, 120), 37, 0.93, -1)
    cv2.fillPoly(depth, [np.array([[340, 155], [380, 80], [420, 155]], np.int32)], 0.93)
    cv2.fillPoly(depth, [np.array([[490, 120], [510, 85], [550, 85], [570, 120],
                                   [550, 155], [510, 155]], np.int32)], 0.93)
    detector = TabletopDetector({"workspace_roi": [0, 0, w, h], "min_component_area_px": 300,
                                 "min_object_height_m": 0.02, "max_object_height_m": 0.12,
                                 "ransac_iterations": 100})
    objects = detector.detect(rgb, depth, {"fx": 600, "fy": 600, "cx": 320, "cy": 240})
    assert {obj.shape for obj in objects} == {"block", "cylinder", "triangular_prism", "hexagonal_prism"}
    assert all(0.06 < obj.height_m < 0.08 for obj in objects)


def test_missing_task3_calibration_causes_zero_arm_motion():
    from supcon.tasks.task3 import Task3Runner
    pose = {"x": 0.2, "y": 0.0, "z": 0.5, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    scene = {
        "calibration_file": "missing.json", "observe_pose": pose,
        "perception": {},
        "grasp": {"rpy": [0, 0, 0], "pregrasp_clearance_m": 0.1, "grasp_top_offset_m": -0.02,
                  "lift_clearance_m": 0.12, "local_refine_max_xy_m": 0.025, "min_shape_confidence": 0.7},
        "hand_grasps": {name: [0.5] * 10 for name in ("block", "hexagonal_prism", "triangular_prism", "cylinder")},
        "destinations": {name: {"approach_pose": pose, "place_pose": pose, "retreat_pose": pose}
                         for name in ("block", "hexagonal_prism", "triangular_prism", "cylinder")},
    }

    class Arm:
        calls = 0

        def __getattr__(self, _name):
            self.calls += 1
            raise AssertionError("标定缺失时不应访问机械臂")

    class Hand:
        calls = 0

        def __getattr__(self, _name):
            self.calls += 1
            raise AssertionError("标定缺失时不应访问灵巧手")

    with TemporaryDirectory() as directory:
        path = Path(directory) / "task3.json"
        path.write_text(json.dumps(scene), encoding="utf-8")
        cfg = SimpleNamespace(arm=SimpleNamespace(task3_safe_pose=pose),
                              debug=SimpleNamespace(dump_enabled=False), resolve=lambda value: value)
        runner = Task3Runner(cfg, Arm(), Hand(), None, None,
                             SimpleNamespace(scene_file=str(path), observe_vel=0.1, fine_vel=0.05, preflight=True))
        ok, message = runner.run()
    assert not ok
    assert "标定文件" in message
    assert runner.arm.calls == 0
    assert runner.hand.calls == 0
