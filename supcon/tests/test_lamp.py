"""亮灯检测单元测试（无需硬件）。

运行：python tests/test_lamp.py
"""
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.vision.camera import MockCamera
from supcon.vision.lamp import LampDetector

LAMPS = [{"cx": 150, "cy": 240, "color": "green"},
         {"cx": 320, "cy": 240, "color": "white"},
         {"cx": 490, "cy": 240, "color": "red"}]


def test_detect_each_lamp():
    cfg = load_config()
    det = LampDetector(cfg.task1)
    for lit in (0, 1, 2):
        rgb = MockCamera(lamps=LAMPS, lit_index=lit).grab_rgb()
        assert det.detect_lit_index(rgb, LAMPS) == lit, f"lit={lit} 检测错误"


def test_no_lamp_lit():
    cfg = load_config()
    det = LampDetector(cfg.task1)
    rgb = MockCamera(lamps=LAMPS, lit_index=None).grab_rgb()
    assert det.detect_lit_index(rgb, LAMPS) is None


def test_direct_threshold_ignores_white_lamp():
    cfg = load_config()
    det = LampDetector(cfg.task1)
    off = MockCamera(lamps=LAMPS, lit_index=None).grab_rgb()
    on = MockCamera(lamps=LAMPS, lit_index=2).grab_rgb()
    assert det.detect_lit_index(off, LAMPS) is None
    assert det.detect_lit_index(on, LAMPS) == 2


def test_green_overexposed_core_is_detected():
    """Gemini 335 实拍中，绿灯灯芯会过曝成低饱和白/青色。"""
    cfg = load_config()
    det = LampDetector(cfg.task1)
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    # 模拟实拍绿灯：仅有白青高亮灯芯，不再保留高饱和绿色 Hue。
    cv2.circle(rgb, (150, 240), 14, (235, 250, 255), -1)
    states = det.lamp_states(rgb, LAMPS)
    assert states[0]["color_ratio"] == 0.0
    assert states[0]["bright_ratio"] > cfg.task1.green_bright_core_ratio_min
    assert states[0]["criterion"] == "green-bright-core"
    assert det.detect_lit_index(rgb, LAMPS) == 0


def test_find_bright_blobs():
    rgb = MockCamera(lamps=LAMPS, lit_index=0).grab_rgb()
    pts = LampDetector.find_bright_blobs(rgb, n=3)
    assert len(pts) >= 1
    # 最亮光斑中心应在灯0附近
    assert abs(pts[0][0] - 150) < 20 and abs(pts[0][1] - 240) < 20


if __name__ == "__main__":
    test_detect_each_lamp()
    test_no_lamp_lit()
    test_direct_threshold_ignores_white_lamp()
    test_green_overexposed_core_is_detected()
    test_find_bright_blobs()
    print("✅ 亮灯检测测试全部通过")
