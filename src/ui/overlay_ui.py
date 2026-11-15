"""Khối: phản hồi trực quan. Decision -> trạng thái HUD (7 trạng thái) và vẽ lên khung hình."""
from __future__ import annotations

import time
from typing import Optional

import cv2

from ..datatypes import ACCEPT, ARMED, UNCERTAIN, Decision

HUD_TEXT = {
    "IDLE": "Dang cho", "ARMED": "San sang nhan lenh", "COMMAND": "Giu yen...",
    "CONFIRM": "Like = dong y, Dislike = huy",
    "UNCERTAIN": "Chua chac, giu them", "REJECT": "Khong phai lenh",
    "EXECUTE": "Da gui", "COOLDOWN": "Nghi giay lat",
}

ACTION_NAMES = {
    "next": "NEXT SLIDE",
    "previous": "PREVIOUS SLIDE",
    "play_pause": "PLAY/PAUSE",
    "start_show": "START SHOW",
    "exit_show": "EXIT SHOW"
}


class OverlayUI:
    def __init__(self, on_change=None, command_duration_s: float = 1.0):
        self.on_change = on_change
        self.command_duration_s = command_duration_s
        self.hud = {"state": "IDLE", "label": "", "conf": 0.0, "progress": 0.0, "reason": ""}
        self.last_command: Optional[str] = None
        self.last_command_time: float = 0.0
        self.last_command_t_ms: Optional[int] = None

    def __call__(self, dec: Decision) -> Decision:
        if dec.verdict == ACCEPT:          # ACCEPT và EXECUTE dùng chung một ô HUD
            state = "EXECUTE"
            if dec.command:
                self.last_command = dec.command
                self.last_command_time = time.monotonic()
                self.last_command_t_ms = dec.t_ms
        elif dec.verdict == UNCERTAIN:
            state = "UNCERTAIN"
        elif dec.state == ARMED and dec.reason in ("low_conf", "low_margin"):
            state = "REJECT"
        else:
            state = dec.state
        changed = state != self.hud["state"]
        self.hud = {"state": state, "label": dec.label, "conf": dec.conf, "progress": dec.progress, "reason": dec.reason}
        if changed and self.on_change:
            self.on_change(self.hud)
        return dec

    def draw(self, frame, t_ms: Optional[int] = None) -> None:
        # từ teammate: cv2.putText hiển thị "label xx%" trong 05_realtime.py / run_gate_realtime.py
        h = self.hud
        text = f"{h['state']} | {h['label']} {h['conf']:.0%} | {HUD_TEXT.get(h['state'], '')}"
        cv2.putText(frame, text, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Hiện 1 dòng ghi command đã thực hiện gần nhất trong 1s từ khi nhận command, rồi biến mất
        is_active = False
        if self.last_command:
            if t_ms is not None and self.last_command_t_ms is not None:
                is_active = (0 <= (t_ms - self.last_command_t_ms) <= int(self.command_duration_s * 1000))
            else:
                is_active = (0.0 <= (time.monotonic() - self.last_command_time) <= self.command_duration_s)

        if is_active and self.last_command:
            action_name = ACTION_NAMES.get(self.last_command, self.last_command.upper())
            cmd_text = f"CMD: {action_name}"
            # Viền đen nền giúp chữ tương phản rõ ràng trên mọi hình nền webcam
            cv2.putText(frame, cmd_text, (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
            cv2.putText(frame, cmd_text, (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
