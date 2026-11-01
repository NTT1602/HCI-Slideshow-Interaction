"""Replay: đọc lại Observation từ log, chạy qua Pipeline với policy khác (dry-run), so sánh trên cùng dữ liệu."""
from __future__ import annotations

import json
from dataclasses import replace

from ..actions.action_dispatcher import ActionDispatcher
from ..config import POLICIES, Config
from ..pipeline import Pipeline
from ..datatypes import Observation
from .metrics import evaluate


def load_log(path: str):
    cfg, obs = None, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["type"] == "header":
                cfg = Config.from_dict(d["config"])
            else:
                obs.append(Observation.from_dict(d["obs"]))
    return cfg, obs


def run(observations, cfg: Config):
    cfg = replace(cfg, dry_run=True)  # replay không bao giờ được bấm phím thật
    p = Pipeline(cfg, dispatcher=ActionDispatcher(cfg, quiet=True))
    return [p.process(o) for o in observations]


def compare(observations, base_cfg: Config, policies=POLICIES) -> dict:
    return {name: evaluate(observations, run(observations, base_cfg.with_policy(name))) for name in policies}

