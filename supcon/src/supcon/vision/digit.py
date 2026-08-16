"""任务 2 顶面数字识别：固定字体模板匹配。

比赛道具只有 1–4，且更新规则规定数字仅在顶面。模板必须用赛场相机、赛场光照采集。
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class DigitError(RuntimeError):
    pass


class DigitRecognizer:
    def __init__(self, template_dir: str, minimum_score: float = 0.72):
        self.minimum_score = minimum_score
        self.templates: dict[int, np.ndarray] = {}
        for digit in range(1, 5):
            p = Path(template_dir) / f"{digit}.png"
            if p.exists():
                image = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    self.templates[digit] = self._binary(image)
        if len(self.templates) != 4:
            raise DigitError("数字模板不完整：需要 template_dir/1.png 至 4.png")

    @staticmethod
    def _binary(image: np.ndarray) -> np.ndarray:
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # 同时兼容深色数字/浅色数字：让稀疏笔画为白色。
        if np.mean(bw > 0) > 0.5:
            bw = 255 - bw
        return bw

    def recognize(self, rgb_crop: np.ndarray) -> tuple[int, float]:
        query = self._binary(rgb_crop)
        best_digit, best_score = None, -1.0
        for digit, templ in self.templates.items():
            resized = cv2.resize(query, (templ.shape[1], templ.shape[0]))
            score = float(cv2.matchTemplate(resized, templ, cv2.TM_CCOEFF_NORMED)[0, 0])
            if score > best_score:
                best_digit, best_score = digit, score
        if best_digit is None or best_score < self.minimum_score:
            raise DigitError(f"顶面数字置信度不足：score={best_score:.3f}")
        return best_digit, best_score
