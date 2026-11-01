from src.perception.features import frame_ext, landmarks_to_vector
from tests.helpers import make_hand


def test_vector_has_63_values():
    assert len(landmarks_to_vector(make_hand((1, 1, 1, 1)))) == 63


def test_vector_invariant_to_position_and_size():
    a = landmarks_to_vector(make_hand((1, 1, 0, 0), cx=0.3, cy=0.7, s=0.10))
    b = landmarks_to_vector(make_hand((1, 1, 0, 0), cx=0.6, cy=0.9, s=0.20))
    assert max(abs(x - y) for x, y in zip(a, b)) < 1e-6


def test_finger_extension():
    assert min(frame_ext(make_hand((1, 1, 1, 1)))) > 0.9
    assert max(frame_ext(make_hand((0, 0, 0, 0)))) < 0.1
