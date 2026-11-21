from types import SimpleNamespace

import pytest

from src.actions.action_dispatcher import ActionDispatcher, parse_key
from src.config import Config
from src.datatypes import ACCEPT, REJECT, Decision


class FakeKb:
    def __init__(self):
        self.log = []

    def press(self, k):
        self.log.append(("press", k))

    def release(self, k):
        self.log.append(("release", k))


FAKE_KEY = SimpleNamespace(right="<right>", left="<left>", esc="<esc>", f5="<f5>", shift="<shift>", alt="<alt>", ctrl="<ctrl>")


def make(dry_run=False, **kw):
    kb = FakeKb()
    cfg = Config(dry_run=dry_run, keymap={"next": "right", "previous": "left", "start_show": "shift+f5", "exit_show": "esc"}, **kw)
    return ActionDispatcher(cfg, quiet=True, backend=(kb, FAKE_KEY)), kb


def accept(cmd, t=0):
    return Decision(t, ACCEPT, cmd, "accepted", "COOLDOWN")


def test_next_and_previous_press_arrow_keys():
    d, kb = make()
    d(accept("next"))
    d(accept("previous"))
    assert kb.log == [("press", "<right>"), ("release", "<right>"), ("press", "<left>"), ("release", "<left>")]


def test_start_show_sends_shift_f5_with_modifier_held_around_the_key():
    d, kb = make()
    d(accept("start_show"))
    assert kb.log == [("press", "<shift>"), ("press", "<f5>"), ("release", "<f5>"), ("release", "<shift>")]


def test_exit_show_sends_escape():
    d, kb = make()
    d(accept("exit_show"))
    assert kb.log == [("press", "<esc>"), ("release", "<esc>")]


def test_command_without_a_key_sends_nothing():
    d, kb = make()
    d(accept("play_pause"))                       # đã bỏ khỏi bộ cử chỉ mới: không có phím tương ứng
    assert kb.log == []


def test_dry_run_records_but_sends_nothing():
    d, kb = make(dry_run=True)
    d(accept("next"))
    assert kb.log == [] and [k for _, k in d.sent] == ["right"]


def test_only_accept_sends_keys():
    d, kb = make()
    d(Decision(0, REJECT, "next", "holding", "COMMAND"))
    assert kb.log == [] and d.sent == []


def test_bad_config_fails_early():
    with pytest.raises(ValueError):
        parse_key("hyper+p")
    with pytest.raises(ValueError):
        ActionDispatcher(Config(keymap={"next": "nokey"}, dry_run=False), backend=(FakeKb(), FAKE_KEY))
