"""Live Runtime: vòng lặp thời gian thực camera -> MediaPipe -> Pipeline -> hiển thị.
Thay cho 05_realtime.py và run_gate_realtime.py của teammate. Cần webcam và quyền camera."""
from __future__ import annotations

import os
import time

import cv2

from .config import Config
from .evaluation.session_logger import SessionLogger
from .perception.camera_source import CameraSource
from .perception.hand_tracker import HandTracker
from .pipeline import Pipeline

WINDOW = "Gesture slide controller (q de thoat)"


class Heartbeat:
    """Gom số liệu và trả về một dòng trạng thái mỗi `every_s` giây, để biết vòng lặp còn chạy và có thấy tay hay không."""

    def __init__(self, every_s: float, now: float):
        self.every_s, self.t0, self.frames, self.hands = every_s, now, 0, 0

    def update(self, has_hand: bool, hud: dict, now: float):
        self.frames += 1
        self.hands += 1 if has_hand else 0
        dt = now - self.t0
        if self.every_s <= 0 or dt < self.every_s:
            return None
        msg = (f"[live] {self.frames / dt:.0f} khung/s | thấy tay {self.hands / self.frames:.0%} | "
               f"trạng thái {hud['state']} | nhãn {hud['label'] or '-'} {hud['conf']:.0%}")
        self.t0, self.frames, self.hands = now, 0, 0
        return msg


def _print_state(hud: dict) -> None:
    print(f"[{hud['state']}] {hud['label'] or '-'} {hud['conf']:.0%} ({hud['reason']})")


def _setup_window(cfg: Config) -> None:
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        cv2.resizeWindow(WINDOW, cfg.preview_width, int(cfg.preview_width * 3 / 4))
        if cfg.preview_topmost:  # luôn nổi trên cùng, kể cả khi PowerPoint đang toàn màn hình
            cv2.setWindowProperty(WINDOW, getattr(cv2, "WND_PROP_TOPMOST", 5), 1)
    except cv2.error:
        pass  # bản OpenCV/hệ điều hành không hỗ trợ: bỏ qua

def run_live(cfg: Config, log: bool = True):
    logger = None
    if log:
        os.makedirs(cfg.log_dir, exist_ok=True)
        logger = SessionLogger(os.path.join(cfg.log_dir, time.strftime("%Y%m%d-%H%M%S") + ".jsonl"), cfg)
    pipe = Pipeline(cfg, logger=logger)
    if not cfg.dry_run:
        print("Đang GỬI PHÍM THẬT. Bấm vào cửa sổ PowerPoint (đang trình chiếu) để nó nhận phím; Ctrl+C trong terminal để dừng.")
    try:
        with CameraSource(cfg.camera_index) as cam, HandTracker() as tracker:
            while True:
                frame, t_ms = cam.read()
                if frame is None:
                    break
                dec = pipe.process(tracker.track(frame, t_ms))
                tracker.draw(frame)
                pipe.overlay.draw(frame)
                cv2.imshow("Gesture slide controller (q de thoat)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cv2.destroyAllWindows()
        if logger:
            logger.close()
