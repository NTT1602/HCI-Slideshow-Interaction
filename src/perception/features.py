from __future__ import annotations

import math
from collections import deque

from ..config import Config
from ..datatypes import FeatureWindow, Observation

FINGERS = ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))  # (MCP, PIP, TIP): trỏ, giữa, nhẫn, út


def _d(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def landmarks_to_vector(lm) -> list:
    wx, wy, wz = lm[0][0], lm[0][1], lm[0][2]
    scale = max(_d(lm[0], lm[9]), 1e-6)
    out = []
    for p in lm:
        out += [(p[0] - wx) / scale, (p[1] - wy) / scale, (p[2] - wz) / scale]
    return out


def frame_ext(lm) -> list:
    """Mức duỗi 4 ngón (0..1), dùng cho RuleRecognizer."""
    w = lm[0]
    ext = []
    for _, pip, tip in FINGERS:
        r = _d(w, lm[tip]) / max(_d(w, lm[pip]), 1e-6)
        ext.append(1.0 / (1.0 + math.exp(-(r - 1.05) / 0.08)))
    return ext

THUMB_MARGIN = 0.9

def frame_thumb(lm):
    seg = _d(lm[2], lm[3]) + _d(lm[3], lm[4])
    length = _d(lm[2], lm[4])
    straight = length / max(seg, 1e-6)
    ext = 1.0 / (1.0 + math.exp(-(straight - THUMB_MARGIN) / 0.04))
    direction = (lm[2][1] - lm[4][1]) / max(length, 1e-6)   # y ảnh hướng xuống: đầu cao hơn khớp gốc => dương
    return ext, direction


class FeatureExtractor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.buf = deque()  # (t_ms, vector, ext, wrist theo đơn vị kích thước tay)

    def __call__(self, obs: Observation) -> FeatureWindow:
        if obs.landmarks is None:
            self.buf.clear()
            return FeatureWindow(obs.t_ms, False)
        lm = obs.landmarks
        scale = max(_d(lm[0], lm[9]), 1e-6)
        self.buf.append((obs.t_ms, landmarks_to_vector(lm), frame_ext(lm), (lm[0][0] / scale, lm[0][1] / scale), frame_thumb(lm)))
        while obs.t_ms - self.buf[0][0] > self.cfg.window_ms:
            self.buf.popleft()
        n = len(self.buf)
        vector = tuple(sum(b[1][i] for b in self.buf) / n for i in range(63))
        ext = tuple(sum(b[2][i] for b in self.buf) / n for i in range(4))
        thumb = (sum(b[4][0] for b in self.buf) / n, sum(b[4][1] for b in self.buf) / n)
        speed = 0.0
        if n >= 2:
            path = sum(_d(self.buf[i][3], self.buf[i - 1][3]) for i in range(1, n))
            span = (self.buf[-1][0] - self.buf[0][0]) / 1000.0
            speed = path / span if span > 0 else 0.0
        return FeatureWindow(obs.t_ms, True, vector, ext, speed, n, thumb, lm)

