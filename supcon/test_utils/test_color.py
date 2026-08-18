#!/usr/bin/env python3
"""灯颜色识别测试（白底面板版）。

两件事：
  1) 合成自测：白底 + 3 盏灯位置**不等距**，验证做差标定/判定逻辑正确；
  2) 真实图片：用 origin.png（全灭基准）与各亮灯帧做差，报告判定结果。

用法：
    python test_utils/test_color.py
    python test_utils/test_color.py --skip-synthetic   # 只看真实图片

关键前提（现场必须满足）：所有帧同视角、同分辨率、锁定曝光/白平衡，
否则做差会残留大量背景噪声。本目录当前测试图为手持/不同缩放拍摄，仅作
逻辑演示；真实效果请以固定相机拍摄的帧为准。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import cv2
import numpy as np

from supcon.config import load_config
from supcon.vision.lamp import LampDetector

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}
COLOR_DIR = pathlib.Path(__file__).parent / "color"
POS_CN = {0: "左", 1: "中", 2: "右"}


def imread_rgb(p):
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"无法读取图片（可能损坏/格式不支持）: {p.name}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _gray(rgb):
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY) if rgb.ndim == 3 else rgb


def align_to(ref_rgb, src_rgb):
    """把 src 对齐到 ref 坐标系：优先 ORB 单应变换，特征不足/失败退回 resize。"""
    if src_rgb.shape[:2] == ref_rgb.shape[:2]:
        return src_rgb
    rg, sg = _gray(ref_rgb), _gray(src_rgb)
    h, w = ref_rgb.shape[:2]
    orb = cv2.ORB_create(5000)
    kp1, d1 = orb.detectAndCompute(sg, None)
    kp2, d2 = orb.detectAndCompute(rg, None)
    if kp1 and kp2 and d1 is not None and d2 is not None and len(kp1) >= 8 and len(kp2) >= 8:
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        ms = sorted(bf.match(d1, d2), key=lambda m: m.distance)
        if len(ms) >= 8:
            s = np.float32([kp1[m.queryIdx].pt for m in ms[:200]]).reshape(-1, 1, 2)
            d = np.float32([kp2[m.trainIdx].pt for m in ms[:200]]).reshape(-1, 1, 2)
            H, mask = cv2.findHomography(s, d, cv2.RANSAC, 5.0)
            if H is not None and mask is not None and int(mask.sum()) >= 8:
                return cv2.warpPerspective(src_rgb, H, (w, h))
    return cv2.resize(src_rgb, (w, h), interpolation=cv2.INTER_LINEAR)


def _draw_lamp(img, cx, cy, lit):
    r = 14
    val = 250 if lit else 90
    cv2.circle(img, (int(cx), int(cy)), r, (val, val, val), -1)
    cv2.circle(img, (int(cx), int(cy)), r, (200, 200, 200), 2)


def synthetic_self_test(detector):
    """白底 + 不等距灯位：验证 calibrate_by_diff 与 detect_lit_index_by_diff。"""
    print("=== 合成自测（白底、3 灯不等距） ===")
    h, w = 500, 700
    # 刻意不等距：中间灯偏左，验证不依赖 x/4、x/2、3x/4 假设。
    true_lamps = [(130.0, 200.0), (360.0, 215.0), (560.0, 195.0)]
    rng = np.random.default_rng(0)

    def panel(lit_idx):
        img = np.full((h, w, 3), 240, np.uint8)  # 白底
        noise = rng.normal(0, 2.0, img.shape)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        for i, (x, y) in enumerate(true_lamps):
            _draw_lamp(img, x, y, lit=(i == lit_idx))
        return img

    origin = panel(None)
    lit_frames = [panel(0), panel(1), panel(2)]

    pts = LampDetector.calibrate_by_diff(origin, lit_frames, n=3)
    lamps = [{"cx": x, "cy": y} for x, y in pts]
    print("  标定灯位:", [(round(x, 1), round(y, 1)) for x, y in pts])
    print("  真值灯位:", [(x, y) for x, y in true_lamps])
    err = max(np.hypot(p[0] - t[0], p[1] - t[1]) for p, t in zip(pts, true_lamps))
    print(f"  标定最大误差: {err:.1f} px  {'[OK]' if err < 5 else '[FAIL] 偏差过大'}")

    ok = True
    for truth, name in [(0, "左灯亮"), (1, "中灯亮"), (2, "右灯亮")]:
        idx = detector.detect_lit_index_by_diff(panel(truth), origin, lamps)
        mark = "[OK]" if idx == truth else "[FAIL]"
        ok = ok and idx == truth
        print(f"  {name}: 判定=#{idx}（期望 #{truth}） {mark}")
    print(f"  合成自测: {'通过' if ok else '失败'}\n")
    return ok


def real_image_test(detector, cfg):
    print("=== 真实图片（origin.png 做差） ===")
    origin_p = COLOR_DIR / "origin.png"
    if not origin_p.exists():
        print(f"  未找到 {origin_p}，跳过（请提供全灭基准帧 origin.png）")
        return
    origin = imread_rgb(origin_p)
    files = sorted(p for p in COLOR_DIR.iterdir()
                   if p.suffix.lower() in IMAGE_EXTS and p.name != "origin.png")
    if not files:
        print("  color 目录没有亮灯帧")
        return
    imgs = {p.name: imread_rgb(p) for p in files}
    print("  各图尺寸(H×W): origin =", f"{origin.shape[0]}x{origin.shape[1]}",
          "|", ", ".join(f"{n}={a.shape[0]}x{a.shape[1]}" for n, a in sorted(imgs.items())))
    aligned = {n: align_to(origin, a) for n, a in imgs.items()}
    try:
        pts = LampDetector.calibrate_by_diff(origin, list(aligned.values()), n=3)
    except RuntimeError as e:
        print(f"  做差标定失败: {e}")
        print("  （提示：当前测试图分辨率/视角不一致，无法像素对齐；现场需固定相机）")
        return
    lamps = [{"cx": x, "cy": y} for x, y in pts]
    print("  标定灯位(左→右):", [(round(x, 1), round(y, 1)) for x, y in pts])
    baseline = LampDetector.scores(origin, lamps, cfg.task1.roi_radius)
    print("  基线亮度:", [round(s, 1) for s in baseline])
    for name in sorted(aligned):
        live = aligned[name]
        roi = LampDetector.scores(live, lamps, cfg.task1.roi_radius)
        delta = [round(r - b, 1) for r, b in zip(roi, baseline)]
        # 判定与运行时 task1 完全一致：ROI 亮度 − 全灭基线，取增量最大者（算差值比大小）
        idx = detector.detect_lit_index(live, lamps, baseline=baseline)
        lit = "无/不明确" if idx is None else f"#{idx}（{POS_CN.get(idx, idx)}灯）"
        print(f"  {name}: 判定={lit} | ROI亮度={[round(s, 1) for s in roi]} | 增量={delta}")
    print("  注意：增量未超 lamp_abs_min/margin 时如实报「无/不明确」，不做强猜；"
          "现场固定相机、同分辨率时增量才显著。")


def main():
    cfg = load_config()
    detector = LampDetector(cfg.task1)
    skip = "--skip-synthetic" in sys.argv
    if not skip:
        synthetic_self_test(detector)
    real_image_test(detector, cfg)


if __name__ == "__main__":
    main()
