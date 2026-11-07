"""Live Runtime: vòng lặp thời gian thực camera -> MediaPipe -> Pipeline -> hiển thị.
Thay cho 05_realtime.py và run_gate_realtime.py của teammate. Cần webcam và quyền camera."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import replace

import cv2

from .config import Config
from .evaluation.session_logger import SessionLogger
from .perception.camera_source import CameraSource
from .perception.hand_tracker import HandTracker
from .pipeline import Pipeline
from .ui.overlay_ui import OverlayUI

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

class LiveSession:
    """Một phiên chạy: run() chặn cho tới khi request_stop() (hoặc bấm q ở cửa sổ camera, hoặc lỗi).
    Có thể đổi dry-run / bật tắt cửa sổ camera khi đang chạy; snapshot() cho giao diện đọc trạng thái từ luồng khác."""

    def __init__(self, cfg: Config, log: bool = True, preview: bool = True):
        self.cfg, self.log, self.preview = cfg, log, preview
        self.dry_run = cfg.dry_run
        self.stop_event = threading.Event()
        self.pipe = None
        self.running = False
        self.starting = True
        self.error = None
        self.fps = 0.0
        self.hand_ratio = 0.0

    def request_stop(self) -> None:
        self.stop_event.set()

    def set_dry_run(self, flag: bool) -> None:
        if self.pipe is not None:
            self.pipe.dispatcher.set_dry_run(flag)  # có thể raise nếu thiếu pynput: lúc đó chế độ giữ nguyên
        self.dry_run = flag

    def snapshot(self) -> dict:
        pipe = self.pipe
        ov = pipe.overlay if pipe else None
        return {
            "running": self.running, "starting": self.starting, "dry_run": self.dry_run, "error": self.error,
            "hud": dict(ov.hud) if ov else None,
            "last_command": ov.last_command if ov else None,
            "last_command_age": (time.monotonic() - ov.last_command_time) if ov and ov.last_command else None,
            "fps": self.fps, "hand": self.hand_ratio,
        }

    def run(self) -> None:
        logger = None
        try:
            cfg = replace(self.cfg, dry_run=self.dry_run)
            if self.log:
                os.makedirs(cfg.log_dir, exist_ok=True)
                logger = SessionLogger(os.path.join(cfg.log_dir, time.strftime("%Y%m%d-%H%M%S") + ".jsonl"), cfg)
            self.pipe = Pipeline(cfg, overlay=OverlayUI(on_change=_print_state), logger=logger)
            if not self.dry_run:
                print("Đang GỬI PHÍM THẬT. Bấm vào cửa sổ PowerPoint (đang trình chiếu) để nó nhận phím; Ctrl+C trong terminal để dừng.")
            beat = Heartbeat(cfg.status_every_s, time.monotonic())
            with CameraSource(cfg.camera_index) as cam, HandTracker() as tracker:
                self.running, self.starting = True, False
                win_open, n, hands, t_fps = False, 0, 0, time.monotonic()
                while not self.stop_event.is_set():
                    frame, t_ms = cam.read()
                    if frame is None:
                        print("[live] Camera không trả khung hình nữa, dừng.")
                        break
                    obs = tracker.track(frame, t_ms)
                    self.pipe.process(obs)
                    now = time.monotonic()
                    n, hands = n + 1, hands + (1 if obs.landmarks is not None else 0)
                    if now - t_fps >= 1.0:
                        self.fps, self.hand_ratio, n, hands, t_fps = n / (now - t_fps), hands / n, 0, 0, now
                    msg = beat.update(obs.landmarks is not None, self.pipe.overlay.hud, now)
                    if msg:
                        print(msg)
                    if self.preview:
                        if not win_open:
                            _setup_window(cfg)
                            win_open = True
                        tracker.draw(frame)
                        self.pipe.overlay.draw(frame)
                        cv2.imshow(WINDOW, frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    elif win_open:
                        cv2.destroyWindow(WINDOW)
                        win_open = False
        except KeyboardInterrupt:
            pass
        except Exception as e:  # giao diện hiển thị lỗi này thay vì đóng im lặng
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.running = self.starting = False
            cv2.destroyAllWindows()
            if logger:
                logger.close()


def run_live(cfg: Config, log: bool = True):
    session = LiveSession(cfg, log=log, preview=True)
    session.run()
    if session.error:
        print(f"[live] Lỗi: {session.error}")
