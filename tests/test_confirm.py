from src.actions.action_dispatcher import ActionDispatcher
from src.config import Config
from src.pipeline import Pipeline
from tests.helpers import session

CFG = Config(policy="fixed", command_hold_ms={"exit_show": 600})


def run(segments):
    p = Pipeline(CFG, dispatcher=ActionDispatcher(CFG, quiet=True))
    decs = [p.process(o) for o in session(segments)]
    return p, decs


def accepts(decs):
    return [d.command for d in decs if d.verdict == "ACCEPT"]


def test_recognizer_labels():
    from src.perception.features import FeatureExtractor
    from src.perception.recognizer import RuleRecognizer
    from tests.helpers import make_hand
    from src.datatypes import Observation
    def label(ext, thumb):
        fx = FeatureExtractor(CFG)
        return RuleRecognizer()(fx(Observation(0, make_hand(ext, thumb=thumb)))).label
    assert label((1, 1, 1, 0), "tuck") == "exit_show"
    assert label((0, 0, 0, 0), "tuck") == "play_pause"
    assert label((0, 0, 0, 0), "up") == "like"
    assert label((0, 0, 0, 0), "down") == "dislike"


def test_three_fingers_alone_never_exits():
    p, decs = run([("arm", 500, None), ("three", 2500, None)])
    assert accepts(decs) == [] and decs[-1].state == "CONFIRM" and p.dispatcher.sent == []


def test_like_confirms_then_cooldown_then_idle():
    p, decs = run([("arm", 500, None), ("three", 1000, None), ("like", 700, None), ("other", 1500, None), ("other", 500, None)])
    assert accepts(decs) == ["exit_show"]
    assert [k for _, k in p.dispatcher.sent] == ["esc"]
    states = [d.state for d in decs]
    assert "CONFIRM" in states and "COOLDOWN" in states and decs[-1].state == "IDLE"


def test_dislike_cancels_back_to_idle():
    p, decs = run([("arm", 500, None), ("three", 1000, None), ("dislike", 400, None)])
    assert accepts(decs) == [] and p.dispatcher.sent == []
    assert decs[-1].state == "IDLE" and decs[-1].reason in ("cancelled", "idle")


def test_confirm_times_out():
    p, decs = run([("arm", 500, None), ("three", 1000, None), ("other", CFG.confirm_timeout_ms + 600, None)])
    assert accepts(decs) == [] and decs[-1].state == "IDLE"


def test_short_like_does_not_confirm():
    p, decs = run([("arm", 500, None), ("three", 1000, None), ("like", 150, None), ("other", 800, None)])
    assert accepts(decs) == []
