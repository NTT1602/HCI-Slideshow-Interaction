"""Test luồng Intent Gate (unit + tích hợp nhẹ). Tự chứa: chỉ cần src/ và numpy, không webcam, không mediapipe, không màn hình."""
import random

from src.config import Config
from src.datatypes import ACCEPT, FeatureWindow, Hypothesis
from src.decision.gate import IntentGate

DT = 33  # ms giữa hai khung (~30 fps)


def fw(t, hand=True):
    return FeatureWindow(t, hand, (), (0, 0, 0, 0), 0.0, 5)


def hyp(t, label, conf=0.95, hand=True):
    cmd = label if label in ("next", "previous", "play_pause") else None
    return Hypothesis(t, hand, label, {label: conf, "none": 1 - conf}, 0.8, cmd)


def run(gate, segments, t0=0):
    """segments = [(nhãn, thời lượng ms)] -> danh sách Decision."""
    out, t = [], t0
    for label, dur in segments:
        for _ in range(max(1, dur // DT)):
            out.append(gate(fw(t, label != "nohand"), hyp(t, label, hand=label != "nohand")))
            t += DT
    return out


def accepted(decs):
    return [d.command for d in decs if d.verdict == ACCEPT]


def test_command_without_arm_is_never_accepted():
    g = IntentGate(Config(policy="fixed"))
    assert accepted(run(g, [("next", 3000)])) == []


def test_arm_then_command_is_accepted_exactly_once():
    g = IntentGate(Config(policy="fixed"))
    decs = run(g, [("arm", 600), ("next", 1000)])
    assert accepted(decs) == ["next"]


def test_low_confidence_command_is_rejected():
    g = IntentGate(Config(policy="fixed"))
    decs = run(g, [("arm", 600)]) + [g(fw(t), hyp(t, "next", conf=0.5)) for t in range(1000, 3000, DT)]
    assert accepted(decs) == []


def test_armed_times_out_back_to_idle_and_needs_release():
    cfg = Config(policy="fixed")
    g = IntentGate(cfg)
    run(g, [("arm", 600)])
    decs = run(g, [("arm", cfg.armed_timeout_ms + 1500)], t0=1000)        # giữ cử chỉ arm quá hạn
    assert decs[-1].state == "IDLE"                                         # phải về IDLE, không kẹt ở ARMED
    assert accepted(run(g, [("next", 1500)], t0=10_000)) == []              # chưa hạ tay: lệnh không được nhận


def test_cooldown_blocks_a_second_command():
    cfg = Config(policy="fixed")
    g = IntentGate(cfg)
    decs = run(g, [("arm", 600), ("next", 600), ("next", cfg.cooldown_ms // 2)])
    assert len(accepted(decs)) == 1


def test_losing_the_hand_rejects():
    g = IntentGate(Config(policy="fixed"))
    run(g, [("arm", 600)])
    assert run(g, [("nohand", 200)], t0=1000)[-1].reason == "no_hand"


def test_naive_policy_has_no_gate():
    """Đường cơ sở (baseline): không có arm vẫn nhận lệnh. Đây chính là lỗi Midas Touch mà Intent Gate khắc phục."""
    g = IntentGate(Config(policy="naive"))
    assert accepted(run(g, [("next", 1000)])) != []


def test_random_stream_never_accepts_without_arm():
    """Invariant: với policy fixed, mọi ACCEPT phải xuất hiện sau ít nhất một khung 'arm' trước đó."""
    rnd = random.Random(1)
    labels = ["arm", "next", "previous", "play_pause", "none", "nohand"]
    for seed in range(30):
        rnd.seed(seed)
        g = IntentGate(Config(policy="fixed"))
        seen_arm, t = False, 0
        for _ in range(400):
            label = rnd.choice(labels)
            d = g(fw(t, label != "nohand"), hyp(t, label, conf=rnd.uniform(0.4, 1.0), hand=label != "nohand"))
            seen_arm = seen_arm or label == "arm"
            assert d.verdict != ACCEPT or seen_arm
            t += DT
