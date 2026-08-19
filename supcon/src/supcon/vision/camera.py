"""相机抽象：真机 Orbbec / 本地图片 / 模拟面板图。

统一接口：
    grab_rgb()  -> HxWx3 uint8（RGB 顺序）
    grab_depth() -> HxW float32（米）或 None
    close()
"""
from __future__ import annotations

import glob
import logging
import os
import time
from abc import ABC, abstractmethod

import cv2
import numpy as np

log = logging.getLogger("camera")

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


class CameraError(RuntimeError):
    pass


class Camera(ABC):
    @abstractmethod
    def grab_rgb(self) -> np.ndarray:
        ...

    def grab_depth(self) -> np.ndarray | None:
        return None

    def grab_rgbd(self) -> tuple[np.ndarray, np.ndarray | None]:
        """同一观察时刻的 RGB 与深度。

        Task3 必须使用该接口，避免分别调用 ``grab_rgb`` / ``grab_depth``
        取得不同帧而造成像素与深度不对应。
        """
        return self.grab_rgb(), self.grab_depth()

    def close(self) -> None:
        pass


class FileCamera(Camera):
    """读本地图片（开发用）。color_file 可为单张图片路径或目录（取最新一张）。"""

    def __init__(self, color_file: str, depth_file: str = ""):
        self.color_file = color_file
        self.depth_file = depth_file

    @staticmethod
    def _pick(path: str) -> str:
        if os.path.isdir(path):
            files = [os.path.join(path, f) for f in os.listdir(path)
                     if os.path.splitext(f)[1].lower() in _IMAGE_EXTS]
            if not files:
                raise CameraError(f"目录里没有图片: {path}")
            return max(files, key=os.path.getmtime)
        return path

    def grab_rgb(self) -> np.ndarray:
        p = self._pick(self.color_file)
        img = cv2.imread(p, cv2.IMREAD_COLOR)
        if img is None:
            raise CameraError(f"无法读取图片: {p}")
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def grab_depth(self) -> np.ndarray | None:
        if not self.depth_file:
            return None
        p = self._pick(self.depth_file)
        img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        return img.astype(np.float32) / 1000.0  # 假设 mm


class MockCamera(Camera):
    """合成面板图：3 盏灯（一盏亮）+ 开关示意。离线联调用。"""

    def __init__(self, lamps: list | None = None, lit_index: int | None = 0,
                 size: tuple = (640, 480)):
        self.lamps = lamps or [{"cx": 200, "cy": 240, "color": "green"},
                               {"cx": 320, "cy": 240, "color": "white"},
                               {"cx": 440, "cy": 240, "color": "red"}]
        self.lit = lit_index
        self.size = size

    def grab_rgb(self) -> np.ndarray:
        w, h = self.size
        img = np.zeros((h, w, 3), np.uint8)
        for i, l in enumerate(self.lamps):
            cx, cy = int(l["cx"]), int(l["cy"])
            # 亮灯颜色与每个灯的标称色一致；红灯过曝时真实相机可能偏橙黄，
            # 这里仍用红色验证色相双区间逻辑。
            lit_colors = {"green": (0, 255, 0), "white": (255, 255, 255), "red": (255, 0, 0)}
            color = lit_colors.get(str(l.get("color", "green")).lower(), (0, 255, 0)) if i == self.lit else (90, 90, 90)
            cv2.circle(img, (cx, cy), 16, color, -1)
            cv2.circle(img, (cx, cy), 16, (255, 255, 255), 2)
            cv2.rectangle(img, (cx - 10, cy + 28), (cx + 10, cy + 40),
                          (120, 120, 120), -1)  # 开关示意
        return img


