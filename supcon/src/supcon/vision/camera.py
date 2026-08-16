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
        self.lamps = lamps or [{"cx": 200, "cy": 240}, {"cx": 320, "cy": 240},
                               {"cx": 440, "cy": 240}]
        self.lit = lit_index
        self.size = size

    def grab_rgb(self) -> np.ndarray:
        w, h = self.size
        img = np.zeros((h, w, 3), np.uint8)
        for i, l in enumerate(self.lamps):
            cx, cy = int(l["cx"]), int(l["cy"])
            val = 250 if i == self.lit else 90
            cv2.circle(img, (cx, cy), 16, (val, val, val), -1)
            cv2.circle(img, (cx, cy), 16, (255, 255, 255), 2)
            cv2.rectangle(img, (cx - 10, cy + 28), (cx + 10, cy + 40),
                          (120, 120, 120), -1)  # 开关示意
        return img


class OrbbecCamera(Camera):
    """真机 Gemini 335（OrbbecSDK v2 / pyorbbecsdk）。

    未安装 pyorbbecsdk 时构造即报错：pip install pyorbbecsdk
    """

    def __init__(self, width: int | None = None, height: int | None = None):
        try:
            from pyorbbecsdk import Config, OBSensorType, Pipeline
        except ImportError as e:
            raise CameraError(
                "未安装 pyorbbecsdk。真机模式需要：pip install pyorbbecsdk "
                "（版本需与 Python 匹配，见奥比中光官方说明）") from e
        self._pipeline = Pipeline()
        config = Config()
        profiles = self._pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        self._profile = profiles.get_default_video_stream_profile()
        config.enable_stream(self._profile)
        self._pipeline.start(config)
        self.intrinsics = self._read_intrinsics()
        log.info("Gemini 335 彩色流已启动，内参=%s", self.intrinsics)

    def _read_intrinsics(self) -> dict | None:
        try:
            p = self._pipeline.get_camera_param()
            i = p.rgb_intrinsic
            return {"fx": float(i.fx), "fy": float(i.fy),
                    "cx": float(i.cx), "cy": float(i.cy)}
        except Exception as e:
            log.warning("读取内参失败: %s", e)
            return None

    def grab_rgb(self) -> np.ndarray:
        frames = self._pipeline.wait_for_frames(2000)
        if frames is None:
            raise CameraError("取流超时（2s 无帧）")
        cf = frames.get_color_frame()
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

    def close(self) -> None:
        try:
            self._pipeline.stop()
        except Exception:
            pass


def make_camera(cfg_cam, lamps: list | None = None) -> Camera:
    """按配置构造相机。lamps 仅 mock 模式绘制面板灯位时用。"""
    mode = cfg_cam.mode
    if mode == "real":
        return OrbbecCamera(cfg_cam.width or None, cfg_cam.height or None)
    if mode == "mock":
        return MockCamera(lamps=lamps)
    return FileCamera(cfg_cam.color_file, cfg_cam.depth_file)
