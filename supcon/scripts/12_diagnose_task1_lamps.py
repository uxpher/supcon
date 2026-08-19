#!/usr/bin/env python3
"""Task1 指示灯 HSV 阈值现场诊断（只读相机，不控制机械臂）。

应在机械臂已经停在观察位、且只点亮一盏灯时运行：
    python scripts/12_diagnose_task1_lamps.py

输出每个已标定 ROI 的绿色像素比例及 HSV 统计，并保存带 ROI 标记的图片。
"""
import pathlib
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import PROJECT_ROOT, load_config
from supcon.vision.camera import make_camera
from supcon.vision.lamp import LampDetector


def main():
    cfg = load_config()
    lamps = (cfg.task1.panel or {}).get("lamps") or []
    if len(lamps) != 3:
        raise RuntimeError("请先运行 03_calibrate_panel.py --mode manual，完成 3 个灯 ROI 标定")

    camera = make_camera(cfg.camera)
    try:
        # 丢弃首帧，给自动曝光一点收敛时间；仍不移动机械臂。
        camera.grab_rgb()
        time.sleep(0.2)
        rgb = camera.grab_rgb()
    finally:
        camera.close()

    detector = LampDetector(cfg.task1)
    states = detector.lamp_states(rgb, lamps)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    view = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    h, w = hsv.shape[:2]
    print("HSV 阈值：green H=%d~%d；red H<=%d 或 H>=%d；彩色灯 S>=%d；"
          "白灯 S<=%d；三类灯 V>=%d；ratio>=%.3f；绿灯高亮核心>=%.3f" % (
              cfg.task1.green_h_min, cfg.task1.green_h_max,
              cfg.task1.red_h_low_max, cfg.task1.red_h_high_min,
              cfg.task1.lamp_color_s_min, cfg.task1.white_s_max,
              cfg.task1.lamp_on_v_min, cfg.task1.lamp_on_ratio_min,
              cfg.task1.green_bright_core_ratio_min))
    for index, lamp in enumerate(lamps):
        cx, cy = int(lamp["cx"]), int(lamp["cy"])
        radius = int(lamp.get("roi_radius", cfg.task1.roi_radius))
        x0, x1 = max(0, cx - radius), min(w, cx + radius)
        y0, y1 = max(0, cy - radius), min(h, cy + radius)
        roi = hsv[y0:y1, x0:x1]
        if roi.size:
            sat_bright = roi[(roi[..., 1] >= cfg.task1.lamp_color_s_min) &
                             (roi[..., 2] >= cfg.task1.lamp_on_v_min)]
            if sat_bright.size:
                hue_text = "%.1f" % float(np.median(sat_bright[:, 0]))
            else:
                hue_text = "无高饱和亮像素"
            mean_s, mean_v = float(roi[..., 1].mean()), float(roi[..., 2].mean())
        else:
            hue_text, mean_s, mean_v = "ROI越界", 0.0, 0.0
        state = states[index]
        verdict = "亮候选" if state["on"] else "未通过"
        print("灯%d[%s] ROI=(%d,%d,r=%d): score=%.4f color=%.4f bright=%.4f %s[%s] | "
              "S均值=%.1f V均值=%.1f 高S/V像素H中位=%s" % (
            index, state["color"], cx, cy, radius, state["ratio"], state["color_ratio"],
            state["bright_ratio"], verdict, state["criterion"], mean_s, mean_v, hue_text))
        color = (0, 255, 0) if verdict == "亮候选" else (0, 0, 255)
        cv2.circle(view, (cx, cy), radius, color, 2)
        cv2.putText(view, "#%d %s %.3f" % (index, state["color"], state["ratio"]), (cx - radius, cy - radius - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

    out = PROJECT_ROOT / "runtime" / "debug" / ("task1_lamp_diag_" + time.strftime("%Y%m%d_%H%M%S") + ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", view)[1].tofile(str(out))
    print("标注图片已保存：%s" % out)
    index = detector.detect_lit_index(rgb, lamps)
    print("最终判定：%s" % ("无/不唯一" if index is None else "灯%d" % index))


if __name__ == "__main__":
    main()
