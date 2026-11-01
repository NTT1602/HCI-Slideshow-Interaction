import numpy as np
from src.datatypes import ACCEPT, Decision
from src.ui.overlay_ui import OverlayUI


def test_overlay_shows_last_command_and_expires():
    ui = OverlayUI(command_duration_s=1.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Ban đầu chưa có lệnh nào
    ui.draw(frame, t_ms=0)
    assert ui.last_command is None

    # Nhận quyết định ACCEPT lệnh "next" tại t = 1000 ms
    dec = Decision(
        t_ms=1000,
        verdict=ACCEPT,
        command="next",
        reason="held",
        state="EXECUTE",
        label="next",
        conf=0.95,
    )
    ui(dec)

    assert ui.last_command == "next"

    # Tại t = 1500 ms (cách 0.5s <= 1.0s): lệnh vẫn còn hiển thị
    frame_at_500ms = np.zeros((480, 640, 3), dtype=np.uint8)
    ui.draw(frame_at_500ms, t_ms=1500)
    # Khung hình có vẽ chữ (không toàn màu đen)
    assert frame_at_500ms.sum() > 0

    # Tại t = 2000 ms (vừa đúng 1s): vẫn hiển thị
    frame_at_1000ms = np.zeros((480, 640, 3), dtype=np.uint8)
    ui.draw(frame_at_1000ms, t_ms=2000)
    assert frame_at_1000ms.sum() > 0

    # Tại t = 2001 ms (> 1.0s): lệnh đã hết hạn và biến mất
    frame_expired = np.zeros((480, 640, 3), dtype=np.uint8)
    # Reset hud text to black/empty to check if command line is drawn
    ui.hud["state"] = ""
    ui.draw(frame_expired, t_ms=2050)
    # Check that pixels around y=75 are not drawn with command
    # Line 2 was at y=75
    y75_pixels = frame_expired[65:85, :]
    assert y75_pixels.sum() == 0

