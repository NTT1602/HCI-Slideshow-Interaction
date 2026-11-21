"""config.yaml: các lệnh của bộ cử chỉ mới phải có phím hợp lệ và gửi đúng phím qua ActionDispatcher."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.actions.action_dispatcher import ActionDispatcher, parse_key
from src.config import load_config
from src.datatypes import ACCEPT, Decision

FAKE_KEY = SimpleNamespace(right="<right>", left="<left>", esc="<esc>", f5="<f5>", shift="<shift>", alt="<alt>", ctrl="<ctrl>", space="<space>")


class FakeKb:
    def __init__(self):
        self.log = []

    def press(self, k):
        self.log.append(("press", k))

    def release(self, k):
        self.log.append(("release", k))


@pytest.fixture
def cfg():
    return load_config(str(Path(__file__).parents[1] / "config.yaml"))


def test_commands_have_the_expected_keys(cfg):
    assert cfg.keymap["next"] == "right"          # vuốt phải: slide kế
    assert cfg.keymap["previous"] == "left"       # vuốt trái: slide trước
    assert cfg.keymap["exit_show"] == "esc"       # dislike: thoát trình chiếu
    assert cfg.keymap["start_show"] in ("f5", "shift+f5")   # like: vào trình chiếu (f5 = từ đầu, shift+f5 = từ slide đang mở)


def test_every_key_in_the_keymap_is_valid(cfg):
    for cmd, spec in cfg.keymap.items():
        parse_key(spec)                            # sai cú pháp thì ném ValueError, test báo đúng lệnh nào sai


def test_play_pause_is_disabled_if_it_is_still_mapped(cfg):
    assert "play_pause" not in cfg.keymap or "play_pause" in cfg.disabled_commands


def test_accepted_commands_press_the_configured_keys(cfg):
    kb = FakeKb()
    d = ActionDispatcher(cfg, quiet=True, backend=(kb, FAKE_KEY))
    d.dry_run = False
    for t, cmd in enumerate(("next", "previous", "exit_show")):
        d(Decision(t, ACCEPT, cmd, "accepted", "COOLDOWN"))
    pressed = [k for op, k in kb.log if op == "press"]
    assert pressed == ["<right>", "<left>", "<esc>"]


def test_dry_run_sends_nothing_but_records(cfg):
    kb = FakeKb()
    d = ActionDispatcher(cfg, quiet=True, backend=(kb, FAKE_KEY))
    d.dry_run = True
    d(Decision(0, ACCEPT, "next", "accepted", "COOLDOWN"))
    assert kb.log == [] and [k for _, k in d.sent] == ["right"]
