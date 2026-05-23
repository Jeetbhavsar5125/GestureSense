"""
core/calibration.py
===================
GestureSense — Per-User Hand Calibration (Feature 9)
Member 1 Responsibility: Dynamic Hand Calibration

Runs a short calibration sequence:
  1. User holds each of 3 reference poses (open palm, fist, index) for 2s each
  2. Records min/max landmark coordinate ranges
  3. Derives calibrated thresholds for finger state detection
  4. Saves calibration data to gestures_config.json

The calibration is used by gesture_engine.py to adjust pinch distance
thresholds and thumb deadband values for each individual user.
"""

import time
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal


class CalibrationThread(QThread):
    """
    Runs calibration in a QThread so the UI stays responsive.

    Signals
    -------
    progress(int step, int total, str instruction)
        Emitted each step with what to do next.
    frame_ready(bytes jpeg_bytes)
        Emitted every ~100ms with the current camera frame.
    finished(dict calibration_data)
        Emitted when calibration completes successfully.
    error(str message)
        Emitted on failure.
    """

    progress    = pyqtSignal(int, int, str)   # step, total, instruction
    frame_ready = pyqtSignal(object)           # QImage
    finished    = pyqtSignal(dict)
    error       = pyqtSignal(str)

    # Calibration steps: (pose_name, emoji, instruction, duration_s)
    STEPS = [
        ("open_palm", "🖐",  "Open your hand fully — spread all fingers wide",  3.0),
        ("fist",      "✊",  "Make a tight fist — curl all fingers",              3.0),
        ("index",     "☝",  "Point with just your index finger",                 3.0),
        ("pinch",     "🤏", "Touch your thumb tip to your index fingertip",      3.0),
    ]

    def __init__(self, cam_index: int = 0, parent=None):
        super().__init__(parent)
        self._cam_index = cam_index
        self._running   = False

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

    def run(self) -> None:
        self._running = True
        mp_hands   = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils
        hands      = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )

        cap = cv2.VideoCapture(self._cam_index)
        if not cap or not cap.isOpened():
            self.error.emit(f"Cannot open camera {self._cam_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        calibration_data: dict = {
            "pinch_threshold":  0.07,   # default
            "thumb_deadband":   0.01,
            "finger_deadband":  0.01,
            "scale_min":        1.0,
            "scale_max":        1.0,
        }

        collected: dict[str, list] = {step[0]: [] for step in self.STEPS}
        total_steps = len(self.STEPS)

        from PyQt6.QtGui import QImage

        for step_idx, (pose, emoji, instruction, duration) in enumerate(self.STEPS):
            if not self._running:
                break

            self.progress.emit(step_idx + 1, total_steps,
                               f"{emoji}  {instruction}")
            deadline = time.time() + duration

            while time.time() < deadline and self._running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                frame = cv2.flip(frame, 1)
                rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res   = hands.process(rgb)

                if res.multi_hand_landmarks:
                    for hand_lm in res.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)
                        lm = hand_lm.landmark
                        # Record raw landmark data
                        pts = np.array([[p.x, p.y, p.z] for p in lm])
                        collected[pose].append(pts)

                # Overlay progress
                remaining = max(0.0, deadline - time.time())
                pct = 1.0 - remaining / duration
                bar_w = int(640 * pct)
                cv2.rectangle(frame, (0, 460), (bar_w, 480), (0, 229, 255), -1)
                cv2.rectangle(frame, (0, 0), (640, 50), (10, 22, 40), -1)
                cv2.putText(frame, f"Step {step_idx+1}/{total_steps}:  {instruction}",
                            (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 229, 255), 2)
                cv2.putText(frame, f"{remaining:.1f}s", (580, 32),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 136), 2)

                rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_out.shape
                qt_img = QImage(rgb_out.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(qt_img)

                time.sleep(0.05)

        cap.release()
        hands.close()

        if not self._running:
            return

        # ── Compute calibration values ────────────────────────────────────────
        # Pinch threshold: average distance between landmark 4 and 8 during pinch pose
        if collected.get("pinch"):
            pinch_dists = []
            for pts in collected["pinch"]:
                d = np.linalg.norm(pts[4] - pts[8])
                pinch_dists.append(d)
            calibration_data["pinch_threshold"] = round(
                float(np.mean(pinch_dists)) * 1.2, 4   # 20% margin
            )

        # Scale range: from open palm vs fist
        if collected.get("open_palm") and collected.get("fist"):
            scales_open = [
                np.max(np.linalg.norm(pts - pts[0], axis=1))
                for pts in collected["open_palm"]
            ]
            scales_fist = [
                np.max(np.linalg.norm(pts - pts[0], axis=1))
                for pts in collected["fist"]
            ]
            calibration_data["scale_min"] = round(float(np.mean(scales_fist)), 4)
            calibration_data["scale_max"] = round(float(np.mean(scales_open)), 4)

        calibration_data["calibrated"] = True
        calibration_data["timestamp"]  = time.strftime("%Y-%m-%dT%H:%M:%S")

        self.finished.emit(calibration_data)


def apply_calibration(engine, calibration: dict) -> None:
    """
    Apply saved calibration data to a GestureEngine instance.
    Called at startup if calibration exists in config.
    """
    if not calibration or not calibration.get("calibrated"):
        return
    # For now: update pinch threshold in the engine's detect() live
    # This is extensible as the engine grows
    threshold = calibration.get("pinch_threshold", 0.07)
    # Monkey-patch the engine's pinch threshold (non-breaking)
    engine._calibrated_pinch_threshold = threshold
    print(f"[Calibration] Applied — pinch threshold: {threshold:.4f}")
