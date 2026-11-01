"""Khối: MediaPipe Hands. Khung hình -> Observation.

LƯU Ý: dùng API cũ mp.solutions.hands (như code của teammate) nên cần mediapipe==0.10.21.
Nếu chuyển sang HandLandmarker (LIVE_STREAM) thì chỉ cần sửa file này, hợp đồng Observation giữ nguyên.
"""
from __future__ import annotations

from typing import Any, Optional

import cv2

from ..datatypes import Observation


class HandTracker:
    # từ teammate: landmark_utils.py -> create_hands, process_frame, extract_landmarks, draw_landmarks
    def __init__(self, static_image_mode: bool = False):
        import mediapipe as mp
        self._mp = mp
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=static_image_mode, max_num_hands=1, model_complexity=1,
            min_detection_confidence=0.6, min_tracking_confidence=0.6)
        self.results: Any = None

    def track(self, frame_bgr, t_ms: int) -> Observation:
        self.results = self.hands.process(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        r = self.results
        if not r.multi_hand_landmarks:
            return Observation(t_ms)
        lm = [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in r.multi_hand_landmarks[0].landmark]
        world: Optional[list] = None
        if getattr(r, "multi_hand_world_landmarks", None):
            world = [[round(p.x, 5), round(p.y, 5), round(p.z, 5)] for p in r.multi_hand_world_landmarks[0].landmark]
        hand_label, score = None, 0.0
        if r.multi_handedness:
            c = r.multi_handedness[0].classification[0]
            hand_label, score = c.label, float(c.score)
        return Observation(t_ms, lm, hand_label, score, world)

    def draw(self, frame_bgr) -> None:
        if self.results is not None and self.results.multi_hand_landmarks:
            mp = self._mp
            for hand in self.results.multi_hand_landmarks:
                mp.solutions.drawing_utils.draw_landmarks(frame_bgr, hand, mp.solutions.hands.HAND_CONNECTIONS)

    def close(self):
        self.hands.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
