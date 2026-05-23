"""
ui/pages/dashboard.py
=====================
Main dashboard: gesture reference on the LEFT, live camera feed in the CENTER,
gesture status panel on the RIGHT.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui  import QFont, QPixmap, QImage, QColor, QPainter, QBrush, QLinearGradient, QPen

from ui.theme          import (
    BG, BG2, BG3, CARD, ACCENT, ACCENT2, GREEN, ORANGE, RED,
    WHITE, MUTED, BORDER, TEXT,
)
from ui.widgets.finger_bar import FingerBar


# ── All gesture definitions (icon, name, description) ────────────────────────

GESTURE_LIST = [
    ("fist",          "✊", "Fist",              "Close all fingers"),
    ("open_palm",     "🖐", "Open Palm",          "All fingers extended"),
    ("index",         "☝", "Index Finger",       "Point with 1 finger"),
    ("peace",         "✌", "Peace Sign",         "Index + middle up"),
    ("three_fingers", "🤟", "Three Fingers",      "Index + middle + ring"),
    ("thumb_up",      "👍", "Thumb Up",           "Thumb pointing up"),
    ("thumb_down",    "👎", "Thumb Down",         "Thumb pointing down"),
    ("pinch",         "🤏", "Pinch",              "Thumb + index touch"),
    ("ok_sign",       "👌", "OK Sign",            "Pinch + other 3 up"),
    ("shaka",         "🤙", "Shaka",              "Thumb + pinky only"),
    ("index_pinky",   "🤘", "Rock On (Next)",     "Index + pinky up"),
]

MOUSE_LABELS = {
    "index":         "Move cursor",
    "pinch":         "Left click",
    "peace":         "Right click",
    "ok_sign":       "Double click",
    "three_fingers": "Scroll",
    "thumb_up":      "Scroll up",
    "thumb_down":    "Scroll down",
    "index_pinky":   "Next →",
}


# ── Cooldown progress bar ─────────────────────────────────────────────────────

class _CooldownBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0   # 1.0 = full cooldown, 0.0 = ready
        self._cooling  = False
        self.setFixedHeight(7)

    def set_cooldown(self, remaining: float, total: float):
        self._progress = (remaining / total) if total > 0 else 0.0
        self._cooling  = remaining > 0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setBrush(QBrush(QColor(BORDER)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 3, 3)

        fill = int(w * (1 - self._progress))
        if fill > 0:
            col = QColor(ORANGE if self._cooling else GREEN)
            p.setBrush(QBrush(col))
            p.drawRoundedRect(0, 0, fill, h, 3, 3)


# ── Dwell progress bar ────────────────────────────────────────────────────────

class _DwellBar(QWidget):
    """Shows how close a gesture is to passing the dwell threshold (0–1)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._frac = 0.0
        self.setFixedHeight(5)

    def set_frac(self, frac: float):
        self._frac = max(0.0, min(1.0, frac))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.setBrush(QBrush(QColor(BORDER)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 2, 2)

        fill = int(w * self._frac)
        if fill > 0:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor(ACCENT))
            grad.setColorAt(1.0, QColor("#7c3aed"))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(0, 0, fill, h, 2, 2)


# ── Gesture reference row ─────────────────────────────────────────────────────

