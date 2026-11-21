"""Khối: nhận diện cử chỉ. FeatureWindow -> Hypothesis (nhãn, xác suất, chênh lệch hai lớp đầu, cờ "không phải lệnh").

RuleRecognizer (luật hình học) nhận tư thế tĩnh; vuốt next/previous do GRU nhận (xem gru_recognizer.py).
"""
from __future__ import annotations

from ..config import Config
from ..datatypes import COMMANDS, NONE_LABEL, POSE_COMMANDS, FeatureWindow, Hypothesis

# Bảng mẫu cử chỉ (luật hình học). Mỗi mẫu: (trỏ, giữa, nhẫn, út) hoặc (trỏ, giữa, nhẫn, út, ngón_cái)
#   4 ngón:     1 = duỗi, 0 = co
#   ngón cái:   0 = co (gập vào) | 1 = duỗi chĩa LÊN | -1 = duỗi chĩa XUỐNG | 2 = duỗi hướng bất kỳ | bỏ trống (4 số) = không quan tâm

RULE_TEMPLATES = {
    "arm":        (0, 0, 0, 0, 0),        # nắm tay
    "play_pause": (1, 1, 0, 0),        # mở bàn tay
    "like":       (0, 0, 0, 0, 1),     # nắm tay + ngón cái lên   -> start_show (vào trình chiếu)
    "dislike":    (0, 0, 0, 0, -1),    # nắm tay + ngón cái xuống -> exit_show (thoát trình chiếu)
}
OTHER_MASS = 0.05


def _to_hypothesis(t_ms: int, probs: dict) -> Hypothesis:
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    label = ranked[0][0]
    margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0)
    command = POSE_COMMANDS.get(label, label)
    return Hypothesis(t_ms, True, label, probs, margin, command if command in COMMANDS else None)


class RuleRecognizer:
    def __init__(self, exclude=()):
        """exclude: bỏ các mẫu này (vd. next/previous khi HybridRecognizer giao chúng cho GRU)."""
        self.templates = {k: v for k, v in RULE_TEMPLATES.items() if k not in set(exclude)}

    def __call__(self, fw: FeatureWindow) -> Hypothesis:
        if not fw.hand:
            return Hypothesis(fw.t_ms, False, NONE_LABEL)
        t_ext, t_dir = fw.thumb 
        thumb = {
            0: 1.0 - t_ext,
            1: t_ext * min(1.0, max(0.0, (t_dir - 0.5) / 0.3)),
            -1: t_ext * min(1.0, max(0.0, (-t_dir - 0.5) / 0.3)),
            2: t_ext,
        }
        lik = {}
        for name, tpl in self.templates.items():
            p = 1.0
            for e, t in zip(fw.ext, tpl[:4]):
                p *= e if t else (1.0 - e)
            if len(tpl) > 4:
                p *= thumb[tpl[4]]
            else:  
                sib = [thumb[o[4]] for o in self.templates.values() if len(o) > 4 and o[:4] == tpl[:4]]
                if sib:
                    p *= 1.0 - max(sib)
            lik[name] = p
        lik[NONE_LABEL] = lik.get(NONE_LABEL, 0.0) + OTHER_MASS  # tổ hợp ngón lạ coi là none
        z = sum(lik.values())
        return _to_hypothesis(fw.t_ms, {k: v / z for k, v in lik.items()})


def make_recognizer(cfg: Config):
    if cfg.recognizer in ("gru", "hybrid"):
        from .gru_recognizer import GRURecognizer, HybridRecognizer  # nhập muộn: chỉ cần TensorFlow khi dùng GRU
        if cfg.recognizer == "hybrid":
            return HybridRecognizer(cfg)
        return GRURecognizer(cfg.gru_model_dir, flip_x=cfg.gru_flip_x, step_ms=cfg.gru_step_ms)
    return RuleRecognizer()
