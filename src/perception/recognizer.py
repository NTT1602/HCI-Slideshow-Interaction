"""Khối: nhận diện cử chỉ. FeatureWindow -> Hypothesis (nhãn, xác suất, chênh lệch hai lớp đầu, cờ "không phải lệnh").

Hai bản cùng giao diện: RFRecognizer (Random Forest của teammate) và RuleRecognizer (luật hình học, không cần model).
"""
from __future__ import annotations

from ..config import Config
from ..datatypes import COMMANDS, CONFIRM_YES, CONFIRM_NO, NONE_LABEL, FeatureWindow, Hypothesis

RULE_TEMPLATES = {"arm": (0, 0, 0, 0), "next": (1, 1, 0, 0), "previous": (1, 0, 0, 0), "play_pause": (1, 1, 1, 1), "exit_show": (1, 1, 1, 0)}
OTHER_MASS = 0.05


def _to_hypothesis(t_ms: int, probs: dict) -> Hypothesis:
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    label = ranked[0][0]
    margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0)
    return Hypothesis(t_ms, True, label, probs, margin, label if label in COMMANDS else None)


class RFRecognizer:
    # từ teammate: 05_realtime.py / run_gate_realtime.py -> joblib.load, predict_proba, argmax
    def __init__(self, model_path: str):
        import joblib
        self.model = joblib.load(model_path)

    def __call__(self, fw: FeatureWindow) -> Hypothesis:
        if not fw.hand:
            return Hypothesis(fw.t_ms, False, NONE_LABEL)
        proba = self.model.predict_proba([list(fw.vector)])[0]
        return _to_hypothesis(fw.t_ms, {str(c): float(p) for c, p in zip(self.model.classes_, proba)})


class RuleRecognizer:
    def __call__(self, fw: FeatureWindow) -> Hypothesis:
        if not fw.hand:
            return Hypothesis(fw.t_ms, False, NONE_LABEL)
        lik = {}
        for name, tpl in RULE_TEMPLATES.items():
            p = 1.0
            for e, t in zip(fw.ext, tpl):
                p *= e if t else (1.0 - e)
            lik[name] = p
        thumb_ext, thumb_dir = fw.thumb  # ngón cái duỗi? chĩa lên hay xuống? (features.frame_thumb)
        up = thumb_ext * min(1.0, max(0.0, (thumb_dir - 0.5) / 0.3))
        down = thumb_ext * min(1.0, max(0.0, (-thumb_dir - 0.5) / 0.3))
        fist = lik["play_pause"]
        lik["play_pause"] = fist * (1.0 - max(up, down))
        lik[CONFIRM_YES], lik[CONFIRM_NO] = fist * up, fist * down
        lik[NONE_LABEL] = lik.get(NONE_LABEL, 0.0) + OTHER_MASS  # tổ hợp ngón lạ coi là "none"
        z = sum(lik.values())
        return _to_hypothesis(fw.t_ms, {k: v / z for k, v in lik.items()})


def make_recognizer(cfg: Config):
    return RFRecognizer(cfg.model_path) if cfg.recognizer == "rf" else RuleRecognizer()
