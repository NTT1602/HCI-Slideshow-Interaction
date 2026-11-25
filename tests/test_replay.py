import pytest

from src.actions.action_dispatcher import ActionDispatcher
from src.config import POLICIES, Config
from src.evaluation.replay import compare, load_log, run
from src.evaluation.session_logger import SessionLogger
from src.pipeline import Pipeline
from tests.fakes import ScriptedRecognizer, observations

SEGS = [("none", 500, "bg"), ("arm", 700, "arm"), ("swipe_right", 600, "cmd:next"), ("none", 500, "bg")]


@pytest.fixture(autouse=True)
def scripted_model(monkeypatch):
    """replay.run tự tạo Pipeline từ config nên thay 'model' bằng bản giả ở chỗ Pipeline gọi make_recognizer (không phải sửa code)."""
    monkeypatch.setattr("src.pipeline.make_recognizer", lambda cfg: ScriptedRecognizer(SEGS))


def base_cfg(**kw):
    base = dict(policy="swipe", dry_run=True, conf=0.7, hold_ms=400, swipe_hold_ms=0, cooldown_ms=800,
                reverse_block_ms=2500, command_hold_ms={}, disabled_commands=[], confirm_commands=[])
    base.update(kw)
    return Config(**base)


def test_pipeline_live_and_replay_give_same_decisions(tmp_path):
    cfg, obs = base_cfg(), observations(SEGS)
    path = tmp_path / "s.jsonl"
    logger = SessionLogger(str(path), cfg)
    p = Pipeline(cfg, dispatcher=ActionDispatcher(cfg, quiet=True), logger=logger)
    live = [p.process(o) for o in obs]
    logger.close()
    accepts = [d for d in live if d.verdict == "ACCEPT"]
    assert len(accepts) == 1 and accepts[0].command == "next"
    assert [k for t, k in p.dispatcher.sent] == ["right"]            # next -> phím "right" từ config.keymap
    cfg2, obs2 = load_log(str(path))
    assert run(obs2, cfg2) == live                                    # replay cho đúng kết quả của live


def test_compare_runs_all_policies_on_same_data():
    out = compare(observations(SEGS), base_cfg())
    assert set(out) == set(POLICIES)                                  # lấy từ config, thêm policy mới không phải sửa test
    for name in ("naive", "fixed", "swipe"):
        assert out[name]["hits"] == 1, name
