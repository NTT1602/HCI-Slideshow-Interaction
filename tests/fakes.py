"""Đồ giả cho test: dữ liệu quan sát và 'model' theo kịch bản, không cần camera, mediapipe hay tensorflow.

segments = [(nhãn, thời lượng ms, truth)]. Nhãn: none | nohand | arm | swipe_right | swipe_left | like | dislike.
ScriptedRecognizer trả đúng nhãn của kịch bản ở mỗi thời điểm (thay cho GRU / luật tư thế)."""
from bisect import bisect_right

from src.datatypes import Hypothesis, Observation

DT = 33
COMMANDS = {"swipe_right": "next", "swipe_left": "previous", "like": "start_show", "dislike": "exit_show"}


def hand(cx=0.5, cy=0.7, s=0.15):
    """Bàn tay giả 21 landmark (xòe nhẹ); nội dung không quan trọng vì recognizer là bản giả."""
    lm = [[cx, cy, 0.0]]
    for i in range(20):
        lm.append([cx + ((i % 5) - 2) * 0.02 * s / 0.15, cy - (1 + i // 5) * 0.4 * s, 0.0])
    return lm


def timeline(segments, dt=DT):
    starts, labels, t = [], [], 0
    for label, dur, _ in segments:
        for _ in range(max(1, dur // dt)):
            starts.append(t)
            labels.append(label)
            t += dt
    return starts, labels


def observations(segments, dt=DT):
    starts, labels = timeline(segments, dt)
    truths = [tr for _, dur, tr in segments for _ in range(max(1, dur // dt))]
    return [Observation(t, None if lab == "nohand" else hand(), "Right", 0.99, None, tr)
            for t, lab, tr in zip(starts, labels, truths)]


class ScriptedRecognizer:
    def __init__(self, segments, dt=DT, conf=0.95):
        self.starts, self.labels = timeline(segments, dt)
        self.conf = conf

    def __call__(self, fw):
        label = self.labels[max(0, bisect_right(self.starts, fw.t_ms) - 1)]
        if label == "nohand":
            return Hypothesis(fw.t_ms, False, "none", {"none": 1.0}, 1.0, None)
        return Hypothesis(fw.t_ms, True, label, {label: self.conf, "none": 1 - self.conf}, 0.8, COMMANDS.get(label))
