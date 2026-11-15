import json
from pathlib import Path

import numpy as np
import pytest

from src.config import Config
from src.datatypes import FeatureWindow, Observation
from src.perception.features import FeatureExtractor
from src.perception.gru_recognizer import GRURecognizer, HybridRecognizer
from src.perception.recognizer import RuleRecognizer


def make_hand(ext, cx=0.5, cy=0.8, s=0.15):
    """Bàn tay giả 21 landmark, ngón cái gập; ext = duỗi (1) / co (0) cho trỏ, giữa, nhẫn, út.
    (Không dùng tests/helpers.make_hand: hàm đó đang lỗi unpack THUMBS.)"""
    lm = [[cx, cy, 0.0]]
    for dx, dy in ((-0.3, -0.3), (-0.5, -0.6), (-0.35, -0.8), (-0.15, -0.7)):  # ngón cái gập vào lòng
        lm.append([cx + dx * s, cy + dy * s, 0.0])
    for f, e in enumerate(ext):
        x = cx + (-0.3, -0.1, 0.1, 0.3)[f] * s
        for dist in ((1.0, 1.3, 1.6, 1.9) if e else (1.0, 1.3, 1.1, 0.9)):
            lm.append([x, cy - dist * s, 0.0])
    return lm


POSES = {"fist": (0, 0, 0, 0), "open": (1, 1, 1, 1), "next": (1, 1, 0, 0), "previous": (1, 0, 0, 0)}

ROOT = Path(__file__).parents[1]
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "gru_parity.json").read_text(encoding="utf-8"))
CLASSES = FIXTURE["classes"]  # next, none, previous, zoom_in, zoom_out


def model_dir(tmp_path, step_ms=FIXTURE["step_ms"]):
    (tmp_path / "gru.labels.json").write_text(json.dumps(CLASSES), encoding="utf-8")
    (tmp_path / "gru.meta.json").write_text(json.dumps({"sequence_length": 16, "step_ms": step_ms}), encoding="utf-8")
    return str(tmp_path)


class FakeModel:
    def __init__(self, probs):
        self.probs, self.windows = np.asarray([probs], dtype=np.float32), []

    def __call__(self, window):
        self.windows.append(window.copy())
        return self.probs


def fixture_frames():
    for t, lm in zip(FIXTURE["t_ms"], FIXTURE["landmarks"]):
        yield FeatureWindow(t, lm is not None, landmarks=lm)


def test_window_matches_research_preprocessing(tmp_path):
    fake = FakeModel([0, 1, 0, 0, 0])
    rec = GRURecognizer(model_dir(tmp_path), flip_x=True, model=fake)
    for fw in fixture_frames():
        rec(fw)
    assert len(fake.windows) == 16
    np.testing.assert_allclose(fake.windows[-1][0], np.asarray(FIXTURE["expected_window"]), atol=1e-5)


def test_real_model_gives_same_probabilities():
    pytest.importorskip("tensorflow")
    if not (ROOT / "models" / "gru" / "gru.keras").exists():
        pytest.skip("chưa copy model vào models/gru")
    rec = GRURecognizer(str(ROOT / "models" / "gru"), flip_x=True)
    hyp = None
    for fw in fixture_frames():
        hyp = rec(fw)
    raw = np.asarray(rec.model(rec.buffer.window()))[0]
    np.testing.assert_allclose(raw, FIXTURE["expected_probs"], atol=1e-3)
    assert hyp.label == FIXTURE["expected_label"] == "previous"  # vuốt trái (đã lật gương) -> previous


def test_without_unmirroring_swipe_direction_flips(tmp_path):
    fake = FakeModel([0, 1, 0, 0, 0])
    rec = GRURecognizer(model_dir(tmp_path), flip_x=False, model=fake)
    for fw in fixture_frames():
        rec(fw)
    dx = fake.windows[-1][0, 5:, 63]
    assert np.sum(dx) == pytest.approx(-np.sum(np.asarray(FIXTURE["expected_window"])[5:, 63]), abs=1e-5)


def test_samples_by_time_not_by_camera_frames(tmp_path):
    fake = FakeModel([0, 1, 0, 0, 0])
    rec = GRURecognizer(model_dir(tmp_path, step_ms=167), model=fake)
    hand = make_hand(POSES["next"])
    for t in range(0, 1002, 33):  # 30 fps trong ~1 s
        rec(FeatureWindow(t, True, landmarks=hand))
    assert len(fake.windows) == 6  # 1000 / 167 ≈ 6 bước


