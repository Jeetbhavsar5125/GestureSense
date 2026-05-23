"""
ui/app.py
=========
GestureSense main window.
Layout: fixed left sidebar (navigation) + right stacked pages.
Manages camera thread, voice thread, calibration, config persistence, and system tray.

New in v3.1:
  - Onboarding wizard (first run)
  - Voice control thread (Feature 5)
  - Gemini AI assistant (Feature 4)
  - ML gesture detection toggle (Feature 1)
  - High contrast / accessibility mode (Feature 8)
  - Hand calibration launcher (Feature 9)
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget,
    QSystemTrayIcon, QMenu, QMessageBox, QSizePolicy,
    QDialog, QVBoxLayout as QVBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui  import QFont, QIcon, QPixmap, QColor, QPainter, QImage

from core            import config as cfg_mod
from core.ai_assistant import get_assistant, get_assistant_with_key
from ui.theme        import APP_STYLE, get_stylesheet, BG, BG2, BG3, ACCENT, MUTED, WHITE, BORDER, GREEN
from ui.camera_thread import CameraThread
from ui.widgets.logo  import LogoWidget
from ui.pages.dashboard  import DashboardPage
from ui.pages.gestures   import GesturesPage
from ui.pages.settings   import SettingsPage
from ui.pages.ai_page    import AIPage
from ui.pages.onboarding import OnboardingPage


class GestureSenseApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GestureSense")
        self.setMinimumSize(1080, 680)
        self.resize(1280, 800)

        # ── State ──────────────────────────────────────────────────────────────
        self._cfg          = cfg_mod.load()
        self._last_trigger: dict = {}

        # AI assistant — auto-selects Gemini if key is configured
        api_key = self._cfg.get("settings", {}).get("gemini_api_key", "")
        if api_key:
            self._ai = get_assistant_with_key(api_key)
        else:
            self._ai = get_assistant()   # uses GEMINI_API_KEY env var or local
        self._ai.set_config(self._cfg)

        # ── Camera thread ──────────────────────────────────────────────────────
        s = cfg_mod.get_settings(self._cfg)
        self._cam = CameraThread(
            get_mapping_fn      = self._get_mapping,
            get_last_trigger_fn = lambda g: self._last_trigger.get(g, 0.0),
            set_last_trigger_fn = lambda g, t: self._last_trigger.__setitem__(g, t),
            cam_index           = s.get("camera_index", 0),
            ema_alpha           = s.get("ema_alpha", 0.7),
        )
        self._cam.set_custom_patterns(self._cfg.get("custom", {}))
        self._cam.frame_ready.connect(self._on_frame)
        self._cam.gesture_ready.connect(self._on_gesture)
        self._cam.error_occurred.connect(self._on_error)

        # Apply ML model setting
        use_ml = s.get("use_ml_model", True)
        self._cam._engine.set_use_ml(use_ml)

        # ── Voice thread (Feature 5) ───────────────────────────────────────────
        self._voice_thread = None
        if s.get("voice_enabled", False):
            self._start_voice_thread()

        # ── UI ─────────────────────────────────────────────────────────────────
        hc_mode = s.get("high_contrast", False)
        self.setStyleSheet(get_stylesheet(hc_mode))
        self._build_ui()
        self._setup_tray()

        # ── First-run onboarding ───────────────────────────────────────────────
        if self._cfg.get("first_run", True):
            QTimer.singleShot(100, self._show_onboarding)

    # ── Mapping helper ────────────────────────────────────────────────────────

    def _get_mapping(self, gesture_name: str) -> dict:
        return cfg_mod.all_mappings(self._cfg).get(gesture_name, {})

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_content(), 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(228)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: {BG2};
                border-right: 1px solid {BORDER};
            }}
        """)
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(16, 22, 16, 22)
        lay.setSpacing(4)

        # Logo + title
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo_row.addWidget(LogoWidget(42))

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        t1 = QLabel("GestureSense")
        t1.setFont(QFont("Segoe UI Black", 13, QFont.Weight.Black))
        t1.setStyleSheet(f"color: {WHITE};")
        t2 = QLabel("Hand Gesture Controller")
        t2.setFont(QFont("Segoe UI", 8))
        t2.setStyleSheet(f"color: {MUTED};")
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        logo_row.addLayout(title_col, 1)
        lay.addLayout(logo_row)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER}; margin: 10px 0;")
        lay.addWidget(div)

        # Nav buttons
        self._nav_btns = []
        nav_items = [
            ("🏠", "Dashboard",    0),
            ("✋", "Gestures",     1),
            ("🤖", "AI Assistant", 2),
            ("⚙", "Settings",    3),
        ]
        for icon, label, idx in nav_items:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setObjectName("nav")
            btn.setFixedHeight(44)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _, i=idx: self._navigate(i))
            self._nav_btns.append(btn)
            lay.addWidget(btn)

        lay.addStretch()

        # Voice status indicator
        self._voice_status_dot = QLabel("🎤 Voice: OFF")
        self._voice_status_dot.setFont(QFont("Segoe UI", 8))
        self._voice_status_dot.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(self._voice_status_dot)

        # AI mode indicator
        ai_mode = getattr(self._ai, "mode", "local")
        ai_label = "Gemini AI ✨" if ai_mode == "gemini" else "Local AI"
        self._ai_mode_lbl = QLabel(f"🤖 {ai_label}")
        self._ai_mode_lbl.setFont(QFont("Segoe UI", 8))
        color = GREEN if ai_mode == "gemini" else MUTED
        self._ai_mode_lbl.setStyleSheet(f"color: {color};")
        lay.addWidget(self._ai_mode_lbl)

        # ML status indicator
        ml_active = self._cam._engine.is_ml_active()
        self._ml_lbl = QLabel(f"🧠 {'ML Model' if ml_active else 'Rule-Based'}")
        self._ml_lbl.setFont(QFont("Segoe UI", 8))
        self._ml_lbl.setStyleSheet(f"color: {GREEN if ml_active else MUTED};")
        lay.addWidget(self._ml_lbl)

        # Version footer
        ver = QLabel("v3.1  •  MediaPipe")
        ver.setFont(QFont("Segoe UI", 8))
        ver.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(ver)
        return sidebar

    def _build_content(self) -> QStackedWidget:
        self._stack = QStackedWidget()

        # Dashboard
        self._dashboard = DashboardPage(
            on_start        = self._start_camera,
            on_stop         = self._stop_camera,
            on_toggle_mouse = self._toggle_mouse,
            cfg             = self._cfg,
        )

        # Gestures
        self._gestures_page = GesturesPage(
            cfg                = self._cfg,
            on_action_change   = self._on_action_change,
            on_cooldown_change = self._on_cooldown_change,
            on_add_gesture     = self._on_add_gesture,
            on_delete_gesture  = self._on_delete_gesture,
        )

        # Settings (with all new callbacks)
        self._settings_page = SettingsPage(
            cfg                  = self._cfg,
            on_cam_change        = self._on_cam_change,
            on_ema_change        = self._cam.set_ema,
            on_resolution_change = self._on_resolution_change,
            on_ai_mode_change    = self._on_ai_mode_change,
            on_voice_toggle      = self._on_voice_toggle,
            on_ml_toggle         = self._on_ml_toggle,
            on_high_contrast     = self._on_high_contrast,
            on_calibrate         = self._start_calibration,
        )

        # AI Assistant
        self._ai_page = AIPage(ai=self._ai)

        self._stack.addWidget(self._dashboard)       # 0
        self._stack.addWidget(self._gestures_page)   # 1
        self._stack.addWidget(self._ai_page)          # 2
        self._stack.addWidget(self._settings_page)   # 3

        self._navigate(0)
        return self._stack

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _navigate(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setObjectName("nav_active" if i == idx else "nav")
            btn.setStyleSheet("")   # force Qt to re-evaluate

    # ── Onboarding ────────────────────────────────────────────────────────────

    def _show_onboarding(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("GestureSense — Setup")
        dlg.setMinimumSize(1000, 660)
        dlg.resize(1100, 720)
        dlg.setStyleSheet(self.styleSheet())
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        wizard = OnboardingPage()
        wizard.finished.connect(dlg.accept)
        lay.addWidget(wizard)
        dlg.exec()
        # Mark first run complete
        self._cfg["first_run"] = False
        cfg_mod.save(self._cfg)

    # ── Camera controls ────────────────────────────────────────────────────────

    def _start_camera(self):
        if not self._cam.isRunning():
            s = cfg_mod.get_settings(self._cfg)
            self._cam.set_cam_index(s.get("camera_index", 0))
            self._cam.set_custom_patterns(self._cfg.get("custom", {}))
            self._cam.start()

    def _stop_camera(self):
        if self._cam.isRunning():
            self._cam.stop()

    def _toggle_mouse(self, enabled: bool):
        self._cam.set_mouse_mode(enabled)

    # ── Voice thread ───────────────────────────────────────────────────────────

    def _start_voice_thread(self):
        try:
            from core.voice_assistant import VoiceThread
            self._voice_thread = VoiceThread(on_toggle_mouse=self._toggle_mouse)
            self._voice_thread.status_changed.connect(self._on_voice_status)
            self._voice_thread.command_detected.connect(self._on_voice_command)
            self._voice_thread.error_occurred.connect(self._on_voice_error)
            self._voice_thread.start()
        except Exception as e:
            print(f"[App] Voice thread failed to start: {e}")

    def _stop_voice_thread(self):
        if self._voice_thread and self._voice_thread.isRunning():
            self._voice_thread.stop()
            self._voice_thread = None

    def _on_voice_status(self, status: str):
        icons = {"listening": "🎤 Listening…", "processing": "🎤 Processing…",
                 "idle": "🎤 Voice: ON", "error": "🎤 Error"}
        self._voice_status_dot.setText(icons.get(status, "🎤"))
        color = GREEN if status in ("listening", "idle") else MUTED
        self._voice_status_dot.setStyleSheet(f"color: {color};")

    def _on_voice_command(self, phrase: str, key: str, key_type: str):
        print(f"[App] Voice command: '{phrase}' → {key} ({key_type})")

    def _on_voice_error(self, msg: str):
        print(f"[App] Voice error: {msg}")

    # ── Calibration ───────────────────────────────────────────────────────────

    def _start_calibration(self):
        from core.calibration import CalibrationThread
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle("Hand Calibration")
        dlg.setFixedSize(680, 580)
        dlg.setStyleSheet(self.styleSheet())
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        title = QLabel("✋  Hand Calibration")
        title.setFont(QFont("Segoe UI Black", 16, QFont.Weight.Black))
        lay.addWidget(title)

        self._cal_instruction = QLabel("Preparing…")
        self._cal_instruction.setFont(QFont("Segoe UI", 12))
        self._cal_instruction.setWordWrap(True)
        lay.addWidget(self._cal_instruction)

        self._cal_feed = QLabel()
        self._cal_feed.setFixedSize(640, 420)
        self._cal_feed.setStyleSheet(f"background: {BG2}; border-radius: 10px;")
        self._cal_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._cal_feed)

        s = cfg_mod.get_settings(self._cfg)
        self._cal_thread = CalibrationThread(cam_index=s.get("camera_index", 0))
        self._cal_thread.progress.connect(lambda step, total, msg: (
            self._cal_instruction.setText(f"Step {step}/{total}: {msg}")
        ))
        self._cal_thread.frame_ready.connect(self._on_cal_frame)
        self._cal_thread.finished.connect(lambda data: self._on_calibration_done(data, dlg))
        self._cal_thread.error.connect(lambda msg: QMessageBox.critical(dlg, "Calibration Error", msg))
        self._cal_thread.start()

        dlg.finished.connect(lambda _: self._cal_thread.stop())
        dlg.exec()

    def _on_cal_frame(self, qimg: QImage):
        pix = QPixmap.fromImage(qimg)
        self._cal_feed.setPixmap(
            pix.scaled(640, 420, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        )

    def _on_calibration_done(self, data: dict, dlg: QDialog):
        self._cfg["calibration"] = data
        cfg_mod.save(self._cfg)
        from core.calibration import apply_calibration
        apply_calibration(self._cam._engine, data)
        dlg.accept()
        QMessageBox.information(
            self, "Calibration Complete",
            f"✅ Hand calibrated successfully!\n"
            f"Pinch threshold: {data.get('pinch_threshold', 0.07):.4f}\n"
            f"Timestamp: {data.get('timestamp', '')}"
        )

    # ── Signal handlers ────────────────────────────────────────────────────────

    def _on_frame(self, qimg):
        self._dashboard.update_frame(qimg)

    def _on_gesture(self, name: str, conf: float, fingers: list, cd_left: float, dwell_frac: float):
        mapping = self._get_mapping(name)
        self._dashboard.update_gesture(name, conf, fingers, cd_left, mapping, dwell_frac)
        self._gestures_page.highlight_card(name)

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "Camera Error", msg)

    # ── Config change callbacks ────────────────────────────────────────────────

    def _on_action_change(self, gesture_id: str, key: str, key_type: str):
        if gesture_id in self._cfg.get("mappings", {}):
            self._cfg["mappings"][gesture_id]["key"]      = key
            self._cfg["mappings"][gesture_id]["key_type"] = key_type
        elif gesture_id in self._cfg.get("custom", {}):
            self._cfg["custom"][gesture_id]["key"]      = key
            self._cfg["custom"][gesture_id]["key_type"] = key_type
        cfg_mod.save(self._cfg)

    def _on_cooldown_change(self, gesture_id: str, cooldown: float):
        if gesture_id in self._cfg.get("mappings", {}):
            self._cfg["mappings"][gesture_id]["cooldown"] = cooldown
        elif gesture_id in self._cfg.get("custom", {}):
            self._cfg["custom"][gesture_id]["cooldown"] = cooldown
        cfg_mod.save(self._cfg)

    def _on_add_gesture(self, pattern: str, mapping: dict):
        self._cfg.setdefault("custom", {})[pattern] = mapping
        cfg_mod.save(self._cfg)
        self._cam.set_custom_patterns(self._cfg["custom"])
        self._gestures_page.refresh()

    def _on_delete_gesture(self, gesture_id: str):
        self._cfg.get("custom", {}).pop(gesture_id, None)
        cfg_mod.save(self._cfg)
        self._cam.set_custom_patterns(self._cfg.get("custom", {}))
        self._gestures_page.refresh()

    def _on_cam_change(self, idx: int):
        cfg_mod.save(self._cfg)

    def _on_resolution_change(self, w: int, h: int):
        cfg_mod.save(self._cfg)

    # ── New feature callbacks ──────────────────────────────────────────────────

    def _on_ai_mode_change(self, api_key: str):
        """Reinitialize the AI assistant with new key (takes effect immediately)."""
        cfg_mod.save(self._cfg)
        new_ai = get_assistant_with_key(api_key) if api_key else get_assistant()
        new_ai.set_config(self._cfg)
        self._ai = new_ai
        self._ai_page._ai = new_ai
        mode = getattr(new_ai, "mode", "local")
        label = "Gemini AI ✨" if mode == "gemini" else "Local AI"
        color = GREEN if mode == "gemini" else MUTED
        self._ai_mode_lbl.setText(f"🤖 {label}")
        self._ai_mode_lbl.setStyleSheet(f"color: {color};")
        cfg_mod.save(self._cfg)

    def _on_voice_toggle(self, enabled: bool):
        cfg_mod.save(self._cfg)
        if enabled:
            self._start_voice_thread()
            self._voice_status_dot.setText("🎤 Voice: ON")
            self._voice_status_dot.setStyleSheet(f"color: {GREEN};")
        else:
            self._stop_voice_thread()
            self._voice_status_dot.setText("🎤 Voice: OFF")
            self._voice_status_dot.setStyleSheet(f"color: {MUTED};")

    def _on_ml_toggle(self, enabled: bool):
        self._cam._engine.set_use_ml(enabled)
        ml_active = self._cam._engine.is_ml_active()
        self._ml_lbl.setText(f"🧠 {'ML Model' if ml_active else 'Rule-Based'}")
        self._ml_lbl.setStyleSheet(f"color: {GREEN if ml_active else MUTED};")
        cfg_mod.save(self._cfg)

    def _on_high_contrast(self, enabled: bool):
        self.setStyleSheet(get_stylesheet(enabled))
        cfg_mod.save(self._cfg)

    # ── System Tray ───────────────────────────────────────────────────────────

    def _setup_tray(self):
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        logo = LogoWidget(32)
        logo.render(painter)
        painter.end()

        self._tray = QSystemTrayIcon(QIcon(pix), self)
        menu = QMenu()
        menu.addAction("Show", self._show_window)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.setToolTip("GestureSense")
        self._tray.activated.connect(
            lambda reason: self._show_window()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
        self._tray.show()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def _quit(self):
        self._stop_camera()
        self._stop_voice_thread()
        self._tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # ── Window close ─────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Minimize to tray instead of quitting."""
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "GestureSense",
            "Running in background. Double-click tray icon to restore.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )
