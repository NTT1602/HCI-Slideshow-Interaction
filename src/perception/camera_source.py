"""Khối: Camera + OpenCV. Mở webcam, lật gương, gắn timestamp (ms, tăng dần), chỉ giữ khung mới nhất."""
from __future__ import annotations

import time

import cv2


class CameraSource:
    # từ teammate: 01_webcam.py (VideoCapture, kiểm tra isOpened, cv2.flip) - trước đây lặp lại ở mọi script
    def __init__(self, index: int = 0):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError("Không mở được webcam. Hãy kiểm tra quyền camera hoặc camera index.")
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # giữ khung mới nhất, không tích độ trễ
        self.t0 = time.monotonic()

    def read(self):
        """Trả về (khung BGR đã lật gương, t_ms) hoặc (None, None) nếu hết luồng."""
        ok, frame = self.cap.read()
        if not ok:
            return None, None
        return cv2.flip(frame, 1), int((time.monotonic() - self.t0) * 1000)

    def close(self):
        self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
