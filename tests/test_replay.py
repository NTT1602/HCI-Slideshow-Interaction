from src.config import Config
from src.evaluation.replay import compare, load_log, run
from src.evaluation.session_logger import SessionLogger
from src.pipeline import Pipeline
from tests.helpers import session

SEGS = [("none", 500, "bg"), ("arm", 700, "arm"), ("next", 1000, "cmd:next"), ("none", 500, "bg")]


def test_pipeline_live_and_replay_give_same_decisions(tmp_path):
    cfg, obs = Config(recognizer="rule"), session(SEGS)
    path = tmp_path / "s.jsonl"
    logger = SessionLogger(str(path), cfg)
    p = Pipeline(cfg, logger=logger)
    live = [p.process(o) for o in obs]
    logger.close()
    accepts = [d for d in live if d.verdict == "ACCEPT"]
    assert len(accepts) == 1 and accepts[0].command == "next"
    assert [k for t, k in p.dispatcher.sent] == ["right"]            # next -> phím "right" từ config.keymap
    cfg2, obs2 = load_log(str(path))
    assert run(obs2, cfg2) == live                                    # replay cho đúng kết quả của live


def test_compare_runs_all_policies_on_same_data():
    out = compare(session(SEGS), Config(recognizer="rule"))
    assert set(out) == {"naive", "fixed", "adaptive", "abstain", "combined"}
    assert out["fixed"]["hits"] == 1
