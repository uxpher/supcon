#!/usr/bin/env python3
"""步骤3：面板灯位标定（写入 config.yaml 的 task1.panel.lamps）。

先抓一张面板图保存到 config/runtime/panel_capture.png，再标 3 盏灯中心：
  python scripts/03_calibrate_panel.py --mode manual   # 图片窗口鼠标点击 3 盏灯（左→右）
  python scripts/03_calibrate_panel.py --mode auto     # 自动找全图最亮的 3 个光斑（仅深色背景）
  python scripts/03_calibrate_panel.py --mode diff --origin origin.png --lit lit_dir
                                                       # 白底面板做差标定（推荐现场用）

提示：
- manual 模式：弹出窗口后按左→右顺序点击 3 盏灯中心，点满 3 个或按 q/ESC 结束；
- diff 模式：白底面板下 auto 会失效，可用「全灭基准帧 + 若干亮灯帧」做差定位；
  直接 HSV 阈值运行模式不使用亮度基线，要求所有帧同视角同分辨率、锁定曝光仅用于做差定位；
- 标完灯位后，用 scripts/02_record_pose.py 示教每个开关的动作位姿；
- 相机模式由 config.yaml 的 camera.mode 决定（file=读图 / real=真机拍照）。
"""
import argparse
import pathlib
import sys

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import PROJECT_ROOT, load_config, write_task_value
from supcon.utils import setup_logging
from supcon.vision.camera import make_camera
from supcon.vision.lamp import LampDetector

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def imread_rgb(p) -> np.ndarray:
    """读图为 RGB（np.fromfile + imdecode，支持中文路径）。"""
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"无法读取图片（可能损坏/格式不支持）: {p}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _collect_images(spec) -> list[pathlib.Path]:
    """把 --lit 参数（目录或逗号分隔的文件）展开成图片路径列表。"""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        p = pathlib.Path(part)
        if p.is_dir():
            out += sorted(f for f in p.iterdir() if f.suffix.lower() in _IMAGE_EXTS)
        elif p.is_file():
            out.append(p)
        else:
            raise IOError(f"找不到图片或目录: {p}")
    return out


def _align_to(src_rgb, ref_rgb) -> np.ndarray:
    """把 src 对齐到 ref 的坐标系：尺寸一致直接用；否则等比 resize（仅便利，现场应同分辨率）。"""
    if src_rgb.shape[:2] == ref_rgb.shape[:2]:
        return src_rgb
    h, w = ref_rgb.shape[:2]
    return cv2.resize(src_rgb, (w, h), interpolation=cv2.INTER_LINEAR)


def load_or_new_panel(panel: dict | None) -> dict:
    if isinstance(panel, dict):
        return panel
    return {
        "lamps": [],
        "switches": [
            {"id": 0, "type": "button", "approach_pose": None, "press_pose": None},
            {"id": 1, "type": "toggle", "approach_pose": None,
             "flick_start_pose": None, "flick_end_pose": None},
            {"id": 2, "type": "button", "approach_pose": None, "press_pose": None},
        ],
    }


def lamps_from_points(points: list[tuple[float, float]], panel: dict, cfg) -> list[dict]:
    """按左→右更新灯中心，但保留已有的灯→开关映射。"""
    old_lamps = panel.get("lamps") or []
    switch_ids = ([lamp.get("switch_id", index) for index, lamp in enumerate(old_lamps)]
                  if len(old_lamps) == 3 else list(range(3)))
    return [{"id": index, "switch_id": switch_ids[index], "cx": x, "cy": y,
             "roi_radius": cfg.task1.roi_radius}
            for index, (x, y) in enumerate(points)]


def main():
    ap = argparse.ArgumentParser(description="面板灯位标定")
    ap.add_argument("--mode", choices=["auto", "manual", "diff"], default="manual")
    ap.add_argument("--origin", default="", help="diff 模式：全灭基准帧图片路径")
    ap.add_argument("--lit", default="", help="diff 模式：亮灯帧目录或逗号分隔的文件列表")
    ap.add_argument("--save-baseline", action="store_true",
                    help="兼容旧版：保存当前三灯熄灭亮度基线；HSV 直接阈值运行时不使用")
    a = ap.parse_args()

    cfg = load_config()
    setup_logging("INFO", None)
    panel = load_or_new_panel(cfg.task1.panel)

    # diff 模式：白底面板用「全灭基准帧 + 亮灯帧」做差标定，不依赖相机抓帧。
    if a.mode == "diff":
        if not a.origin or not a.lit:
            sys.exit("diff 模式需要 --origin（全灭基准帧）和 --lit（亮灯帧目录/文件）")
        origin = imread_rgb(a.origin)
        lit_rgbs = [_align_to(imread_rgb(p), origin) for p in _collect_images(a.lit)]
        print(f"diff 标定：origin={a.origin} 亮灯帧={len(lit_rgbs)} 张")
        pts = LampDetector.calibrate_by_diff(origin, lit_rgbs, n=3)
        pts = sorted(pts, key=lambda p: p[0])
        panel["lamps"] = lamps_from_points(pts, panel, cfg)
        # origin 即全灭帧；基线仍保存以兼容旧版本，但新版 HSV 判定不读取它。
        panel["baseline_scores"] = LampDetector.scores(origin, panel["lamps"],
                                                       cfg.task1.roi_radius)
        path = write_task_value("task1", "panel", panel)
        print(f"已写入 {path} 的 task1.panel：")
        for l in panel["lamps"]:
            print(f"  灯{l['id']}: ({l['cx']:.0f}, {l['cy']:.0f})")
        print(f"  基线亮度: {[round(s, 1) for s in panel['baseline_scores']]}")
        print("下一步：运行 scripts/02_record_pose.py 示教每个开关的动作位姿。")
        return

    camera = make_camera(cfg.camera)
    rgb = camera.grab_rgb()

    out = PROJECT_ROOT / "config" / "runtime" / "panel_capture.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    print(f"已抓取面板图 → {out}（请人工确认 3 盏灯清晰可见、位置稳定）")

    if a.save_baseline:
        lamps = panel.get("lamps") or []
        if len(lamps) != 3:
            sys.exit("先完成 3 盏灯位置标定，再在三灯均熄灭时执行 --save-baseline")
        panel["baseline_scores"] = LampDetector.scores(rgb, lamps, cfg.task1.roi_radius)
        path = write_task_value("task1", "panel", panel)
        print(f"已写入三灯熄灭亮度基线 → {path}。")
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

    panel["lamps"] = lamps_from_points(pts, panel, cfg)
    path = write_task_value("task1", "panel", panel)

    print(f"已写入 {path} 的 task1.panel：")
    for l in panel["lamps"]:
        print(f"  灯{l['id']}: ({l['cx']:.0f}, {l['cy']:.0f})")
    print("下一步：运行 scripts/02_record_pose.py 示教每个开关的动作位姿。")


if __name__ == "__main__":
    main()
