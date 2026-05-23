"""
ui/pages/settings.py
====================
Settings page: camera index, EMA smoothing, camera resolution,
AI Mode (Gemini/Local), Voice Control, Accessibility, and Hand Calibration.
Changes are saved immediately via callbacks.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSpinBox, QSlider, QComboBox,
    QScrollArea, QLineEdit, QCheckBox, QMessageBox,
    QProgressDialog, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui  import QFont, QPixmap, QImage

from ui.theme import (
    BG2, BG3, CARD, ACCENT, ACCENT2, GREEN, ORANGE, RED,
    WHITE, MUTED, BORDER, TEXT,
)


class SettingsPage(QWidget):
    """
    Callbacks
    ---------
    on_cam_change(index: int)           – camera index changed
    on_ema_change(alpha: float)         – smoothing changed (live)
    on_resolution_change(w, h)          – resolution changed (requires camera restart)
    on_ai_mode_change(key: str)         – Gemini API key changed (empty = local)
    on_voice_toggle(enabled: bool)      – voice control toggled
    on_ml_toggle(enabled: bool)         – ML model toggle changed
    on_high_contrast(enabled: bool)     – high contrast mode toggled
    on_calibrate()                      – launch calibration wizard
    """

    RESOLUTIONS = [
        ("640 × 480  (default)", 640, 480),
        ("1280 × 720  (HD)",     1280, 720),
        ("320 × 240  (low)",     320, 240),
    ]

    def __init__(
        self,
        cfg: dict,
        on_cam_change=None,
        on_ema_change=None,
        on_resolution_change=None,
        on_ai_mode_change=None,
        on_voice_toggle=None,
        on_ml_toggle=None,
        on_high_contrast=None,
        on_calibrate=None,
        parent=None,
    ):
        super().__init__(parent)
        self._cfg                  = cfg
        self._on_cam_change        = on_cam_change
        self._on_ema_change        = on_ema_change
        self._on_resolution_change = on_resolution_change
        self._on_ai_mode_change    = on_ai_mode_change
        self._on_voice_toggle      = on_voice_toggle
        self._on_ml_toggle         = on_ml_toggle
        self._on_high_contrast     = on_high_contrast
        self._on_calibrate         = on_calibrate
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(20)

        lay.addWidget(self._section_title("⚙️  Settings"))

        lay.addWidget(self._build_camera_card())
        lay.addWidget(self._build_smoothing_card())
        lay.addWidget(self._build_resolution_card())
        lay.addWidget(self._build_ai_mode_card())       # Feature 4
        lay.addWidget(self._build_ml_card())             # Feature 1
        lay.addWidget(self._build_voice_card())          # Feature 5
        lay.addWidget(self._build_calibration_card())    # Feature 9
        lay.addWidget(self._build_accessibility_card())  # Feature 8
        lay.addWidget(self._build_mouse_tips_card())
        lay.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll)

    # ── Existing Cards ────────────────────────────────────────────────────────

    def _build_camera_card(self) -> QFrame:
        s = self._cfg.get("settings", {})
        cam_idx = s.get("camera_index", 0)

        f, lay = self._card("📷  Camera")
        lay.addWidget(self._desc(
            "Camera index to use. 0 = default webcam. Try 1 or 2 if you have multiple."
        ))

        row = QHBoxLayout()
        row.setSpacing(12)

        self._cam_spin = QSpinBox()
        self._cam_spin.setRange(0, 9)
        self._cam_spin.setValue(cam_idx)
        self._cam_spin.setFixedWidth(90)

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("primary")
        apply_btn.setFixedWidth(100)
        apply_btn.clicked.connect(self._apply_cam)

        row.addWidget(QLabel("Camera Index:"))
        row.addWidget(self._cam_spin)
        row.addWidget(apply_btn)
        row.addStretch()
        lay.addLayout(row)

        self._cam_status = QLabel("")
        self._cam_status.setFont(QFont("Segoe UI", 9))
        self._cam_status.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(self._cam_status)
        return f

    def _build_smoothing_card(self) -> QFrame:
        s = self._cfg.get("settings", {})
        ema = s.get("ema_alpha", 0.7)

        f, lay = self._card("🖱  Air Mouse Smoothing")
        lay.addWidget(self._desc(
            "Controls how smooth the cursor movement is. "
            "Higher = smoother but slower. Lower = faster but jittery.\n"
            "Range: 0.1 (raw) → 0.95 (very smooth)"
        ))

        row = QHBoxLayout()
        row.setSpacing(14)

        self._ema_slider = QSlider(Qt.Orientation.Horizontal)
        self._ema_slider.setRange(10, 95)
        self._ema_slider.setValue(int(ema * 100))
        self._ema_slider.setFixedWidth(260)

        self._ema_val_lbl = QLabel(f"{ema:.2f}")
        self._ema_val_lbl.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        self._ema_val_lbl.setStyleSheet(f"color: {ACCENT};")
        self._ema_val_lbl.setFixedWidth(44)

        self._ema_slider.valueChanged.connect(self._on_ema_changed)

        row.addWidget(QLabel("Alpha:"))
        row.addWidget(self._ema_slider)
        row.addWidget(self._ema_val_lbl)
        row.addStretch()
        lay.addLayout(row)
        return f

    def _build_resolution_card(self) -> QFrame:
        s = self._cfg.get("settings", {})
        w = s.get("width", 640)
        h = s.get("height", 480)

        f, lay = self._card("🎥  Camera Resolution")
        lay.addWidget(self._desc(
            "Resolution for the camera feed. Higher resolutions improve detection "
            "accuracy but require more CPU. Requires camera restart to apply."
        ))

        row = QHBoxLayout()
        row.setSpacing(12)

        self._res_combo = QComboBox()
        self._res_combo.setFixedWidth(210)
        cur_idx = 0
        for i, (label, rw, rh) in enumerate(self.RESOLUTIONS):
            self._res_combo.addItem(label)
            if rw == w and rh == h:
                cur_idx = i
        self._res_combo.setCurrentIndex(cur_idx)

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("primary")
        apply_btn.setFixedWidth(100)
        apply_btn.clicked.connect(self._apply_resolution)

        row.addWidget(QLabel("Resolution:"))
        row.addWidget(self._res_combo)
        row.addWidget(apply_btn)
        row.addStretch()
        lay.addLayout(row)
        return f

    # ── New Feature Cards ─────────────────────────────────────────────────────

    def _build_ai_mode_card(self) -> QFrame:
        """Feature 4 — AI Mode (Local vs Gemini LLM)."""
        f, lay = self._card("🤖  AI Assistant Mode")
        lay.addWidget(self._desc(
            "By default the AI Assistant runs fully offline (rule-based).\n"
            "Enter a Google Gemini API key to enable natural language responses.\n"
            "Get a free key at: aistudio.google.com"
        ))

        import os
        existing_key = self._cfg.get("settings", {}).get("gemini_api_key", "")

        key_row = QHBoxLayout()
        key_row.setSpacing(10)
        key_row.addWidget(QLabel("Gemini API Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("AIza… (leave empty for offline mode)")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setText(existing_key)
        self._api_key_input.setFixedHeight(38)
        key_row.addWidget(self._api_key_input, 1)

        apply_key_btn = QPushButton("Apply")
        apply_key_btn.setObjectName("primary")
        apply_key_btn.setFixedWidth(90)
        apply_key_btn.clicked.connect(self._apply_ai_key)
        key_row.addWidget(apply_key_btn)
        lay.addLayout(key_row)

        self._ai_status_lbl = QLabel("Mode: Local (offline)")
        self._ai_status_lbl.setFont(QFont("Segoe UI", 9))
        if existing_key:
            self._ai_status_lbl.setText("Mode: Gemini LLM ✅")
            self._ai_status_lbl.setStyleSheet(f"color: {GREEN};")
        else:
            self._ai_status_lbl.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(self._ai_status_lbl)
        return f

    def _build_ml_card(self) -> QFrame:
        """Feature 1 — ML vs Rule-Based gesture detection."""
        from pathlib import Path
        model_exists = (Path(__file__).parent.parent.parent / "model" / "gesture_model.pkl").exists()

        f, lay = self._card("🧠  Gesture Detection Mode")
        desc_text = (
            "Choose how gestures are classified:\n"
            "• Rule-Based (default): fast, always available\n"
            "• ML Model: uses your trained Random Forest for higher accuracy\n\n"
        )
        if model_exists:
            desc_text += "✅ gesture_model.pkl found — ML mode is available."
        else:
            desc_text += "⚠ No trained model found. Run model/train_model.py first."
        lay.addWidget(self._desc(desc_text))

        s = self._cfg.get("settings", {})
        use_ml = s.get("use_ml_model", False) and model_exists

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(QLabel("Detection:"))

        self._ml_combo = QComboBox()
        self._ml_combo.addItem("Rule-Based (always available)")
        self._ml_combo.addItem("ML Model (requires trained model)")
        self._ml_combo.setCurrentIndex(1 if use_ml else 0)
        self._ml_combo.setEnabled(model_exists)
        self._ml_combo.setFixedWidth(260)
        self._ml_combo.currentIndexChanged.connect(self._on_ml_changed)
        row.addWidget(self._ml_combo)
        row.addStretch()
        lay.addLayout(row)

        if not model_exists:
            hint = QLabel("💡 Run: python model/train_model.py")
            hint.setFont(QFont("Courier New", 9))
            hint.setStyleSheet(f"color: {ORANGE};")
            lay.addWidget(hint)
        return f

    def _build_voice_card(self) -> QFrame:
        """Feature 5 — Voice Control."""
        f, lay = self._card("🎤  Voice Control")
        lay.addWidget(self._desc(
            "Enable voice commands alongside hand gestures.\n"
            "Say commands like: 'pause', 'next', 'volume up', 'open youtube'\n"
            "Requires internet connection (Google Web Speech API).\n"
            "Packages needed: SpeechRecognition, pyaudio"
        ))

        s = self._cfg.get("settings", {})
        voice_enabled = s.get("voice_enabled", False)

        row = QHBoxLayout()
        row.setSpacing(14)
        self._voice_check = QCheckBox("Enable Voice Control")
        self._voice_check.setChecked(voice_enabled)
        self._voice_check.setFont(QFont("Segoe UI", 11))
        self._voice_check.stateChanged.connect(self._on_voice_changed)
        row.addWidget(self._voice_check)
        row.addStretch()
        lay.addLayout(row)

        self._voice_status_lbl = QLabel("Voice: OFF")
        self._voice_status_lbl.setFont(QFont("Segoe UI", 9))
        color = GREEN if voice_enabled else MUTED
        self._voice_status_lbl.setStyleSheet(f"color: {color};")
        lay.addWidget(self._voice_status_lbl)

        # Microphone selector
        try:
            from core.voice_assistant import list_microphones
            mics = list_microphones()
        except Exception:
            mics = []

        if mics:
            mic_row = QHBoxLayout()
            mic_row.setSpacing(10)
            mic_row.addWidget(QLabel("Microphone:"))
            self._mic_combo = QComboBox()
            self._mic_combo.addItem("Default", -1)
            for idx, name in mics[:8]:
                self._mic_combo.addItem(name[:50], idx)
            self._mic_combo.setFixedWidth(280)
            mic_row.addWidget(self._mic_combo)
            mic_row.addStretch()
            lay.addLayout(mic_row)
        return f

    def _build_calibration_card(self) -> QFrame:
        """Feature 9 — Per-User Hand Calibration."""
        f, lay = self._card("✋  Hand Calibration")
        s = self._cfg.get("calibration", {})
        is_calibrated = s.get("calibrated", False)

        desc = (
            "Calibrate detection thresholds to your specific hand shape and size.\n"
            "The 30-second calibration sequence asks you to hold 4 poses.\n"
            "This improves pinch detection and reduces false positives."
        )
        if is_calibrated:
            ts = s.get("timestamp", "unknown")
            desc += f"\n\n✅ Last calibrated: {ts}"
        lay.addWidget(self._desc(desc))

        row = QHBoxLayout()
        row.setSpacing(12)

        cal_btn = QPushButton("🔧  Calibrate My Hand")
        cal_btn.setObjectName("primary")
        cal_btn.setFixedHeight(42)
        cal_btn.setFixedWidth(200)
        cal_btn.clicked.connect(self._start_calibration)
        row.addWidget(cal_btn)

        if is_calibrated:
            reset_btn = QPushButton("Reset")
            reset_btn.setFixedHeight(42)
            reset_btn.clicked.connect(self._reset_calibration)
            row.addWidget(reset_btn)

        row.addStretch()
        lay.addLayout(row)
        return f

    def _build_accessibility_card(self) -> QFrame:
        """Feature 8 — Accessibility Mode."""
        f, lay = self._card("♿  Accessibility")
        lay.addWidget(self._desc(
            "High Contrast Mode uses pure black/white with bright yellow accents\n"
            "for maximum readability. Also increases button sizes and border widths."
        ))

        s = self._cfg.get("settings", {})
        hc = s.get("high_contrast", False)

        row = QHBoxLayout()
        row.setSpacing(14)
        self._hc_check = QCheckBox("High Contrast Mode")
        self._hc_check.setChecked(hc)
        self._hc_check.setFont(QFont("Segoe UI", 11))
        self._hc_check.stateChanged.connect(self._on_hc_changed)
        row.addWidget(self._hc_check)
        row.addStretch()
        lay.addLayout(row)

        self._hc_status = QLabel("High contrast: OFF" if not hc else "High contrast: ON ✅")
        self._hc_status.setFont(QFont("Segoe UI", 9))
        self._hc_status.setStyleSheet(f"color: {GREEN if hc else MUTED};")
        lay.addWidget(self._hc_status)
        return f

    def _build_mouse_tips_card(self) -> QFrame:
        f, lay = self._card("💡  Air Mouse Cheat Sheet")
        tips = [
            ("☝  Index Finger",   "Move cursor — raise index, rest down"),
            ("🤏  Pinch",         "Left-click / Drag — pinch thumb + index"),
            ("✌  Peace Sign",     "Right-click"),
            ("👌  OK Sign",        "Double-click"),
            ("🤟  Three Fingers",  "Scroll — move hand up/down"),
        ]
        for gesture, action in tips:
            row = QHBoxLayout()
            row.setSpacing(16)
            g_lbl = QLabel(gesture)
            g_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            g_lbl.setStyleSheet(f"color: {ACCENT};")
            g_lbl.setFixedWidth(160)
            a_lbl = QLabel(action)
            a_lbl.setFont(QFont("Segoe UI", 10))
            a_lbl.setStyleSheet(f"color: {TEXT};")
            row.addWidget(g_lbl)
            row.addWidget(a_lbl)
            row.addStretch()
            lay.addLayout(row)
        return f

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _card(self, title: str):
        """Return (QFrame, inner_QVBoxLayout)."""
        f = QFrame()
        f.setStyleSheet(f"""
            QFrame {{
                background: {CARD};
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
        """)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lay.addWidget(t)
        return f, lay

    @staticmethod
    def _section_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {WHITE};")
        return lbl

    @staticmethod
    def _desc(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet(f"color: {MUTED};")
        lbl.setWordWrap(True)
        return lbl

    # ── Slots — Existing ──────────────────────────────────────────────────────

    def _apply_cam(self):
        idx = self._cam_spin.value()
        self._cfg.setdefault("settings", {})["camera_index"] = idx
        if self._on_cam_change:
            self._on_cam_change(idx)
        self._cam_status.setText(f"✓ Camera set to index {idx} — restart tracking to apply.")
        self._cam_status.setStyleSheet(f"color: {GREEN};")

    def _on_ema_changed(self, v: int):
        alpha = v / 100.0
        self._ema_val_lbl.setText(f"{alpha:.2f}")
        self._cfg.setdefault("settings", {})["ema_alpha"] = alpha
        if self._on_ema_change:
            self._on_ema_change(alpha)

    def _apply_resolution(self):
        idx = self._res_combo.currentIndex()
        _, rw, rh = self.RESOLUTIONS[idx]
        self._cfg.setdefault("settings", {}).update({"width": rw, "height": rh})
        if self._on_resolution_change:
            self._on_resolution_change(rw, rh)

    # ── Slots — New Features ──────────────────────────────────────────────────

    def _apply_ai_key(self):
        key = self._api_key_input.text().strip()
        self._cfg.setdefault("settings", {})["gemini_api_key"] = key
        if self._on_ai_mode_change:
            self._on_ai_mode_change(key)
        if key:
            self._ai_status_lbl.setText("Mode: Gemini LLM ✅  (restart app to apply)")
            self._ai_status_lbl.setStyleSheet(f"color: {GREEN};")
        else:
            self._ai_status_lbl.setText("Mode: Local (offline)")
            self._ai_status_lbl.setStyleSheet(f"color: {MUTED};")

    def _on_ml_changed(self, idx: int):
        use_ml = idx == 1
        self._cfg.setdefault("settings", {})["use_ml_model"] = use_ml
        if self._on_ml_toggle:
            self._on_ml_toggle(use_ml)

    def _on_voice_changed(self, state: int):
        enabled = state == Qt.CheckState.Checked.value
        self._cfg.setdefault("settings", {})["voice_enabled"] = enabled
        self._voice_status_lbl.setText("Voice: ON 🎤" if enabled else "Voice: OFF")
        self._voice_status_lbl.setStyleSheet(f"color: {GREEN if enabled else MUTED};")
        if self._on_voice_toggle:
            self._on_voice_toggle(enabled)

    def _on_hc_changed(self, state: int):
        enabled = state == Qt.CheckState.Checked.value
        self._cfg.setdefault("settings", {})["high_contrast"] = enabled
        self._hc_status.setText("High contrast: ON ✅" if enabled else "High contrast: OFF")
        self._hc_status.setStyleSheet(f"color: {GREEN if enabled else MUTED};")
        if self._on_high_contrast:
            self._on_high_contrast(enabled)

    def _start_calibration(self):
        if self._on_calibrate:
            self._on_calibrate()

    def _reset_calibration(self):
        self._cfg.pop("calibration", None)
        QMessageBox.information(
            self, "Calibration Reset",
            "Hand calibration has been reset to defaults.\n"
            "Click 'Calibrate My Hand' to recalibrate."
        )
