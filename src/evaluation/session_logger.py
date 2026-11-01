"""Khối: ghi nhật ký. JSONL: dòng đầu là Config, mỗi dòng sau là một khung (obs + decision).
Ghi cả landmark thô để Replay chạy lại được với policy khác. (Thay cho gate._log ghi CSV của teammate.)"""
from __future__ import annotations

import json

from ..config import Config
from ..datatypes import Decision, Observation


class SessionLogger:
    def __init__(self, path: str, cfg: Config):
        self.f = open(path, "w", encoding="utf-8")
        self._w({"type": "header", "config": cfg.to_dict()})

    def _w(self, d: dict):
        self.f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def __call__(self, obs: Observation, dec: Decision) -> None:
        self._w({"type": "frame", "obs": obs.to_dict(), "decision": dec.to_dict()})

    def close(self):
        self.f.close()