class OrbbecCamera(Camera):
    """真机 Gemini 335（OrbbecSDK v2 / pyorbbecsdk2，import 名 pyorbbecsdk）。

    未安装时构造即报错：pip install pyorbbecsdk2（不是 PyPI 的 pyorbbecsdk 1.x 旧包）
    """

    def __init__(self, width: int | None = None, height: int | None = None,
                 align_depth_to_color: bool = True):
        try:
            from pyorbbecsdk import Config, OBSensorType, Pipeline, OBAlignMode
        except ImportError as e:
            raise CameraError(
                "未安装 pyorbbecsdk2（OrbbecSDK v2）。真机模式需要：pip install pyorbbecsdk2 "
                "（版本需与 Python 匹配，见奥比中光官方说明）") from e

        self._has_depth = False
        self._depth_aligned = False

        def build(align_mode):
            """构造并启动一个 pipeline；返回 (pipeline, has_depth)。失败抛异常。"""
            pipeline = Pipeline()
            config = Config()
            color_profiles = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
            config.enable_stream(color_profiles.get_default_video_stream_profile())
            has_depth = False
            try:
                depth_profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
                config.enable_stream(depth_profiles.get_default_video_stream_profile())
                has_depth = True
            except Exception as e:
                log.warning("深度流启动失败（将无深度数据）: %s", e)
            if align_mode is not None:
                config.set_align_mode(align_mode)
            pipeline.start(config)
            return pipeline, has_depth

        # Gemini335 默认 profile 常不支持硬件 D2C：依次尝试 HW → SW → 不对齐。
        candidates: list[tuple] = []
        if align_depth_to_color:
            candidates = [(OBAlignMode.HW_MODE, True), (OBAlignMode.SW_MODE, True)]
        candidates.append((None, False))
        last_err = None
        for mode, aligned in candidates:
            try:
                self._pipeline, self._has_depth = build(mode)
                self._depth_aligned = bool(aligned and self._has_depth)
                log.info("相机流启动完成：对齐=%s 深度流=%s",
                         ("HW/SW" if aligned else "无"), self._has_depth)
                break
            except Exception as e:
                last_err = e
                log.warning("对齐方式 %s 启动失败: %s", mode, e)
        else:
            raise CameraError(f"相机启动失败: {last_err}")

        self.intrinsics = self._read_intrinsics()
        log.info("Gemini 335 内参=%s", self.intrinsics)

    def _read_intrinsics(self) -> dict | None:
        try:
            p = self._pipeline.get_camera_param()
            i = p.rgb_intrinsic
            return {"fx": float(i.fx), "fy": float(i.fy),
                    "cx": float(i.cx), "cy": float(i.cy)}
        except Exception as e:
            log.warning("读取内参失败: %s", e)
            return None

    @staticmethod
    def _decode_rgb(cf) -> np.ndarray:
        if cf is None:
            raise CameraError("无彩色帧")
        w, h = cf.get_width(), cf.get_height()
        arr = np.frombuffer(cf.get_data(), dtype=np.uint8)
        fmt = str(cf.get_format()).upper()
        # pyorbbecsdk 的具体枚举值因 SDK 版本不同略有差异，按名称兼容常见格式。
        if "MJPG" in fmt or "JPEG" in fmt:
            image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if image is None:
                raise CameraError(f"无法解码 JPEG 彩色帧，format={fmt}")
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if "YUYV" in fmt or "YUY2" in fmt:
            if arr.size < w * h * 2:
                raise CameraError(f"YUYV 彩色帧长度异常: {arr.size}")
            return cv2.cvtColor(arr[:w * h * 2].reshape((h, w, 2)), cv2.COLOR_YUV2RGB_YUY2)
        if arr.size < w * h * 3:
            raise CameraError(f"彩色帧数据长度异常: {arr.size}，format={fmt}")
        image = arr[:w * h * 3].reshape((h, w, 3))
        if "BGR" in fmt:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if "RGB" not in fmt:
            log.warning("未识别的彩色像素格式 %s，按 RGB 解释；须现场核对", fmt)
        return image

    @staticmethod
    def _decode_depth(df) -> np.ndarray | None:
        if df is None:
            return None
        w, h = df.get_width(), df.get_height()
        raw = np.frombuffer(df.get_data(), dtype=np.uint16)
        if raw.size < w * h:
            raise CameraError(f"深度帧长度异常: {raw.size} < {w * h}")
        raw = raw[:w * h].reshape((h, w)).astype(np.float32)
        # Orbbec SDK 的 value_scale 定义为：Y16 原始值 × scale = mm。
        # 个别 Python 包版本只暴露 get_depth_scale（通常为 m/计数），故兼容两者。
        if hasattr(df, "get_value_scale"):
            depth_m = raw * float(df.get_value_scale()) / 1000.0
        elif hasattr(df, "get_depth_scale"):
            depth_m = raw * float(df.get_depth_scale())
        else:
            log.warning("深度帧未提供 scale，按默认 1mm/计数解释")
            depth_m = raw / 1000.0
        depth_m[depth_m <= 0] = 0.0
        return depth_m

    def grab_rgbd(self) -> tuple[np.ndarray, np.ndarray | None]:
        """从同一 FrameSet 解码 RGB 和 Y16 深度（深度单位统一为米）。

        彩色流（1280x720）常比深度流（848x480）晚到：轮询等待彩色帧就绪。
        当前分类走 RGB、深度仅用于可视化，分辨率不一致时只告警不报错。
        """
        frames = None
        for _ in range(20):
            frames = self._pipeline.wait_for_frames(2000)
            if frames is not None and frames.get_color_frame() is not None:
                break
            time.sleep(0.1)
        if frames is None:
            raise CameraError("取流超时（2s 无帧）")
        rgb = self._decode_rgb(frames.get_color_frame())
        depth = self._decode_depth(frames.get_depth_frame()) if self._has_depth else None
        if depth is not None and depth.shape != rgb.shape[:2]:
            log.warning(
                "RGB/深度分辨率不一致：RGB=%s depth=%s（深度未对齐）。"
                "当前分类走 RGB、深度仅用于可视化，不影响执行。",
                rgb.shape[:2], depth.shape)
        return rgb, depth

    def grab_rgb(self) -> np.ndarray:
        return self.grab_rgbd()[0]

    def grab_depth(self) -> np.ndarray | None:
        """深度图（float32，米）。深度流未启动时返回 None。"""
        return self.grab_rgbd()[1]

    def close(self) -> None:
        try:
            self._pipeline.stop()
        except Exception:
            pass


def make_camera(cfg_cam, lamps: list | None = None) -> Camera:
    """按配置构造相机。lamps 仅 mock 模式绘制面板灯位时用。"""
    mode = cfg_cam.mode
    if mode == "real":
        return OrbbecCamera(cfg_cam.width or None, cfg_cam.height or None,
                            getattr(cfg_cam, "align_depth_to_color", True))
    if mode == "mock":
        return MockCamera(lamps=lamps)
    return FileCamera(cfg_cam.color_file, cfg_cam.depth_file)
