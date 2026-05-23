"""
core/gesture_engine.py
======================
Hand tracking and gesture detection using MediaPipe Hands.
Single source of truth — no more duplication across files.

ML Integration
--------------
If model/gesture_model.pkl exists (trained by model/train_model.py),
the engine will use the Random Forest classifier instead of the
built-in rule-based logic.  Falls back automatically if no model is found.
"""

import math
import os
from pathlib import Path
import numpy as np
import mediapipe as mp

# Optional ML imports — silently ignored if scikit-learn/joblib not installed
try:
    import joblib
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False

_MODEL_PATH = Path(__file__).parent.parent / "model" / "gesture_model.pkl"


class GestureEngine:
    """Wraps MediaPipe Hands and provides clean gesture detection API."""

    # Gestures that are reserved for mouse control mode
    MOUSE_GESTURES = frozenset({
        "index", "pinch", "peace", "three_fingers", "ok_sign",
        "thumb_up", "thumb_down", "index_pinky",
    })

    def __init__(
        self,
        max_hands: int = 1,
        detection_conf: float = 0.75,
        tracking_conf: float = 0.75,
        use_ml: bool = True,
    ):
        self._use_ml = use_ml and _ML_AVAILABLE
        self.mp_hands = mp.solutions.hands
        self.mp_draw  = mp.solutions.drawing_utils
        self.hands    = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=detection_conf,
            min_tracking_confidence=tracking_conf,
        )
        # Custom fingerprint patterns loaded from config
        self._custom_patterns: set[str] = set()

        # ML model (loaded lazily)
        self._ml_clf    = None
        self._ml_le     = None
        self._ml_loaded = False
        if self._use_ml:
            self._load_ml_model()

    def set_custom_patterns(self, custom: dict) -> None:
        """Register custom gesture fingerprints (5-digit binary keys)."""
        self._custom_patterns = set(custom.keys())

    def set_use_ml(self, enabled: bool) -> None:
        """Toggle ML model on/off at runtime (from Settings page)."""
        self._use_ml = enabled and _ML_AVAILABLE
        if self._use_ml and not self._ml_loaded:
            self._load_ml_model()

    def is_ml_active(self) -> bool:
        """True if ML model is loaded and currently in use."""
        return self._use_ml and self._ml_clf is not None

    def _load_ml_model(self) -> None:
        """Load the trained RandomForest model from disk (silent on failure)."""
        try:
            if _MODEL_PATH.exists() and _ML_AVAILABLE:
                payload        = joblib.load(_MODEL_PATH)
                self._ml_clf   = payload["model"]
                self._ml_le    = payload["label_encoder"]
                self._ml_loaded = True
                print(f"[GestureEngine] ML model loaded from {_MODEL_PATH}")
            else:
                self._ml_loaded = False
        except Exception as e:
            print(f"[GestureEngine] ML model load failed: {e} — using rule-based")
            self._ml_loaded = False

    @staticmethod
    def _normalize_lm(lm) -> np.ndarray:
        """Flatten & normalize 21 landmarks (wrist=origin, scale=max dist)."""
        pts = np.array([[p.x, p.y, p.z] for p in lm], dtype=np.float32)
        pts -= pts[0]                                   # translate to wrist
        scale = np.max(np.linalg.norm(pts, axis=1)) + 1e-9
        pts /= scale
        return pts.flatten().reshape(1, -1)             # (1, 63)

    def process(self, rgb_frame):
        """Run MediaPipe inference on an RGB frame."""
        return self.hands.process(rgb_frame)

    # ── Finger State Detection ─────────────────────────────────────────────────

    def finger_states(self, lm, handedness: str = "Right") -> list:
        """
        Return [thumb, index, middle, ring, pinky] as 1=up / 0=down.
        Thumb uses X-axis comparison; others compare tip Y vs PIP joint Y.
        A small deadband of 0.01 is applied to reduce noise jitter.
        """
        if handedness == "Right":
            thumb = 1 if lm[4].x < lm[3].x - 0.01 else 0
        else:
            thumb = 1 if lm[4].x > lm[3].x + 0.01 else 0

        fingers = [thumb]
        for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
            fingers.append(1 if lm[tip].y < lm[pip].y - 0.01 else 0)
        return fingers

    # ── Geometry ──────────────────────────────────────────────────────────────

    @staticmethod
    def dist(p1, p2) -> float:
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

    # ── Gesture Classification ────────────────────────────────────────────────

    def detect(self, lm, fingers: list) -> tuple:
        """
        Classify the current hand pose.
        Returns (gesture_name: str, confidence: float).

        Priority order:
          1. Custom fingerprint patterns (user-defined)
          2. ML model (if loaded and use_ml=True)
          3. Rule-based logic (always available as fallback)
        """
        t, i, m, r, p = fingers

        pinch_dist = self.dist(lm[4], lm[8])
        is_pinch   = pinch_dist < 0.07
        is_ok      = pinch_dist < 0.07 and m == 1 and r == 1 and p == 1
        is_shaka   = t == 1 and i == 0 and m == 0 and r == 0 and p == 1

        # 1. Custom fingerprint takes priority (always)
        pattern = "".join(str(f) for f in fingers)
        if pattern in self._custom_patterns:
            return pattern, 0.95

        # 2. ML model path
        if self._use_ml and self._ml_clf is not None:
            try:
                X      = self._normalize_lm(lm)
                label  = self._ml_le.inverse_transform(self._ml_clf.predict(X))[0]
                proba  = self._ml_clf.predict_proba(X).max()
                if label != "none" and proba > 0.65:
                    return label, float(proba)
            except Exception:
                pass  # silent fallback to rules

        # 3. Rule-based fallback
        if is_ok:                                      return "ok_sign",       0.97
        if is_pinch and not (m or r):                  return "pinch",         0.95
        if is_shaka:                                   return "shaka",         0.96
        if i == 0 and m == 0 and r == 0 and p == 0:   return "fist",          0.97
        if i == 1 and m == 1 and r == 1 and p == 1:   return "open_palm",     0.97
        if i == 1 and m == 0 and r == 0 and p == 0:   return "index",         0.96
        if i == 1 and m == 1 and r == 0 and p == 0:   return "peace",         0.95
        if i == 1 and m == 1 and r == 1 and p == 0:   return "three_fingers", 0.94
        if i == 1 and m == 0 and r == 0 and p == 1:   return "index_pinky",   0.95

        if t == 1 and i == 0 and m == 0 and r == 0 and p == 0:
            return ("thumb_up", 0.96) if lm[4].y < lm[0].y else ("thumb_down", 0.95)

        return "none", 0.0

    def draw_landmarks(self, frame, hand_lm) -> None:
        """Overlay hand skeleton on a BGR frame in-place."""
        self.mp_draw.draw_landmarks(
            frame, hand_lm, self.mp_hands.HAND_CONNECTIONS
        )
