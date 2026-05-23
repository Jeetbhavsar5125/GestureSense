"""
core/detector.py
================
Shared gesture detection engine used by both the Desktop App
and the Web Backend. Contains:
  - get_finger_states()  : maps MediaPipe landmarks → [thumb, index, middle, ring, pinky]
  - detect_gesture()     : maps finger states + custom patterns → gesture name + confidence
"""
import math


def get_distance(p1, p2) -> float:
    """Euclidean distance between two MediaPipe landmarks."""
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)


def get_finger_states(lm, handedness: str = "Right") -> list[int]:
    """
    Determine which fingers are extended (1) or curled (0).

    Thumb  → X-axis comparison with a 0.01 deadband to avoid noise.
    Others → tip Y must be clearly above its PIP joint (−0.01 margin).

    Returns a list of 5 ints: [thumb, index, middle, ring, pinky]
    """
    # Thumb: sideways extension detected via X coordinate
    if handedness == "Right":
        thumb = 1 if lm[4].x < lm[3].x - 0.01 else 0
    else:
        thumb = 1 if lm[4].x > lm[3].x + 0.01 else 0

    fingers = [thumb]

    # Index, Middle, Ring, Pinky: tip above PIP joint
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        fingers.append(1 if lm[tip].y < lm[pip].y - 0.01 else 0)

    return fingers


def detect_gesture(lm, fingers: list[int], custom_patterns: dict = None) -> tuple[str, float]:
    """
    Map finger states and optional custom fingerprint patterns to a gesture name.

    Args:
        lm:              MediaPipe hand landmark list
        fingers:         Output of get_finger_states()
        custom_patterns: Dict of {binary_pattern_str: mapping_dict} for user-defined gestures

    Returns:
        (gesture_name, confidence) — gesture_name is "none" when unrecognised
    """
    t, i, m, r, p = fingers

    # ── Computed flags ───────────────────────────────────────────────────────
    pinch_dist = get_distance(lm[4], lm[8])
    is_pinch   = pinch_dist < 0.07
    # OK sign: pinch + middle/ring/pinky all extended
    is_ok      = is_pinch and m == 1 and r == 1 and p == 1
    # Shaka (hang loose): thumb + pinky only
    is_shaka   = t == 1 and i == 0 and m == 0 and r == 0 and p == 1

    # ── Custom fingerprint match (checked first so user can override) ─────
    if custom_patterns:
        pattern = "".join(str(f) for f in fingers)
        if pattern in custom_patterns:
            return pattern, 0.95

    # ── Named built-in gestures ───────────────────────────────────────────
    if is_ok:
        return "ok_sign", 0.97

    # Pinch only when middle/ring are NOT extended (avoids ok_sign ambiguity)
    if is_pinch and not (m == 1 or r == 1):
        return "pinch", 0.95

    if is_shaka:
        return "shaka", 0.96

    # Fist: all four fingers curled (thumb excluded — X-axis reading is unreliable)
    if i == 0 and m == 0 and r == 0 and p == 0:
        return "fist", 0.97

    # Open palm: all four fingers extended (thumb excluded)
    if i == 1 and m == 1 and r == 1 and p == 1:
        return "open_palm", 0.97

    # Index finger only
    if i == 1 and m == 0 and r == 0 and p == 0:
        return "index", 0.96

    # Peace sign: index + middle
    if i == 1 and m == 1 and r == 0 and p == 0:
        return "peace", 0.95

    # Three fingers: index + middle + ring
    if i == 1 and m == 1 and r == 1 and p == 0:
        return "three_fingers", 0.94

    # Rock-on / horns: index + pinky (good for "Next" — rarely done accidentally)
    if i == 1 and m == 0 and r == 0 and p == 1:
        return "index_pinky", 0.95

    # Thumb only: compare thumb tip Y against wrist (lm[0]) for up/down
    if t == 1 and i == 0 and m == 0 and r == 0 and p == 0:
        return ("thumb_up", 0.96) if lm[4].y < lm[0].y else ("thumb_down", 0.95)

    return "none", 0.0
