"""Khối: nhận diện cử chỉ. FeatureWindow -> Hypothesis (nhãn, xác suất, chênh lệch hai lớp đầu, cờ "không phải lệnh").

Hai bản cùng giao diện: RFRecognizer (Random Forest của teammate) và RuleRecognizer (luật hình học, không cần model).
"""
from __future__ import annotations

from ..config import Config
from ..datatypes import COMMANDS, CONFIRM_NO, CONFIRM_YES, NONE_LABEL, FeatureWindow, Hypothesis

# Bảng mẫu cử chỉ (luật hình học). Mỗi mẫu: (trỏ, giữa, nhẫn, út) hoặc (trỏ, giữa, nhẫn, út, ngón_cái)
#   4 ngón:     1 = duỗi, 0 = co
#   ngón cái:   0 = co (gập vào) | 1 = duỗi chĩa LÊN | -1 = duỗi chĩa XUỐNG | 2 = duỗi hướng bất kỳ | bỏ trống (4 số) = không quan tâm

RULE_TEMPLATES = {
    "arm":        (0, 0, 0, 0, 0),        # nắm tay
    "next":       (1, 1, 0, 0),        # trỏ + giữa
    "previous":   (1, 0, 0, 0),        # trỏ
    "play_pause": (1, 1, 1, 1),        # mở bàn tay
    "exit_show":  (1, 1, 1, 0),        # 3 ngón (cần xác nhận)
    "like":       (0, 0, 0, 0, 1),     # nắm tay + ngón cái lên   (đồng ý)
    "dislike":    (0, 0, 0, 0, -1),    # nắm tay + ngón cái xuống (hủy)
}
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
        t_ext, t_dir = fw.thumb 
        thumb = {
            0: 1.0 - t_ext,
            1: t_ext * min(1.0, max(0.0, (t_dir - 0.5) / 0.3)),
            -1: t_ext * min(1.0, max(0.0, (-t_dir - 0.5) / 0.3)),
            2: t_ext,
        }
        lik = {}
        for name, tpl in RULE_TEMPLATES.items():
            p = 1.0
            for e, t in zip(fw.ext, tpl[:4]):
                p *= e if t else (1.0 - e)
            if len(tpl) > 4:
                p *= thumb[tpl[4]]
            else:  
                sib = [thumb[o[4]] for o in RULE_TEMPLATES.values() if len(o) > 4 and o[:4] == tpl[:4]]
                if sib:
                    p *= 1.0 - max(sib)
            lik[name] = p
        lik[NONE_LABEL] = lik.get(NONE_LABEL, 0.0) + OTHER_MASS  # tổ hợp ngón lạ coi là none
        z = sum(lik.values())
        return _to_hypothesis(fw.t_ms, {k: v / z for k, v in lik.items()})


def make_recognizer(cfg: Config):
    if cfg.recognizer == "rf":
        return RFRecognizer(cfg.model_path)
    # if cfg.recognizer in ("external", "hybrid"):
    #     from .external_recognizer import ExternalRecognizer, HybridRecognizer  # nhập muộn: chỉ cần khi dùng model ngoài
    #     return HybridRecognizer(cfg) if cfg.recognizer == "hybrid" else ExternalRecognizer(cfg)
    return RuleRecognizer()
