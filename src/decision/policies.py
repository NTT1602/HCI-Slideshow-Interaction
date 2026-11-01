"""Policy cắm rời: hàm thuần (cfg, ctx) -> Gating. Intent Gate gọi hàm này mỗi khung.

naive: không Intent Gate (mốc so sánh) | fixed: ngưỡng + thời gian giữ cố định (tương đương GestureGate của teammate
nhưng có bước ARM) | adaptive: khắt khe hơn khi tay chuyển động nhanh | abstain: nhập nhằng thì UNCERTAIN | combined.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Config


@dataclass(frozen=True)
class Context:
    t_ms: int
    speed: float


@dataclass(frozen=True)
class Gating:
    min_conf: float
    min_margin: float
    hold_ms: int
    require_arm: bool
    abstain: bool


def _adapt(cfg: Config, ctx: Context):
    excess = max(0.0, ctx.speed - cfg.speed_floor)
    conf = min(0.97, cfg.conf + min(cfg.max_boost, cfg.speed_gain * excess))
    return conf, int(cfg.hold_ms * (1.0 + cfg.hold_gain * excess))


def naive(cfg, ctx):
    return Gating(0.5, 0.0, 0, False, False)


def fixed(cfg, ctx):  # từ teammate: GestureGate.threshold, hold_frames (đổi sang ms)
    return Gating(cfg.conf, 0.0, cfg.hold_ms, True, False)


def adaptive(cfg, ctx):
    conf, hold = _adapt(cfg, ctx)
    return Gating(conf, 0.0, hold, True, False)


def abstain(cfg, ctx):
    return Gating(cfg.conf, cfg.margin, cfg.hold_ms, True, True)


def combined(cfg, ctx):
    conf, hold = _adapt(cfg, ctx)
    return Gating(conf, cfg.margin, hold, True, True)


REGISTRY = {"naive": naive, "fixed": fixed, "adaptive": adaptive, "abstain": abstain, "combined": combined}


def get_policy(name: str):
    return REGISTRY[name]
