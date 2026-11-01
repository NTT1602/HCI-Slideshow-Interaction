import math

from src.datatypes import Decision, FeatureWindow, Hypothesis, Observation


THUMBS = {
    "tuck": ((-0.3, -0.3), (-0.5, -0.6), (-0.35, -0.8), (-0.15, -0.7)),    # gập vào lòng bàn tay (cong)
    "out": ((-0.4, -0.3), (-0.8, -0.5), (-1.15, -0.6), (-1.5, -0.7)),      # duỗi sang bên
    "up": ((-0.3, -0.3), (-0.35, -0.7), (-0.35, -1.1), (-0.35, -1.5)),     # duỗi thẳng lên
    "down": ((-0.3, 0.2), (-0.35, 0.6), (-0.35, 1.0), (-0.35, 1.4)),       # duỗi thẳng xuống
}

def make_hand(ext, cx=0.5, cy=0.8, s=0.15, thumb="tuck"):
    """Bàn tay giả 21 landmark; ext = mức duỗi 4 ngón (trỏ, giữa, nhẫn, út)."""
    lm = [[cx, cy, 0.0]]
    ang, dists = THUMBS[thumb]  # ngón cái: tuck = gập vào lòng bàn tay, up/down = duỗi chĩa lên/xuống
    for dist in dists:
        lm.append([cx + math.sin(ang) * dist * s, cy - math.cos(ang) * dist * s, 0.0])
    for f, e in enumerate(ext):
        a, k = (-0.2, -0.07, 0.07, 0.2)[f], (0.85 if f == 3 else 1.0)
        for dist in (1.0 * k, (1.3 + 0.2 * e) * k, (1.15 + 0.65 * e) * k, (0.9 + 1.2 * e) * k):
            lm.append([cx + math.sin(a) * dist * s, cy - math.cos(a) * dist * s, 0.0])
    return lm


POSES = {"arm": (1, 1, 1, 1), "next": (1, 1, 0, 0), "previous": (1, 0, 0, 0), "fist": (0, 0, 0, 0), "other": (0, 1, 0, 0),
         "three": (1, 1, 1, 0), "like": (0, 0, 0, 0), "dislike": (0, 0, 0, 0)}  # fist = nắm tay (play_pause); other = tư thế không phải lệnh


def session(segments, dt=33):
    """segments = [(tên tư thế, thời lượng ms, truth)] -> danh sách Observation."""
    out, t = [], 0
    for pose, dur, truth in segments:
        for _ in range(max(1, dur // dt)):
            out.append(Observation(t, make_hand(POSES[pose], thumb={"like": "up", "dislike": "down"}.get(pose, "tuck")), "Right", 0.99, None, truth))
            t += dt
    return out


def fw(t, speed=0.0, hand=True):
    return FeatureWindow(t, hand, (), (0, 0, 0, 0), speed, 5)


def hyp(t, label, conf=0.95, margin=0.8, hand=True):
    cmd = label if label in ("next", "previous", "play_pause") else None
    return Hypothesis(t, hand, label, {label: conf, "none": 1 - conf}, margin, cmd)
