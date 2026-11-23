from src.actions.action_dispatcher import ActionDispatcher
from src.config import Config
from src.evaluation.metrics import evaluate
from src.pipeline import Pipeline
from tests.fakes import ScriptedRecognizer, observations


def cfg(**kw):
    base = dict(policy="swipe", dry_run=True, swipe_hold_ms=0, cooldown_ms=800, reverse_block_ms=2500,
                command_hold_ms={}, disabled_commands=[], confirm_commands=[])
    base.update(kw)
    return Config(**base)


def run_pipeline(segs, **kw):
    c = cfg(**kw)
    p = Pipeline(c, recognizer=ScriptedRecognizer(segs), dispatcher=ActionDispatcher(c, quiet=True))
    obs = observations(segs)
    return obs, [p.process(o) for o in obs]


def test_swipe_that_the_user_meant_is_a_hit_without_false_trigger():
    obs, dec = run_pipeline([("none", 500, "bg"), ("swipe_right", 300, "cmd:next"), ("none", 500, "bg")])
    m = evaluate(obs, dec)
    assert (m["intents"], m["hits"], m["false_triggers"]) == (1, 1, 0)
    assert m["median_latency_ms"] >= 0


def test_swipe_nobody_asked_for_counts_as_a_false_trigger():
    """Model báo vuốt nhưng người dùng không chủ ý (truth = nền): phải bị tính là kích hoạt nhầm."""
    obs, dec = run_pipeline([("none", 500, "bg"), ("swipe_right", 300, "bg"), ("none", 500, "bg")])
    assert evaluate(obs, dec)["false_triggers"] == 1


def test_arm_policy_ignores_a_swipe_that_comes_without_arm():
    obs, dec = run_pipeline([("swipe_right", 1500, "bg")], policy="fixed", hold_ms=400)
    assert evaluate(obs, dec)["false_triggers"] == 0