def test_zoom_is_merged_into_none(tmp_path):
    rec = GRURecognizer(model_dir(tmp_path), model=FakeModel([0.05, 0.05, 0.1, 0.5, 0.3]))
    hyp = rec(FeatureWindow(0, True, landmarks=make_hand(POSES["open"])))
    assert hyp.label == "none" and hyp.command is None
    assert hyp.probs["none"] == pytest.approx(0.85)
    assert set(hyp.probs) == {"next", "previous", "none"}


def test_rule_exclude_removes_static_next_previous():
    rule = RuleRecognizer(exclude=("next", "previous"))
    fx = FeatureExtractor(Config())
    for pose in ("next", "previous"):
        hyp = rule(fx(Observation(0, make_hand(POSES[pose]))))
        assert hyp.label not in ("next", "previous")


def hybrid(tmp_path, gru_probs, **cfg):
    gru = GRURecognizer(model_dir(tmp_path), model=FakeModel(gru_probs))
    return HybridRecognizer(Config(recognizer="hybrid", **cfg), gru=gru)


def test_hybrid_prefers_confident_swipe(tmp_path):
    rec = hybrid(tmp_path, [0.9, 0.05, 0.05, 0, 0])
    hyp = rec(FeatureWindow(0, True, ext=(1, 1, 1, 1), landmarks=make_hand(POSES["open"])))
    assert hyp.label == "next" and hyp.command == "next"


def test_hybrid_uses_rule_for_static_poses(tmp_path):
    rec = hybrid(tmp_path, [0.1, 0.8, 0.1, 0, 0])
    fist = FeatureExtractor(Config())(Observation(0, make_hand(POSES["fist"])))
    assert rec(fist).label == RuleRecognizer()(fist).label


def test_hybrid_ignores_static_command_while_hand_moves_fast(tmp_path):
    rec = hybrid(tmp_path, [0.1, 0.8, 0.1, 0, 0], static_max_speed=1.5)
    open_hand = FeatureExtractor(Config())(Observation(0, make_hand(POSES["open"])))
    assert RuleRecognizer(exclude=("next", "previous"))(open_hand).label == "play_pause"
    moving = FeatureWindow(0, True, open_hand.vector, open_hand.ext, 5.0, 3, open_hand.thumb, open_hand.landmarks)
    assert rec(moving).command is None


def test_hybrid_no_hand_still_feeds_gru(tmp_path):
    rec = hybrid(tmp_path, [0.9, 0.05, 0.05, 0, 0])
    hyp = rec(FeatureWindow(0, False))
    assert not hyp.has_hand and hyp.command is None
    assert len(rec.gru.model.windows) == 1


def test_feature_window_carries_raw_landmarks():
    hand = make_hand(POSES["next"])
    fw = FeatureExtractor(Config())(Observation(0, hand))
    assert fw.landmarks == hand


def test_reset_forgets_sequence(tmp_path):
    fake = FakeModel([0.9, 0.05, 0.05, 0, 0])
    rec = GRURecognizer(model_dir(tmp_path), model=fake)
    for fw in fixture_frames():
        rec(fw)
    rec.reset()
    assert rec(FeatureWindow(10_000, True, landmarks=make_hand(POSES["open"]))).label == "next"  # bước mới -> chạy lại model
    window = fake.windows[-1][0]
    assert not window[:-1].any()        # chỉ còn đúng 1 bước sau reset
    assert not window[-1, 63:].any()    # không có motion giả nối với chuỗi cũ


def test_pipeline_resets_recognizer_after_accept():
    from src.datatypes import Hypothesis
    from src.pipeline import Pipeline
    from src.actions.action_dispatcher import ActionDispatcher

    class Stub:
        resets = 0

        def __call__(self, fw):
            return Hypothesis(fw.t_ms, fw.hand, "next", {"next": 0.99, "none": 0.01}, 0.98, "next")

        def reset(self):
            Stub.resets += 1

    cfg = Config(policy="swipe", swipe_hold_ms=0, cooldown_ms=10_000)
    p = Pipeline(cfg, recognizer=Stub(), dispatcher=ActionDispatcher(cfg, quiet=True))
    verdicts = [p.process(Observation(t, make_hand(POSES["open"]))).verdict for t in range(0, 300, 33)]
    assert verdicts.count("ACCEPT") == 1
    # xóa lúc ACCEPT và ở mọi khung cooldown: chuyển động trong cooldown không được tính cho lệnh sau
    assert Stub.resets == len(verdicts)
