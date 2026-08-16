#!/usr/bin/env python3
"""步骤3：面板灯位标定（生成 panel.json 的 lamps 部分）。

先抓一张面板图保存到 config/runtime/panel_capture.png，再标 3 盏灯中心：
  python scripts/03_calibrate_panel.py --mode manual   # 图片窗口鼠标点击 3 盏灯（左→右）
  python scripts/03_calibrate_panel.py --mode auto     # 自动找全图最亮的 3 个光斑

提示：
- manual 模式：弹出窗口后按左→右顺序点击 3 盏灯中心，点满 3 个或按 q/ESC 结束；
- 标完灯位后，用 scripts/02_record_pose.py 示教每个开关的动作位姿；
- 相机模式由 config.yaml 的 camera.mode 决定（file=读图 / real=真机拍照）。
"""
import argparse
import json
import pathlib
import sys

import cv2

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon_task2.config import PROJECT_ROOT, load_config
from supcon_task2.utils import setup_logging
from supcon_task2.vision.camera import make_camera
from supcon_task2.vision.lamp import LampDetector


def load_or_new_panel(path: str) -> dict:
    if pathlib.Path(path).exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "lamps": [],
        "switches": [
            {"id": 0, "type": "button", "approach_pose": None, "press_pose": None},
            {"id": 1, "type": "button", "approach_pose": None, "press_pose": None},
            {"id": 2, "type": "toggle", "approach_pose": None,
             "flick_start_pose": None, "flick_end_pose": None},
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="面板灯位标定")
    ap.add_argument("--mode", choices=["auto", "manual"], default="manual")
    ap.add_argument("--save-baseline", action="store_true",
                    help="将当前三灯均熄灭画面写为亮度基线；必须先已有 lamps 标定")
    a = ap.parse_args()

    cfg = load_config()
    setup_logging("INFO", None)
    camera = make_camera(cfg.camera)
    rgb = camera.grab_rgb()

    out = PROJECT_ROOT / "config" / "runtime" / "panel_capture.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    print(f"已抓取面板图 → {out}（请人工确认 3 盏灯清晰可见、位置稳定）")

    panel = load_or_new_panel(cfg.resolve(cfg.task1.panel_file))
    if a.save_baseline:
        lamps = panel.get("lamps") or []
        if len(lamps) != 3:
            sys.exit("先完成 3 盏灯位置标定，再在三灯均熄灭时执行 --save-baseline")
        panel["baseline_scores"] = LampDetector.scores(rgb, lamps, cfg.task1.roi_radius)
        with open(cfg.resolve(cfg.task1.panel_file), "w", encoding="utf-8") as f:
            json.dump(panel, f, ensure_ascii=False, indent=2)
        print("已写入三灯熄灭亮度基线。")
        return

    pts = []
    if a.mode == "auto":
        pts = LampDetector.find_bright_blobs(rgb, n=3)
        print("自动检测光斑:", [(round(x, 1), round(y, 1)) for x, y in pts])
    else:
        view = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        win = "点击3盏灯中心(左->右)，q/ESC 结束"
        cv2.imshow(win, view)

        def on_click(e, x, y, flags, param):
            if e == cv2.EVENT_LBUTTONDOWN:
                pts.append((float(x), float(y)))
                print(f"已点第 {len(pts)} 盏灯: ({x}, {y})")

        cv2.setMouseCallback(win, on_click)
        while True:
            k = cv2.waitKey(20) & 0xFF
            if k in (ord("q"), 27) or len(pts) >= 3:
                break
        cv2.destroyAllWindows()

    if len(pts) < 3:
        sys.exit("灯位不足 3 个，请重试")
    pts = sorted(pts, key=lambda p: p[0])  # 按 x 排序 = 面板左→右

    panel["lamps"] = [{"id": i, "switch_id": i, "cx": x, "cy": y, "roi_radius": cfg.task1.roi_radius}
                      for i, (x, y) in enumerate(pts)]
    with open(cfg.resolve(cfg.task1.panel_file), "w", encoding="utf-8") as f:
        json.dump(panel, f, ensure_ascii=False, indent=2)

    print(f"已写入 {cfg.task1.panel_file}：")
    for l in panel["lamps"]:
        print(f"  灯{l['id']}: ({l['cx']:.0f}, {l['cy']:.0f})")
    print("下一步：运行 scripts/02_record_pose.py 示教每个开关的动作位姿。")


if __name__ == "__main__":
    main()
