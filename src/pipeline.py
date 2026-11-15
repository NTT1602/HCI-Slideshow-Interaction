"""Nơi DUY NHẤT nối các khối thành chuỗi thẳng. Live và replay dùng chung lớp này; chỉ khác nguồn Observation.

Observation -> features -> recognizer -> gate -> dispatcher -> overlay -> logger
"""
from __future__ import annotations

import time

from .actions.action_dispatcher import ActionDispatcher
from .config import Config
from .decision.gate import IntentGate
from .perception.features import FeatureExtractor
from .perception.recognizer import make_recognizer
from .datatypes import ACCEPT, COOLDOWN, Decision, Observation
from .ui.overlay_ui import OverlayUI


class Pipeline:
    def __init__(self, cfg: Config, recognizer=None, dispatcher=None, overlay=None, logger=None):
        self.cfg = cfg
        self.features = FeatureExtractor(cfg)
        self.recognizer = recognizer or make_recognizer(cfg)
        self.gate = IntentGate(cfg)
        self.dispatcher = dispatcher or ActionDispatcher(cfg)
        self.overlay = overlay or OverlayUI()
        self.logger = logger
        self.last_ms = 0.0  # độ trễ xử lý khung gần nhất (đo thay cho clock.py)

    def process(self, obs: Observation) -> Decision:
        t0 = time.perf_counter()
        fw = self.features(obs)
        hyp = self.recognizer(fw)
        dec = self.gate(fw, hyp)
        if (dec.verdict == ACCEPT or dec.state == COOLDOWN) and hasattr(self.recognizer, "reset"):
            # Recognizer có bộ nhớ chuỗi (GRU): bỏ mọi chuyển động trong lúc cooldown, nếu không phần đuôi
            # của chính cú vuốt vừa thực hiện sẽ bị nhận lại thành lệnh thứ hai khi hết cooldown.
            self.recognizer.reset()
        dec = self.dispatcher(dec)
        dec = self.overlay(dec)
        if self.logger:
            self.logger(obs, dec)
        self.last_ms = (time.perf_counter() - t0) * 1000.0
        return dec