class _GestureRow(QFrame):
    """One row in the left gesture reference panel."""

    _STYLE_IDLE = f"""
        QFrame {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 10px;
        }}
    """
    _STYLE_ACTIVE = f"""
        QFrame {{
            background: rgba(0,229,255,0.10);
            border: 1px solid {ACCENT};
            border-radius: 10px;
        }}
    """

    def __init__(self, gesture_id: str, icon: str, name: str, description: str, parent=None):
        super().__init__(parent)
        self._gesture_id = gesture_id
        self._active = False

        self.setStyleSheet(self._STYLE_IDLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(10)

        # Emoji icon
        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setFont(QFont("Segoe UI Emoji", 20))
        self._icon_lbl.setFixedWidth(36)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._icon_lbl)

        # Text column
        col = QVBoxLayout()
        col.setSpacing(1)

        self._name_lbl = QLabel(name)
        self._name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._name_lbl.setStyleSheet(f"color: {WHITE};")

        self._action_lbl = QLabel("—")
        self._action_lbl.setFont(QFont("Segoe UI", 8))
        self._action_lbl.setStyleSheet(f"color: {MUTED};")
        self._action_lbl.setWordWrap(True)

        col.addWidget(self._name_lbl)
        col.addWidget(self._action_lbl)
        lay.addLayout(col, 1)

        # Active indicator dot (hidden by default)
        self._dot = QLabel("●")
        self._dot.setFont(QFont("Segoe UI", 8))
        self._dot.setStyleSheet(f"color: {ACCENT};")
        self._dot.hide()
        lay.addWidget(self._dot)

    def set_action(self, action_text: str, mouse_mode: bool = False) -> None:
        """Update the action label (called when config changes or mouse mode toggled)."""
        if mouse_mode and self._gesture_id in MOUSE_LABELS:
            self._action_lbl.setText(f"🖱 {MOUSE_LABELS[self._gesture_id]}")
            self._action_lbl.setStyleSheet(f"color: {ACCENT};")
        elif action_text:
            self._action_lbl.setText(action_text)
            self._action_lbl.setStyleSheet(f"color: {MUTED};")
        else:
            self._action_lbl.setText("— no action")
            self._action_lbl.setStyleSheet(f"color: {MUTED};")

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        self.setStyleSheet(self._STYLE_ACTIVE if active else self._STYLE_IDLE)
        self._dot.setVisible(active)
        self._name_lbl.setStyleSheet(f"color: {ACCENT};" if active else f"color: {WHITE};")


