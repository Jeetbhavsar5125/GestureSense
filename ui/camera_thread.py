"""
ui/camera_thread.py
===================
QThread that continuously reads webcam frames, runs gesture detection,
and emits Qt signals to the UI — keeping all blocking I/O off the main thread.

Dwell-time gating
-----------------
A gesture only fires its mapped action after it has been **continuously
detected for at least DWELL_THRESHOLD seconds** (default 0.35 s).
Any frame that returns a different gesture resets the dwell counter.
This prevents brief accidental hand movements from triggering actions.
"""

import cv2
import time
import threading

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui  import QImage

from core.gesture_engine import GestureEngine
from core.mouse_control  import MouseController
from core.executor       import execute


DWELL_THRESHOLD = 0.35   # seconds — gesture must be held this long to fire


class CameraThread(QThread):
    """
    Signals
    -------
    frame_ready(QImage)
        Emitted every ~33 ms with the latest annotated camera frame.

    gesture_ready(str name, float confidence, list fingers, float cooldown_left, float dwell_frac)
        Emitted every frame with the current gesture state.
        dwell_frac: 0.0–1.0, fraction of dwell threshold reached (for UI progress).

    error_occurred(str message)
        Emitted once if the camera cannot be opened.
    """

    frame_ready    = pyqtSignal(QImage)
    gesture_ready  = pyqtSignal(str, float, list, float, float)   # added dwell_frac
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        get_mapping_fn,
        get_last_trigger_fn,
        set_last_trigger_fn,
        cam_index: int = 0,
        ema_alpha: float = 0.7,
        parent=None,
    ):
        super().__init__(parent)
        self._get_mapping       = get_mapping_fn
        self._get_last_trigger  = get_last_trigger_fn
        self._set_last_trigger  = set_last_trigger_fn
        self._cam_index         = cam_index

        self._running     = False
        self._mouse_mode  = False
        self._engine      = GestureEngine()
        self._mouse       = MouseController(ema_alpha=ema_alpha)

        # Dwell-time gating state
        self._dwell_gesture:    str   = "none"
        self._dwell_start:      float = 0.0
        self._dwell_armed:      bool  = False   # True once dwell fired for this hold

    # ── Configuration (safe to call before/between runs) ──────────────────────

    def set_mouse_mode(self, enabled: bool) -> None:
        self._mouse_mode = enabled
        if not enabled:
            self._mouse._reset()

    def set_custom_patterns(self, custom: dict) -> None:
        self._engine.set_custom_patterns(custom)

    def set_cam_index(self, idx: int) -> None:
        self._cam_index = idx

    def set_ema(self, alpha: float) -> None:
        self._mouse.set_ema(alpha)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        self._running = True
        cap = cv2.VideoCapture(self._cam_index)

        if not cap or not cap.isOpened():
            self.error_occurred.emit(
                f"Cannot open camera index {self._cam_index}.\n"
                "Make sure your webcam is connected and not used by another app."
            )
            self._running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res   = self._engine.process(rgb)

            gesture_name  = "none"
            confidence    = 0.0
            fingers       = [0, 0, 0, 0, 0]
            cooldown_left = 0.0
            dwell_frac    = 0.0

            if res.multi_hand_landmarks:
                for hand_lm, hand_info in zip(
                    res.multi_hand_landmarks, res.multi_handedness
                ):
                    self._engine.draw_landmarks(frame, hand_lm)
                    lm         = hand_lm.landmark
                    handedness = hand_info.classification[0].label
                    fingers    = self._engine.finger_states(lm, handedness)
                    gesture_name, confidence = self._engine.detect(lm, fingers)

                    # ── Mouse control (always on leading edge, no dwell needed) ──
                    if self._mouse_mode:
                        self._mouse.update(gesture_name, lm)

                    # ── Dwell-time gating for keyboard actions ────────────────
                    if gesture_name != "none":
                        is_mouse_gesture = gesture_name in GestureEngine.MOUSE_GESTURES

                        if self._mouse_mode and is_mouse_gesture:
                            # Mouse gestures handled above — reset dwell tracker
                            self._reset_dwell()
                        else:
                            now = time.time()

                            # Did the gesture change?
                            if gesture_name != self._dwell_gesture:
                                self._dwell_gesture = gesture_name
                                self._dwell_start   = now
                                self._dwell_armed   = False

                            # How long has this gesture been held?
                            held = now - self._dwell_start
                            dwell_frac = min(held / DWELL_THRESHOLD, 1.0)

                            mapping  = self._get_mapping(gesture_name)
                            cooldown = mapping.get("cooldown", 1.0)
                            elapsed  = now - self._get_last_trigger(gesture_name)
                            cooldown_left = max(0.0, cooldown - elapsed)

                            # Fire only if: dwell satisfied + cooldown elapsed + not already armed
                            if (
                                held >= DWELL_THRESHOLD
                                and elapsed >= cooldown
                                and not self._dwell_armed
                            ):
                                key      = mapping.get("key", "")
                                key_type = mapping.get("key_type", "none")
                                if key and key_type != "none":
                                    threading.Thread(
                                        target=execute,
                                        args=(key, key_type),
                                        daemon=True,
                                    ).start()
                                self._set_last_trigger(gesture_name, now)
                                self._dwell_armed = True   # won't re-fire until released

                    else:
                        # No gesture — reset dwell
                        self._reset_dwell()
                        if self._mouse_mode:
                            self._mouse.update("none", None)

            else:
                self._reset_dwell()
                if self._mouse_mode:
                    self._mouse.update("none", None)

            self.gesture_ready.emit(gesture_name, confidence, fingers, cooldown_left, dwell_frac)

            # Convert annotated BGR frame → Qt image
            rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_out.shape
            qt_img = QImage(
                rgb_out.data, w, h, ch * w,
                QImage.Format.Format_RGB888,
            )
            self.frame_ready.emit(qt_img)

            time.sleep(0.033)   # ~30 FPS

        cap.release()

    def _reset_dwell(self) -> None:
        self._dwell_gesture = "none"
        self._dwell_start   = 0.0
        self._dwell_armed   = False

    def stop(self):
        self._running = False
        self.wait()
