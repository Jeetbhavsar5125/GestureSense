"""
core/mouse_control.py
=====================
Air-finger mouse control using MediaPipe hand landmarks.

Gesture → Action mapping (Air Mouse mode):
  index finger up   →  move cursor (EMA-smoothed)
  pinch             →  left single-click (leading-edge tap)
  peace sign        →  right-click (single-shot)
  ok sign           →  double-click (single-shot)
  three fingers     →  scroll (velocity-based, Y-axis)
  thumb_up          →  scroll up (steady)
  thumb_down        →  scroll down (steady)
  index_pinky       →  next (right arrow key) — handled by executor, not here
"""

import ctypes
from pynput.mouse import Controller, Button


class MouseController:
    def __init__(
        self,
        ema_alpha: float = 0.7,
        x_min: float = 0.15,
        x_max: float = 0.85,
        y_min: float = 0.15,
        y_max: float = 0.85,
    ):
        self.mouse     = Controller()
        self.ema_alpha = ema_alpha
        self.x_min, self.x_max = x_min, x_max
        self.y_min, self.y_max = y_min, y_max
        self.screen_w, self.screen_h = self._screen_size()

        # Internal state
        self.prev_x: float | None        = None
        self.prev_y: float | None        = None
        self.prev_scroll_y: float | None = None

        # Single-shot edge trackers
        self.last_pinch:  bool = False  # left-click
        self.last_peace:  bool = False  # right-click
        self.last_ok:     bool = False  # double-click

        # Drag state (kept for optional drag mode — pinch hold)
        self.is_dragging: bool = False

        # Thumb scroll state
        self.thumb_scroll_tick: int = 0

    # ── Configuration ─────────────────────────────────────────────────────────

    def set_ema(self, alpha: float) -> None:
        self.ema_alpha = max(0.1, min(0.95, alpha))

    @staticmethod
    def _screen_size() -> tuple:
        try:
            u32 = ctypes.windll.user32
            u32.SetProcessDPIAware()
            return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080

    # ── Cursor Movement ───────────────────────────────────────────────────────

    def _move_cursor(self, lm) -> None:
        """Move cursor to EMA-smoothed position of index fingertip (lm[8])."""
        tip = lm[8]
        xs = (tip.x - self.x_min) / max(self.x_max - self.x_min, 1e-6)
        ys = (tip.y - self.y_min) / max(self.y_max - self.y_min, 1e-6)
        xs = max(0.0, min(1.0, xs))
        ys = max(0.0, min(1.0, ys))
        tx = int(xs * self.screen_w)
        ty = int(ys * self.screen_h)

        if self.prev_x is None:
            cx, cy = tx, ty
        else:
            a  = self.ema_alpha
            cx = int(self.prev_x * a + tx * (1 - a))
            cy = int(self.prev_y * a + ty * (1 - a))

        self.mouse.position = (cx, cy)
        self.prev_x, self.prev_y = float(cx), float(cy)

    def _stop_moving(self) -> None:
        self.prev_x = self.prev_y = None

    # ── Main Update ───────────────────────────────────────────────────────────

    def update(self, gesture: str, lm) -> None:
        """
        Called every camera frame.
        gesture : detected gesture name (str)
        lm      : MediaPipe landmark list or None
        """
        if not lm or gesture == "none":
            self._reset()
            return

        # ── 1. Cursor movement — index OR pinch (so cursor is already where
        #        you click when you pinch)
        if gesture in ("index", "pinch"):
            self._move_cursor(lm)
        else:
            self._stop_moving()

        # ── 2. Left single-click — pinch leading edge (tap, not drag)
        is_pinch = gesture == "pinch"
        if is_pinch and not self.last_pinch:
            # Release any drag first then do a clean click
            if self.is_dragging:
                self.mouse.release(Button.left)
                self.is_dragging = False
            self.mouse.click(Button.left, 1)
        self.last_pinch = is_pinch

        # ── 3. Right-click — peace sign leading edge
        is_peace = gesture == "peace"
        if is_peace and not self.last_peace:
            self.mouse.click(Button.right, 1)
        self.last_peace = is_peace

        # ── 4. Double-click — OK sign leading edge
        is_ok = gesture == "ok_sign"
        if is_ok and not self.last_ok:
            self.mouse.click(Button.left, 2)
        self.last_ok = is_ok

        # ── 5. Scroll with three fingers (velocity-based, Y-axis)
        if gesture == "three_fingers":
            tip = lm[8]
            if self.prev_scroll_y is not None:
                dy = tip.y - self.prev_scroll_y
                if abs(dy) > 0.005:
                    self.mouse.scroll(0, -int(dy * 150))
            self.prev_scroll_y = tip.y
        else:
            self.prev_scroll_y = None

        # ── 6. Thumb up/down → steady scroll (every N frames)
        if gesture == "thumb_up":
            self.thumb_scroll_tick += 1
            if self.thumb_scroll_tick % 4 == 0:   # every ~4 frames ≈ 120ms
                self.mouse.scroll(0, 3)
        elif gesture == "thumb_down":
            self.thumb_scroll_tick += 1
            if self.thumb_scroll_tick % 4 == 0:
                self.mouse.scroll(0, -3)
        else:
            self.thumb_scroll_tick = 0

    def _reset(self) -> None:
        """Release any held state when hand disappears."""
        if self.is_dragging:
            self.mouse.release(Button.left)
            self.is_dragging = False
        self.prev_x = self.prev_y = None
        self.prev_scroll_y = None
        self.last_pinch = self.last_peace = self.last_ok = False
        self.thumb_scroll_tick = 0
