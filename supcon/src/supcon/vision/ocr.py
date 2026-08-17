"""PaddleOCR 封装（CPU 版本）。

用途：
- Task2：识别顶面数字 1-4
- Task3：识别槽位/工位外侧汉字标签（如「三棱柱」「圆柱」等）

安装（CPU 版）：
    pip install paddlepaddle
    pip install paddleocr

注意：
- PaddleOCR 首次运行会联网下载模型权重；可预置模型目录后离线使用。
- 本模块为「延迟初始化 + 优雅降级」：未安装或初始化失败时不抛错，
  由调用方 fallback 到模板匹配（Task2）或轮廓分类（Task3）。
"""
from __future__ import annotations

import logging

log = logging.getLogger("ocr")

# 汉字标签 → 内部形状 key（Task3 用，兼容常见写法；现场确认标签后可按需增补）
LABEL_TO_SHAPE = {
    "长方体": "block",
    "四棱柱": "block",
    "正六棱柱": "hexagonal_prism",
    "六棱柱": "hexagonal_prism",
    "三棱柱": "triangular_prism",
    "三角柱": "triangular_prism",
    "圆柱体": "cylinder",
    "圆柱": "cylinder",
}

# 汉字数字（标签可写「三」而非「3」）
DIGIT_CN = {"一": 1, "二": 2, "三": 3, "四": 4}


class OcrRecognizer:
    """PaddleOCR 封装。延迟初始化；未安装/初始化失败时 available=False。"""

    def __init__(self, lang: str = "ch"):
        self._ocr = None
        self._lang = lang
        self._init_error: str | None = None

    @property
    def available(self) -> bool:
        """懒加载：首次访问才真正初始化 PaddleOCR。"""
        if self._ocr is None and self._init_error is None:
            self._load()
        return self._ocr is not None

    def _load(self) -> None:
        try:
            from paddleocr import PaddleOCR
            try:
                self._ocr = PaddleOCR(use_angle_cls=True, lang=self._lang, show_log=False)
            except TypeError:
                self._ocr = PaddleOCR(lang=self._lang)
            log.info("PaddleOCR 初始化完成（lang=%s）", self._lang)
        except Exception as e:  # noqa: BLE001
            self._init_error = str(e)
            log.warning("PaddleOCR 不可用，将 fallback 到传统算法: %s", e)

    def recognize(self, image) -> list[tuple[str, float]]:
        """返回 [(text, confidence), ...]，按置信度降序；失败返回空列表。"""
        if not self.available:
            return []
        try:
            result = self._ocr.ocr(image, cls=True)
        except TypeError:
            result = self._ocr.ocr(image)
        except Exception as e:  # noqa: BLE001
            log.warning("OCR 识别失败: %s", e)
            return []
        items: list[tuple[str, float]] = []
        if not result:
            return items
        for page in result:
            if not page:
                continue
            for line in page:
                if len(line) < 2:
                    continue
                text, score = line[1][0], float(line[1][1])
                items.append((text, score))
        items.sort(key=lambda x: x[1], reverse=True)
        return items

    def recognize_digit(self, image) -> tuple[int, float] | None:
        """识别单个数字 1-4（Task2）。返回 (digit, score) 或 None。"""
        for text, conf in self.recognize(image):
            for ch in text:
                if ch.isdigit() and 1 <= int(ch) <= 4:
                    return int(ch), conf
            for ch, d in DIGIT_CN.items():
                if ch in text:
                    return d, conf
        return None

    def recognize_shape_label(self, image) -> tuple[str, float] | None:
        """识别汉字形状标签（Task3）。返回 (shape_key, score) 或 None。"""
        for text, conf in self.recognize(image):
            for label, shape in LABEL_TO_SHAPE.items():
                if label in text:
                    return shape, conf
        return None
