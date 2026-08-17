"""亮灯检测单元测试（无需硬件）。

运行：python tests/test_lamp.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon_task2.config import load_config
from supcon_task2.vision.camera import MockCamera
from supcon_task2.vision.lamp import LampDetector

LAMPS = [{"cx": 150, "cy": 240}, {"cx": 320, "cy": 240}, {"cx": 490, "cy": 240}]


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


def test_detect_with_baseline():
    cfg = load_config()
    det = LampDetector(cfg.task1)
    off = MockCamera(lamps=LAMPS, lit_index=None).grab_rgb()
    baseline = det.scores(off, LAMPS, cfg.task1.roi_radius)
    on = MockCamera(lamps=LAMPS, lit_index=2).grab_rgb()
    assert det.detect_lit_index(on, LAMPS, baseline=baseline) == 2


def test_find_bright_blobs():
    rgb = MockCamera(lamps=LAMPS, lit_index=0).grab_rgb()
    pts = LampDetector.find_bright_blobs(rgb, n=3)
    assert len(pts) >= 1
    # 最亮光斑中心应在灯0附近
    assert abs(pts[0][0] - 150) < 20 and abs(pts[0][1] - 240) < 20


if __name__ == "__main__":
    test_detect_each_lamp()
    test_no_lamp_lit()
    test_detect_with_baseline()
    test_find_bright_blobs()
    print("✅ 亮灯检测测试全部通过")
