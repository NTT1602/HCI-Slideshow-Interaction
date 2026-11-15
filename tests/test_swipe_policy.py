"""Policy swipe (mặc định): vuốt là chuyển slide, không cần ARM; lệnh trong disabled_commands bị bỏ qua."""
from src.config import Config
from src.datatypes import ACCEPT, FeatureWindow, Hypothesis
from src.decision.gate import IntentGate
from src.decision.policies import Context, get_policy


def hyp(t, label, p=0.95):
    return Hypothesis(t, True, label, {label: p, "none": 1 - p}, 2 * p - 1, label if label != "none" else None)


def run(cfg, labels, dt=33):
    gate, out = IntentGate(cfg), []
    for i, (label, p) in enumerate(labels):
        t = i * dt
        d = gate(FeatureWindow(t, True), hyp(t, label, p))
        if d.verdict == ACCEPT:
            out.append((t, d.command))
    return out


CFG = Config(policy="swipe", swipe_hold_ms=200, cooldown_ms=2000, conf=0.8)


def test_swipe_policy_values():
    g = get_policy("swipe")(CFG, Context(0, 0.0))
    assert (g.min_conf, g.hold_ms, g.require_arm) == (0.8, 200, False)


def test_swipe_without_arm_executes_once_per_cooldown():
    acc = run(CFG, [("next", 0.95)] * 60)  # ~2 s liên tục (cửa sổ GRU còn giữ nhãn sau cú vuốt)
    assert [c for _, c in acc] == ["next"]


def test_low_confidence_swipe_is_rejected():
    assert run(CFG, [("previous", 0.7)] * 30) == []


def test_disabled_command_is_ignored():
    cfg = Config(policy="swipe", swipe_hold_ms=200, disabled_commands=["play_pause"])
    assert run(cfg, [("play_pause", 0.95)] * 30) == []
    assert [c for _, c in run(cfg, [("next", 0.95)] * 30)] == ["next"]


def pose(t, label, p=0.9):
    from src.datatypes import POSE_COMMANDS
    return Hypothesis(t, True, label, {label: p, "none": 1 - p}, 2 * p - 1, POSE_COMMANDS.get(label))


def run_poses(cfg, labels, dt=33):
    gate, out = IntentGate(cfg), []
    for i, label in enumerate(labels):
        d = gate(FeatureWindow(i * dt, True), pose(i * dt, label))
        if d.verdict == ACCEPT:
            out.append(d.command)
    return out


SHOW = Config(policy="swipe", swipe_hold_ms=0, cooldown_ms=800, conf=0.7, command_hold_ms={"start_show": 600, "exit_show": 600})


def test_thumb_up_starts_and_thumb_down_exits():
    assert run_poses(SHOW, ["like"] * 30 + ["none"] * 40 + ["dislike"] * 30) == ["start_show", "exit_show"]


def test_short_thumb_does_nothing():
    assert run_poses(SHOW, ["like"] * 10 + ["none"] * 10 + ["dislike"] * 10) == []


def test_holding_thumb_does_not_repeat():
    assert run_poses(SHOW, ["like"] * 200) == ["start_show"]


def test_rule_recognizer_maps_thumbs_to_show_commands():
    from src.perception.recognizer import RuleRecognizer
    rule = RuleRecognizer()
    up = rule(FeatureWindow(0, True, ext=(0.0, 0.0, 0.0, 0.0), thumb=(1.0, 1.0)))
    down = rule(FeatureWindow(0, True, ext=(0.0, 0.0, 0.0, 0.0), thumb=(1.0, -1.0)))
    assert (up.label, up.command) == ("like", "start_show")
    assert (down.label, down.command) == ("dislike", "exit_show")
