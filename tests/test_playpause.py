from dataclasses import replace

from src.config import Config
from src.perception.features import FeatureExtractor
from src.perception.recognizer import RuleRecognizer
from src.pipeline import Pipeline
from tests.helpers import make_hand, session


def accepts(cfg, segs):
    p = Pipeline(cfg)
    decisions = [p.process(o) for o in session(segs)]
    return [d for d in decisions if d.verdict == "ACCEPT"], p


def test_fist_is_recognised_as_play_pause_and_odd_pose_is_not_a_command():
    fx, rec = FeatureExtractor(Config(window_ms=0)), RuleRecognizer()
    from src.datatypes import Observation
    fist = rec(fx(Observation(0, make_hand((0, 0, 0, 0)))))
    other = rec(fx(Observation(33, make_hand((0, 1, 0, 0)))))
    assert fist.label == "play_pause" and fist.command == "play_pause"
    assert other.command is None


def test_arm_then_fist_sends_space_once():
    acc, p = accepts(Config(), [("none", 500, "bg"), ("arm", 700, "arm"), ("play_pause", 1500, "cmd:play_pause"), ("none", 500, "bg")])
    assert len(acc) == 1 and acc[0].command == "play_pause"
    assert [k for _, k in p.dispatcher.sent] == ["space"]


def test_fist_without_arm_does_nothing():  # nắm tay mà chưa kích hoạt thì không được gửi phím (Midas Touch)
    acc, _ = accepts(Config(), [("play_pause", 3000, "bg")])
    assert acc == []


def test_fist_needs_longer_hold_than_other_commands():
    cfg = Config({"play_pause": 700}, hold_ms=400)
    assert accepts(cfg, [("arm", 700, "arm"), ("play_pause", 500, "bg")])[0] == []                 # 0,5 s chưa đủ
    assert len(accepts(cfg, [("arm", 700, "arm"), ("play_pause", 1200, "bg")])[0]) == 1            # giữ đủ 0,7 s
    assert len(accepts(cfg, [("arm", 700, "arm"), ("next", 700, "bg")])[0]) == 1             # next vẫn chỉ cần 0,4 s