# ── Dashboard page ────────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    def __init__(self, on_start, on_stop, on_toggle_mouse, cfg=None, parent=None):
        super().__init__(parent)
        self._on_start        = on_start
        self._on_stop         = on_stop
        self._on_toggle_mouse = on_toggle_mouse
        self._cfg             = cfg or {}
        self._running         = False
        self._mouse_mode      = False
        self._last_cooldown_total = 1.0
        self._active_gesture  = "none"
        self._gesture_rows: dict[str, _GestureRow] = {}
        # Flash animation state
        self._flash_active    = False
        self._flash_timer     = QTimer()
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)
        self._build_ui()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_gesture_ref_panel())        # LEFT
        root.addWidget(self._build_camera_panel(), 3)          # CENTER
        root.addWidget(self._build_status_panel())             # RIGHT

    # ── Left: Gesture Reference Panel ─────────────────────────────────────────

    def _build_gesture_ref_panel(self) -> QFrame:
        outer = QFrame()
        outer.setFixedWidth(220)
        outer.setStyleSheet(f"""
            QFrame {{
                background: {BG2};
                border: 1px solid {BORDER};
                border-radius: 16px;
            }}
        """)
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"""
            QWidget {{
                background: transparent;
                border-bottom: 1px solid {BORDER};
            }}
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(14, 0, 14, 0)

        icon = QLabel("✋")
        icon.setFont(QFont("Segoe UI Emoji", 16))
        title = QLabel("Gesture Guide")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {WHITE}; border: none;")

        h_lay.addWidget(icon)
        h_lay.addWidget(title, 1)
        outer_lay.addWidget(header)

        # Mode badge
        self._mode_badge = QLabel("GESTURE MODE")
        self._mode_badge.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        self._mode_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mode_badge.setFixedHeight(22)
        self._mode_badge.setStyleSheet(f"""
            color: {ACCENT};
            background: rgba(0,229,255,0.08);
            border: none;
            border-bottom: 1px solid {BORDER};
            letter-spacing: 1px;
        """)
        outer_lay.addWidget(self._mode_badge)

        # Scrollable gesture list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._ref_lay = QVBoxLayout(container)
        self._ref_lay.setContentsMargins(8, 8, 8, 8)
        self._ref_lay.setSpacing(3)

        # Build a row for each gesture
        for gid, icon_txt, name, desc in GESTURE_LIST:
            row = _GestureRow(gid, icon_txt, name, desc)
            self._gesture_rows[gid] = row
            self._ref_lay.addWidget(row)

        self._ref_lay.addStretch()
        scroll.setWidget(container)
        outer_lay.addWidget(scroll, 1)

        # Footer tip
        tip = QLabel("Hold gesture 0.35s to trigger")
        tip.setFont(QFont("Segoe UI", 7))
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet(f"""
            color: {MUTED};
            border-top: 1px solid {BORDER};
            padding: 6px;
            border-bottom-left-radius: 16px;
            border-bottom-right-radius: 16px;
        """)
        outer_lay.addWidget(tip)

        # Populate action labels from config
        self._refresh_ref_actions()
        return outer

    def _refresh_ref_actions(self) -> None:
        """Sync the action labels in each gesture row from the live config."""
        from core import config as cfg_mod
        mappings = cfg_mod.all_mappings(self._cfg)
        for gid, row in self._gesture_rows.items():
            mapping = mappings.get(gid, {})
            label = mapping.get("label", "")
            key   = mapping.get("key", "")
            key_t = mapping.get("key_type", "none")

            if key_t == "none" or not key:
                action_str = mapping.get("label", "—")
            elif key_t == "url":
                domain = key.replace("https://", "").replace("http://", "").split("/")[0]
                action_str = f"Open {domain}"
            elif key_t == "type":
                action_str = f'Type: "{key[:14]}…"' if len(key) > 14 else f'Type: "{key}"'
            elif key_t == "hotkey":
                action_str = key.upper()
            else:
                action_str = f"{label}" if label else key

            row.set_action(action_str, mouse_mode=self._mouse_mode)

    # ── Center: Camera Panel ──────────────────────────────────────────────────

    def _build_camera_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {BG2};
                border: 1px solid {BORDER};
                border-radius: 18px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        # Camera feed
        self._feed_lbl = QLabel()
        self._feed_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._feed_lbl.setMinimumSize(420, 320)
        self._feed_lbl.setStyleSheet(f"""
            QLabel {{
                background: {BG3};
                border-radius: 12px;
                border: 2px solid transparent;
                color: {MUTED};
                font-size: 14px;
            }}
        """)
        self._feed_lbl.setText("📷  Camera not started\nClick START TRACKING below")
        lay.addWidget(self._feed_lbl, 1)

        # Control buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._start_btn = QPushButton("▶  START TRACKING")
        self._start_btn.setObjectName("primary")
        self._start_btn.setFixedHeight(46)
        self._start_btn.clicked.connect(self._toggle_tracking)

        self._mouse_btn = QPushButton("🖱  AIR MOUSE: OFF")
        self._mouse_btn.setFixedHeight(46)
        self._mouse_btn.clicked.connect(self._toggle_mouse)

        btn_row.addWidget(self._start_btn, 2)
        btn_row.addWidget(self._mouse_btn, 1)
        lay.addLayout(btn_row)
        return frame

    # ── Right: Status Panel ───────────────────────────────────────────────────

    def _build_status_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(260)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(self._build_gesture_card())
        lay.addWidget(self._build_cooldown_card())
        lay.addWidget(self._build_finger_card())
        lay.addWidget(self._build_mouse_card())
        lay.addStretch()
        return panel

    def _build_gesture_card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(self._card_style())
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        title = self._section_label("CURRENT GESTURE")
        lay.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._gesture_icon = QLabel("—")
        self._gesture_icon.setFont(QFont("Segoe UI Emoji", 34))
        self._gesture_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._gesture_icon)

        self._gesture_name = QLabel("No gesture detected")
        self._gesture_name.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._gesture_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gesture_name.setWordWrap(True)
        lay.addWidget(self._gesture_name)

        self._conf_lbl = QLabel("Confidence: —")
        self._conf_lbl.setFont(QFont("Segoe UI", 9))
        self._conf_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._conf_lbl.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(self._conf_lbl)

        # Dwell hold-to-arm progress bar
        dwell_lbl = QLabel("HOLD PROGRESS")
        dwell_lbl.setFont(QFont("Segoe UI", 7))
        dwell_lbl.setStyleSheet(f"color: {MUTED}; letter-spacing: 1px;")
        dwell_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(dwell_lbl)

        self._dwell_bar = _DwellBar()
        lay.addWidget(self._dwell_bar)
        return f

    def _build_cooldown_card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(self._card_style())
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(5)

        lay.addWidget(self._section_label("COOLDOWN STATUS"))

        self._cd_bar = _CooldownBar()
        lay.addWidget(self._cd_bar)

        self._cd_lbl = QLabel("Ready")
        self._cd_lbl.setFont(QFont("Segoe UI", 10))
        self._cd_lbl.setStyleSheet(f"color: {GREEN};")
        lay.addWidget(self._cd_lbl)
        return f

    def _build_finger_card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(self._card_style())
        lay = QVBoxLayout(f)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(6)

        lay.addWidget(self._section_label("FINGER STATES"))

        self._finger_bar = FingerBar()
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._finger_bar)
        row.addStretch()
        lay.addLayout(row)
        return f

    def _build_mouse_card(self) -> QFrame:
        self._mouse_card = QFrame()
        self._mouse_card.setStyleSheet(self._card_style())
        lay = QHBoxLayout(self._mouse_card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        icon = QLabel("🖱")
        icon.setFont(QFont("Segoe UI Emoji", 18))
        lay.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel("Air Mouse Mode")
        t.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._mouse_desc = QLabel("OFF — gesture keys active")
        self._mouse_desc.setFont(QFont("Segoe UI", 8))
        self._mouse_desc.setStyleSheet(f"color: {MUTED};")
        col.addWidget(t)
        col.addWidget(self._mouse_desc)

        ref = QLabel("☝ Move  •  🤏 Click  •  ✌ R-click\n👌 Dbl  •  🤟 Scroll  •  👍👎 ±Scroll")
        ref.setFont(QFont("Segoe UI", 7))
        ref.setStyleSheet(f"color: {MUTED};")
        ref.setWordWrap(True)
        col.addWidget(ref)

        lay.addLayout(col, 1)
        return self._mouse_card

    # ── Flash animation ───────────────────────────────────────────────────────

    def _trigger_flash(self) -> None:
        """Light up camera border green for 400ms when a gesture fires."""
        if self._flash_active:
            return
        self._flash_active = True
        self._feed_lbl.setStyleSheet(f"""
            QLabel {{
                background: {BG3};
                border-radius: 12px;
                border: 3px solid {GREEN};
                color: {MUTED};
                font-size: 14px;
            }}
        """)
        self._flash_timer.start(400)

    def _clear_flash(self) -> None:
        self._flash_active = False
        self._feed_lbl.setStyleSheet(f"""
            QLabel {{
                background: {BG3};
                border-radius: 12px;
                border: 2px solid transparent;
                color: {MUTED};
                font-size: 14px;
            }}
        """)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _card_style() -> str:
        return f"""
            QFrame {{
                background: {CARD};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
        """

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 7))
        lbl.setStyleSheet(f"color: {MUTED}; letter-spacing: 1px;")
        return lbl

    # ── Toggle Actions ────────────────────────────────────────────────────────

    def _toggle_tracking(self):
        if self._running:
            self._on_stop()
            self._running = False
            self._start_btn.setText("▶  START TRACKING")
            self._start_btn.setObjectName("primary")
            self._feed_lbl.setPixmap(QPixmap())
            self._feed_lbl.setText("📷  Camera stopped\nClick START TRACKING to resume")
        else:
            self._on_start()
            self._running = True
            self._start_btn.setText("⏹  STOP TRACKING")
            self._start_btn.setObjectName("danger")
        self._start_btn.setStyleSheet("")  # Force style refresh

    def _toggle_mouse(self):
        self._mouse_mode = not self._mouse_mode
        self._on_toggle_mouse(self._mouse_mode)
        if self._mouse_mode:
            self._mouse_btn.setText("🖱  AIR MOUSE: ON")
            self._mouse_btn.setObjectName("success")
            self._mouse_desc.setText("ON — index finger moves cursor")
            self._mouse_desc.setStyleSheet(f"color: {GREEN};")
            self._mouse_card.setStyleSheet(f"""
                QFrame {{
                    background: rgba(0,255,136,0.08);
                    border: 1px solid {GREEN};
                    border-radius: 12px;
                }}
            """)
            self._mode_badge.setText("AIR MOUSE MODE")
            self._mode_badge.setStyleSheet(f"""
                color: {GREEN};
                background: rgba(0,255,136,0.08);
                border: none;
                border-bottom: 1px solid {BORDER};
                letter-spacing: 1px;
            """)
        else:
            self._mouse_btn.setText("🖱  AIR MOUSE: OFF")
            self._mouse_btn.setObjectName("")
            self._mouse_desc.setText("OFF — gesture keys active")
            self._mouse_desc.setStyleSheet(f"color: {MUTED};")
            self._mouse_card.setStyleSheet(self._card_style())
            self._mode_badge.setText("GESTURE MODE")
            self._mode_badge.setStyleSheet(f"""
                color: {ACCENT};
                background: rgba(0,229,255,0.08);
                border: none;
                border-bottom: 1px solid {BORDER};
                letter-spacing: 1px;
            """)
        self._mouse_btn.setStyleSheet("")
        # Refresh gesture reference labels to reflect mode
        self._refresh_ref_actions()

    # ── Public Slots ──────────────────────────────────────────────────────────

    def update_frame(self, qimg: QImage) -> None:
        pix = QPixmap.fromImage(qimg)
        self._feed_lbl.setPixmap(
            pix.scaled(
                self._feed_lbl.width(),
                self._feed_lbl.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def update_gesture(
        self,
        name: str,
        conf: float,
        fingers: list,
        cd_left: float,
        mapping: dict,
        dwell_frac: float = 0.0,
    ) -> None:
        # ── Highlight active row in gesture reference ──
        if name != self._active_gesture:
            if self._active_gesture in self._gesture_rows:
                self._gesture_rows[self._active_gesture].set_active(False)
            if name in self._gesture_rows:
                self._gesture_rows[name].set_active(True)
            self._active_gesture = name

        # ── Right panel: icon + label ──
        if name != "none":
            self._gesture_icon.setText(mapping.get("icon", "👋"))
            self._gesture_name.setText(mapping.get("label", name.replace("_", " ").title()))
            self._gesture_name.setStyleSheet(f"color: {ACCENT};")
            self._conf_lbl.setText(f"Confidence: {int(conf * 100)}%")
        else:
            self._gesture_icon.setText("—")
            self._gesture_name.setText("No gesture detected")
            self._gesture_name.setStyleSheet(f"color: {WHITE};")
            self._conf_lbl.setText("Confidence: —")

        # ── Cooldown bar ──
        total = mapping.get("cooldown", self._last_cooldown_total)
        if name != "none":
            self._last_cooldown_total = total
        self._cd_bar.set_cooldown(cd_left, total)
        if cd_left > 0:
            self._cd_lbl.setText(f"Cooling: {cd_left:.1f}s")
            self._cd_lbl.setStyleSheet(f"color: {ORANGE};")
        else:
            self._cd_lbl.setText("Ready")
            self._cd_lbl.setStyleSheet(f"color: {GREEN};")

        # ── Finger states ──
        self._finger_bar.set_fingers(fingers)

        # ── Dwell bar ──
        self._dwell_bar.set_frac(dwell_frac)

        # ── Flash animation: fires when dwell completes ──
        if dwell_frac >= 1.0 and name != "none":
            self._trigger_flash()
