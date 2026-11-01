from src.config import Config
from src.evaluation.metrics import evaluate
from src.pipeline import Pipeline
from tests.helpers import session


def run_pipeline(segs):
    obs = session(segs)
    p = Pipeline(Config(recognizer="rule"))
    return obs, [p.process(o) for o in obs]


def test_hit_without_false_trigger():
    obs, dec = run_pipeline([("none", 500, "bg"), ("arm", 700, "arm"), ("next", 1000, "cmd:next"), ("none", 500, "bg")])
    m = evaluate(obs, dec)
    assert (m["intents"], m["hits"], m["false_triggers"]) == (1, 1, 0)
    assert m["median_latency_ms"] > 0


def test_command_pose_without_arm_is_not_executed():
    obs, dec = run_pipeline([("next", 1500, "bg")])  # làm cử chỉ lệnh nhưng không kích hoạt: không được gửi phím
    assert evaluate(obs, dec)["false_triggers"] == 0
