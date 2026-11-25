from pathlib import Path

from src.config import load_config
from src.live import Heartbeat

HUD = {"state": "ARMED", "label": "arm", "conf": 0.97}


def test_heartbeat_reports_fps_hand_ratio_and_state_every_interval():
    hb = Heartbeat(5.0, now=0.0)
    assert all(hb.update(i % 2 == 0, HUD, now=0.1 * i) is None for i in range(1, 40))   # chưa đủ 5 giây
    msg = hb.update(True, HUD, now=5.0)
    assert "khung/s" in msg and "thấy tay 50%" in msg and "ARMED" in msg and "arm 97%" in msg
    assert hb.update(True, HUD, now=5.1) is None                                          # đã reset


def test_heartbeat_can_be_turned_off():
    hb = Heartbeat(0, now=0.0)
    assert hb.update(True, HUD, now=100.0) is None


def test_config_yaml_has_preview_and_status_options():
    cfg = load_config(str(Path(__file__).parents[1] / "config.yaml"))
    assert cfg.preview_width > 0 and cfg.status_every_s == 5 and cfg.preview_topmost is True
