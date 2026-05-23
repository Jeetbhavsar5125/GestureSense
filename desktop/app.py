"""
desktop/app.py
==============
GestureSense PyQt6 Desktop Application.
Uses shared core.detector and core.executor modules.
Run via:  python main.py  or  python main.py --desktop
"""

import os
import sys
import time
import threading

import cv2
import mediapipe as mp

from core.mouse_control import MouseController

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QLineEdit, QComboBox,
    QDoubleSpinBox, QGridLayout, QMessageBox, QStackedWidget, QSlider
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QBrush, QPen, QColor, QRadialGradient, QIcon

import config.manager as cfg_mgr
from core.detector import get_finger_states, detect_gesture
from core.executor import execute_action

# ── Palette ───────────────────────────────────────────────────────────────────
BG = "#050d1a"; BG2 = "#0a1628"; BG3 = "#0f1f38"; CARD = "#0d1f3c"
ACCENT = "#00e5ff"; ACCENT2 = "#7c3aed"; GREEN = "#00ff88"
ORANGE = "#ff9500"; RED = "#ff3b5c"; WHITE = "#f0f8ff"
MUTED = "#4a6080"; TEXT = "#a8c4e0"; BORDER = "#1a3050"

STYLE = f"""
QMainWindow,QWidget{{background:{BG};color:{WHITE};font-family:'Segoe UI',Arial,sans-serif;}}
QLabel{{color:{WHITE};background:transparent;}}
QPushButton{{background:{BG3};color:{WHITE};border:1px solid {BORDER};border-radius:8px;padding:8px 18px;font-size:13px;font-weight:600;}}
QPushButton:hover{{border-color:{ACCENT};color:{ACCENT};background:rgba(0,229,255,0.07);}}
QPushButton#primary{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT2},stop:1 {ACCENT});color:#050d1a;border:none;font-weight:700;}}
QPushButton#danger{{border-color:{RED};color:{RED};}}
QPushButton#danger:hover{{background:rgba(255,59,92,0.1);}}
QPushButton#success{{background:rgba(0,255,136,0.12);border-color:{GREEN};color:{GREEN};}}
QLineEdit,QComboBox,QDoubleSpinBox{{background:{BG2};color:{WHITE};border:1px solid {BORDER};border-radius:6px;padding:7px 10px;font-size:13px;}}
QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus{{border-color:{ACCENT};}}
QComboBox QAbstractItemView{{background:{BG3};color:{WHITE};border:1px solid {BORDER};}}
QComboBox::drop-down{{border:none;}}
QScrollArea{{border:none;background:transparent;}}
QScrollBar:vertical{{background:{BG2};width:6px;border-radius:3px;}}
QScrollBar::handle:vertical{{background:{BORDER};border-radius:3px;min-height:20px;}}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
QSlider::groove:horizontal{{background:{BORDER};height:4px;border-radius:2px;}}
QSlider::handle:horizontal{{background:{ACCENT};width:14px;height:14px;border-radius:7px;margin:-5px 0;}}
QSlider::sub-page:horizontal{{background:{ACCENT};border-radius:2px;}}
"""

KEY_OPTIONS = [
    ("Space (Play/Pause)", "space", "special"),
    ("Right Arrow (+5s)",  "right", "special"),
    ("Left Arrow (-5s)",   "left",  "special"),
    ("Up Arrow (Vol+)",    "up",    "special"),
    ("Down Arrow (Vol-)",  "down",  "special"),
    ("L key (+10s)",       "l",     "char"),
    ("J key (-10s)",       "j",     "char"),
    ("M key (Mute)",       "m",     "char"),
    ("F key (Fullscreen)", "f",     "char"),
    ("T key (Theater)",    "t",     "char"),
    ("K key (Play/Pause alt)", "k", "char"),
    ("Enter",              "enter", "special"),
    ("Escape",             "esc",   "special"),
    ("F11",                "f11",   "special"),
    ("Open Link...",       "url_action", "url"),
    ("Type Text...",       "type_text", "type"),
    ("Custom key...",      "custom","char"),
]

# ── Camera Thread ─────────────────────────────────────────────────────────────
class CameraThread(QThread):
    frame_ready    = pyqtSignal(QImage)
    gesture_ready  = pyqtSignal(str, float, list, float)
    error_occurred = pyqtSignal(str)

    def __init__(self, mappings, custom, last_trigger, cam_index=0):
        super().__init__()
        self.mappings     = mappings
        self.custom       = custom
        self.last_trigger = last_trigger
        self.cam_index    = cam_index
        self.running      = False
        self.mouse_control_enabled = False
        self.mouse_controller      = MouseController()
        self._mp_hands    = mp.solutions.hands
        self._mp_draw     = mp.solutions.drawing_utils
        self._hands       = self._mp_hands.Hands(
            static_image_mode=False, max_num_hands=1,
            min_detection_confidence=0.75, min_tracking_confidence=0.75)

    def run(self):
        self.running = True
        cap = cv2.VideoCapture(self.cam_index)
        if not cap or not cap.isOpened():
            self.error_occurred.emit(
                f"Could not open camera {self.cam_index}. Try a different camera index.")
            self.running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res   = self._hands.process(rgb)

            gesture_name = "none"; confidence = 0.0
            fingers = [0, 0, 0, 0, 0]; cooldown_left = 0.0

            if res.multi_hand_landmarks:
                for hand_lm, hand_info in zip(res.multi_hand_landmarks, res.multi_handedness):
                    self._mp_draw.draw_landmarks(frame, hand_lm, self._mp_hands.HAND_CONNECTIONS)
                    lm         = hand_lm.landmark
                    handedness = hand_info.classification[0].label
                    fingers    = get_finger_states(lm, handedness)
                    gesture_name, confidence = detect_gesture(lm, fingers, self.custom)

                    if self.mouse_control_enabled:
                        self.mouse_controller.update(gesture_name, lm)

                    if gesture_name != "none":
                        is_mouse_gesture = gesture_name in ("index", "pinch", "peace", "three_fingers", "ok_sign")
                        if self.mouse_control_enabled and is_mouse_gesture:
                            # Handled by mouse_controller
                            pass
                        else:
                            mapping  = self.mappings.get(gesture_name) or self.custom.get(gesture_name) or {}
                            cooldown = mapping.get("cooldown", 1.0)
                            now      = time.time()
                            elapsed  = now - self.last_trigger.get(gesture_name, 0)
                            cooldown_left = max(0.0, cooldown - elapsed)
                            if elapsed >= cooldown:
                                key      = mapping.get("key", "")
                                key_type = mapping.get("key_type", "none")
                                if key_type != "none" and key:
                                    threading.Thread(
                                        target=execute_action, args=(key, key_type), daemon=True).start()
                                self.last_trigger[gesture_name] = now
            else:
                if self.mouse_control_enabled:
                    self.mouse_controller.update("none", None)

            self.gesture_ready.emit(gesture_name, confidence, fingers, cooldown_left)
            rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_out.shape
            self.frame_ready.emit(
                QImage(rgb_out.data, w, h, ch * w, QImage.Format.Format_RGB888))
            time.sleep(0.033)

        cap.release()

    def stop(self):
        self.running = False
        self.wait()

# ── Small widgets ─────────────────────────────────────────────────────────────
class LogoWidget(QWidget):
    def __init__(self, size=48):
        super().__init__()
        self.size_ = size
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QRadialGradient(self.size_/2, self.size_/2, self.size_/2)
        grad.setColorAt(0, QColor("#7c3aed")); grad.setColorAt(1, QColor("#00e5ff"))
        p.setBrush(QBrush(grad)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self.size_, self.size_, self.size_*0.22, self.size_*0.22)

class FingerIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.fingers = [0, 0, 0, 0, 0]
        self.setFixedSize(130, 70)

    def set_fingers(self, fingers):
        self.fingers = fingers; self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        names   = ["T","I","M","R","P"]
        w       = self.width(); h = self.height()
        gap     = w // 5; bar_w = 18
        heights = [28, 38, 40, 36, 30]
        for i, (name, up) in enumerate(zip(names, self.fingers)):
            x = i*gap + gap//2 - bar_w//2; bh = heights[i]; y = h - 14 - bh
            p.setBrush(QBrush(QColor(ACCENT) if up else QColor(BORDER)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, y, bar_w, bh, 4, 4)
            p.setPen(QPen(QColor(MUTED))); p.setFont(QFont("Segoe UI", 7))
            p.drawText(x, h-2, bar_w, 12, Qt.AlignmentFlag.AlignHCenter, name)

class CooldownBar(QWidget):
    def __init__(self):
        super().__init__()
        self.progress = 0.0; self.on_cd = False; self.setFixedHeight(6)

    def set_cooldown(self, remaining, total):
        self.progress = (remaining / total) if total > 0 else 0.0
        self.on_cd    = remaining > 0; self.update()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width(); h = self.height()
        p.setBrush(QBrush(QColor(BORDER))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 3, 3)
        fill_w = int(w * (1 - self.progress))
        if fill_w > 0:
            p.setBrush(QBrush(QColor(GREEN) if not self.on_cd else QColor(ORANGE)))
            p.drawRoundedRect(0, 0, fill_w, h, 3, 3)

class GestureCard(QFrame):
    def __init__(self, gesture_id, mapping, is_custom=False, on_delete=None, on_edit_cooldown=None):
        super().__init__()
        self.gesture_id = gesture_id; self.active = False
        self.setObjectName("gestureCard")
        self.setStyleSheet(f"QFrame#gestureCard{{background:{CARD};border:1px solid {BORDER};border-radius:10px;padding:4px;}}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8); layout.setSpacing(12)
        icon_lbl = QLabel(mapping.get("icon", "🤌"))
        icon_lbl.setFont(QFont("Segoe UI Emoji", 20)); icon_lbl.setFixedWidth(36)
        layout.addWidget(icon_lbl)
        info = QVBoxLayout(); info.setSpacing(2)
        name_lbl = QLabel(mapping.get("label", "Custom"))
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color:{WHITE};")
        key_str = mapping.get("key", ""); ktype = mapping.get("key_type", "none")
        key_lbl = QLabel(f"Key: {key_str.upper() if key_str else '—'}  •  {ktype}  •  ID: {gesture_id}")
        key_lbl.setFont(QFont("Courier New", 9)); key_lbl.setStyleSheet(f"color:{MUTED};")
        info.addWidget(name_lbl); info.addWidget(key_lbl); layout.addLayout(info, 1)
        cd_layout = QVBoxLayout(); cd_layout.setSpacing(3)
        cd_label = QLabel(f"⏱ {mapping.get('cooldown', 1.0)}s")
        cd_label.setFont(QFont("Courier New", 9)); cd_label.setStyleSheet(f"color:{ACCENT};")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(1, 50); slider.setValue(int(mapping.get("cooldown", 1.0) * 10))
        slider.setFixedWidth(90)
        slider.valueChanged.connect(lambda v: (
            cd_label.setText(f"⏱ {v/10:.1f}s"),
            on_edit_cooldown(gesture_id, v/10) if on_edit_cooldown else None))
        cd_layout.addWidget(cd_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        cd_layout.addWidget(slider); layout.addLayout(cd_layout)
        self.active_dot = QLabel("●")
        self.active_dot.setFont(QFont("Segoe UI", 14))
        self.active_dot.setStyleSheet(f"color:{MUTED};"); self.active_dot.setFixedWidth(20)
        layout.addWidget(self.active_dot)
        if is_custom and on_delete:
            del_btn = QPushButton("✕"); del_btn.setObjectName("danger")
            del_btn.setFixedSize(32, 32); del_btn.clicked.connect(lambda: on_delete(gesture_id))
            layout.addWidget(del_btn)

    def set_active(self, active):
        if active != self.active:
            self.active = active
            color = ACCENT if active else MUTED
            self.active_dot.setStyleSheet(f"color:{color};")
            bg = "rgba(0,229,255,0.06)" if active else CARD
            bd = ACCENT if active else BORDER
            self.setStyleSheet(f"QFrame#gestureCard{{background:{bg};border:1px solid {bd};border-radius:10px;padding:4px;}}")

class AddGesturePanel(QFrame):
    gesture_added = pyqtSignal(str, dict)

    def __init__(self):
        super().__init__()
        self.setObjectName("addPanel")
        self.setStyleSheet(f"QFrame#addPanel{{background:{BG2};border:1px solid {BORDER};border-radius:12px;}}")
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 16, 20, 16); layout.setSpacing(12)
        title = QLabel("➕  Add Custom Gesture")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold)); title.setStyleSheet(f"color:{ACCENT};")
        layout.addWidget(title)
        desc = QLabel("Toggle which fingers should be UP to define your gesture pattern.")
        desc.setFont(QFont("Segoe UI", 10)); desc.setStyleSheet(f"color:{MUTED};"); desc.setWordWrap(True)
        layout.addWidget(desc)
        finger_layout = QHBoxLayout(); finger_layout.setSpacing(8)
        self.finger_btns = []
        for name in ["👍 Thumb","☝️ Index","🖕 Middle","💍 Ring","🤙 Pinky"]:
            btn = QPushButton(name); btn.setCheckable(True)
            btn.setFont(QFont("Segoe UI", 9)); btn.setFixedHeight(44)
            btn.setStyleSheet(f"""
                QPushButton{{background:{BG3};border:1px solid {BORDER};border-radius:6px;color:{MUTED};font-size:10px;}}
                QPushButton:checked{{background:rgba(0,229,255,0.12);border-color:{ACCENT};color:{ACCENT};font-weight:bold;}}
            """)
            self.finger_btns.append(btn); finger_layout.addWidget(btn)
        layout.addLayout(finger_layout)
        self.pattern_lbl = QLabel("Pattern: 00000")
        self.pattern_lbl.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        self.pattern_lbl.setStyleSheet(f"color:{ORANGE};"); layout.addWidget(self.pattern_lbl)
        for btn in self.finger_btns:
            btn.toggled.connect(self.update_pattern)
        grid = QGridLayout(); grid.setSpacing(8)
        grid.addWidget(self._lbl("Gesture Name"), 0, 0)
        self.name_input = QLineEdit(); self.name_input.setPlaceholderText("e.g. My Gesture")
        grid.addWidget(self.name_input, 0, 1)
        grid.addWidget(self._lbl("Icon (emoji)"), 0, 2)
        self.icon_input = QLineEdit(); self.icon_input.setPlaceholderText("🤌"); self.icon_input.setFixedWidth(70)
        grid.addWidget(self.icon_input, 0, 3)
        grid.addWidget(self._lbl("Key Action"), 1, 0)
        self.key_combo = QComboBox()
        for display, _, _ in KEY_OPTIONS: self.key_combo.addItem(display)
        self.key_combo.currentIndexChanged.connect(self.on_key_changed)
        grid.addWidget(self.key_combo, 1, 1)
        self.custom_key_input = QLineEdit()
        self.custom_key_input.setPlaceholderText("Type key e.g. 'a' or 'ctrl+s'")
        self.custom_key_input.hide(); grid.addWidget(self.custom_key_input, 1, 2, 1, 2)
        grid.addWidget(self._lbl("Cooldown (sec)"), 2, 0)
        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.1, 10.0); self.cooldown_spin.setSingleStep(0.1)
        self.cooldown_spin.setValue(1.0); grid.addWidget(self.cooldown_spin, 2, 1)
        layout.addLayout(grid)
        add_btn = QPushButton("  ✚  ADD GESTURE"); add_btn.setObjectName("primary")
        add_btn.setFixedHeight(40); add_btn.clicked.connect(self.add_gesture)
        layout.addWidget(add_btn)

    def _lbl(self, text):
        l = QLabel(text); l.setFont(QFont("Segoe UI", 10)); l.setStyleSheet(f"color:{TEXT};"); return l

    def update_pattern(self):
        self.pattern_lbl.setText("Pattern: " + "".join("1" if b.isChecked() else "0" for b in self.finger_btns))

    def on_key_changed(self, idx):
        _, key, key_type = KEY_OPTIONS[idx]
        self.custom_key_input.setVisible(key == "custom" or key_type == "url" or key_type == "type")
        if key_type == "url":
            self.custom_key_input.setPlaceholderText("Type website URL e.g. youtube.com")
        elif key_type == "type":
            self.custom_key_input.setPlaceholderText("Type text to auto-type, e.g. Hello!")
        else:
            self.custom_key_input.setPlaceholderText("Type key e.g. 'a' or 'ctrl+s'")

    def add_gesture(self):
        pattern  = "".join("1" if b.isChecked() else "0" for b in self.finger_btns)
        name     = self.name_input.text().strip() or "Custom Gesture"
        icon     = self.icon_input.text().strip() or "🤌"
        cd       = self.cooldown_spin.value()
        idx      = self.key_combo.currentIndex()
        _, key, key_type = KEY_OPTIONS[idx]
        if key == "custom" or key_type == "url" or key_type == "type":
            raw = self.custom_key_input.text().strip()
            if not raw:
                QMessageBox.warning(self, "Missing Value", "Please enter a value."); return
            key = raw
            if key_type == "url":
                if not key.startswith(("http://", "https://")): key = "https://" + key
            elif key_type != "type":
                key_type = "hotkey" if "+" in raw else "char"
        self.gesture_added.emit(pattern, {"label": name, "icon": icon, "key": key, "key_type": key_type, "cooldown": cd})
        for b in self.finger_btns: b.setChecked(False)
        self.name_input.clear(); self.icon_input.clear(); self.cooldown_spin.setValue(1.0)

# ── Main Window ───────────────────────────────────────────────────────────────
class GestureSenseApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GestureSense"); self.setMinimumSize(1100, 720); self.resize(1200, 780)
        cfg = cfg_mgr.load()
        self.mappings      = dict(cfg["mappings"])
        self.custom        = dict(cfg["custom"])
        self.last_trigger  = {}
        self.camera_thread = None
        self.gesture_cards = {}
        self.current_gesture = "none"
        self.mouse_control_enabled = False
        self.setStyleSheet(STYLE)
        self._build_ui()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        # Header
        header = QWidget(); header.setFixedHeight(68)
        header.setStyleSheet(f"background:rgba(5,13,26,0.95);border-bottom:1px solid {BORDER};")
        hlay = QHBoxLayout(header); hlay.setContentsMargins(20,0,20,0); hlay.setSpacing(14)
        hlay.addWidget(LogoWidget(44))
        tc = QVBoxLayout(); tc.setSpacing(0)
        t1 = QLabel("GESTURE SENSE"); t1.setFont(QFont("Segoe UI Black", 16, QFont.Weight.Black))
        t1.setStyleSheet(f"color:{WHITE};letter-spacing:2px;")
        t2 = QLabel("Hand Gesture Controller  •  Desktop App")
        t2.setFont(QFont("Segoe UI", 9)); t2.setStyleSheet(f"color:{MUTED};")
        tc.addWidget(t1); tc.addWidget(t2); hlay.addLayout(tc); hlay.addStretch()
        self.status_dot = QLabel("●"); self.status_dot.setFont(QFont("Segoe UI", 14))
        self.status_dot.setStyleSheet(f"color:{RED};")
        self.status_lbl = QLabel("Camera Off"); self.status_lbl.setFont(QFont("Courier New", 10))
        self.status_lbl.setStyleSheet(f"color:{RED};")
        self.fps_lbl = QLabel("-- FPS"); self.fps_lbl.setFont(QFont("Courier New", 10))
        self.fps_lbl.setStyleSheet(f"color:{ACCENT};background:rgba(0,229,255,0.08);padding:4px 10px;border-radius:5px;border:1px solid rgba(0,229,255,0.2);")
        self.cam_combo = QComboBox()
        self.cam_combo.addItems(["Camera 0 (Default)","Camera 1","Camera 2","Camera 3"])
        self.cam_combo.setFixedWidth(140); self.cam_combo.setFixedHeight(36)
        self.start_btn = QPushButton("  ▶  START"); self.start_btn.setObjectName("primary")
        self.start_btn.setFixedSize(110, 36); self.start_btn.clicked.connect(self.toggle_camera)
        self.stop_btn = QPushButton("  ■  STOP"); self.stop_btn.setObjectName("danger")
        self.stop_btn.setFixedSize(100, 36); self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_camera)
        
        self.mouse_chk = QPushButton("🖱️ Mouse Control")
        self.mouse_chk.setCheckable(True)
        self.mouse_chk.setFixedSize(150, 36)
        self.mouse_chk.clicked.connect(self.toggle_mouse_control)
        
        self.dash_btn = QPushButton("  🌐 Web Dashboard"); self.dash_btn.setFixedSize(160, 36)
        self.dash_btn.clicked.connect(self.open_web_dashboard)
        for w in [self.status_dot, self.status_lbl, self.fps_lbl, self.cam_combo,
                  self.start_btn, self.stop_btn, self.mouse_chk, self.dash_btn]:
            hlay.addWidget(w)
        root.addWidget(header)
        # Body
        body = QHBoxLayout(); body.setContentsMargins(16,16,16,16); body.setSpacing(16)
        left = QVBoxLayout(); left.setSpacing(12)
        cam_frame = QFrame()
        cam_frame.setStyleSheet(f"background:#020810;border:1px solid {BORDER};border-radius:12px;")
        cam_lay = QVBoxLayout(cam_frame); cam_lay.setContentsMargins(0,0,0,0); cam_lay.setSpacing(0)
        cam_header = QWidget(); cam_header.setFixedHeight(36)
        cam_header.setStyleSheet(f"background:{CARD};border-radius:11px 11px 0 0;border-bottom:1px solid {BORDER};")
        ch_lay = QHBoxLayout(cam_header); ch_lay.setContentsMargins(12,0,12,0)
        cam_title = QLabel("📷  Live Camera Feed"); cam_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        cam_title.setStyleSheet(f"color:{MUTED};letter-spacing:1px;")
        self.hand_badge = QLabel("No hand detected"); self.hand_badge.setFont(QFont("Courier New", 9))
        self.hand_badge.setStyleSheet(f"color:{MUTED};")
        ch_lay.addWidget(cam_title); ch_lay.addStretch(); ch_lay.addWidget(self.hand_badge)
        cam_lay.addWidget(cam_header)
        self.cam_lbl = QLabel(); self.cam_lbl.setFixedSize(560, 360)
        self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_lbl.setText("Click START to begin"); self.cam_lbl.setFont(QFont("Segoe UI", 12))
        self.cam_lbl.setStyleSheet(f"color:{MUTED};background:#020810;")
        cam_lay.addWidget(self.cam_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        self.cooldown_bar = CooldownBar(); cam_lay.addWidget(self.cooldown_bar)
        left.addWidget(cam_frame)
        act_frame = QFrame()
        act_frame.setStyleSheet(f"background:{CARD};border:1px solid {BORDER};border-radius:12px;")
        act_lay = QHBoxLayout(act_frame); act_lay.setContentsMargins(16,12,16,12); act_lay.setSpacing(16)
        self.active_icon = QLabel("—"); self.active_icon.setFont(QFont("Segoe UI Emoji", 28))
        self.active_icon.setFixedWidth(48); act_lay.addWidget(self.active_icon)
        ic = QVBoxLayout(); ic.setSpacing(2)
        self.active_name   = QLabel("Waiting for gesture..."); self.active_name.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.active_action = QLabel("No action"); self.active_action.setFont(QFont("Courier New", 10))
        self.active_action.setStyleSheet(f"color:{ACCENT};")
        ic.addWidget(self.active_name); ic.addWidget(self.active_action); act_lay.addLayout(ic, 1)
        self.conf_lbl = QLabel("0%"); self.conf_lbl.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        self.conf_lbl.setStyleSheet(f"color:{ACCENT2};"); act_lay.addWidget(self.conf_lbl)
        self.finger_viz = FingerIndicator(); act_lay.addWidget(self.finger_viz)
        left.addWidget(act_frame)
        stats_row = QHBoxLayout(); stats_row.setSpacing(8)
        self.stat_total  = self._stat_box("0", "GESTURES FIRED")
        self.stat_uptime = self._stat_box("00:00", "SESSION TIME")
        self.stat_top    = self._stat_box("—", "TOP GESTURE")
        for sb in [self.stat_total, self.stat_uptime, self.stat_top]: stats_row.addWidget(sb)
        left.addLayout(stats_row)
        body.addLayout(left)
        right = QVBoxLayout(); right.setSpacing(12)
        tab_row = QHBoxLayout(); tab_row.setSpacing(6)
        self.tab_all    = QPushButton("All Gestures")
        self.tab_custom = QPushButton("Custom")
        self.tab_add    = QPushButton("+ Add New"); self.tab_add.setObjectName("success")
        for btn in [self.tab_all, self.tab_custom, self.tab_add]:
            btn.setFixedHeight(34); tab_row.addWidget(btn)
        self.tab_all.clicked.connect(lambda: self.switch_tab(0))
        self.tab_custom.clicked.connect(lambda: self.switch_tab(1))
        self.tab_add.clicked.connect(lambda: self.switch_tab(2))
        right.addLayout(tab_row)
        self.stack = QStackedWidget()
        for tab_idx in range(2):
            w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)
            sc = QScrollArea(); sc.setWidgetResizable(True)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            inner = QWidget(); vl = QVBoxLayout(inner); vl.setSpacing(6); vl.setContentsMargins(0,0,6,0)
            if tab_idx == 0:
                self.all_cards_layout = vl
            else:
                self.no_custom_lbl = QLabel("No custom gestures yet.\nClick '+ Add New' to create one!")
                self.no_custom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.no_custom_lbl.setFont(QFont("Segoe UI", 11))
                self.no_custom_lbl.setStyleSheet(f"color:{MUTED};padding:40px;")
                vl.addWidget(self.no_custom_lbl)
                self.custom_cards_layout = vl
            vl.addStretch(); sc.setWidget(inner); lay.addWidget(sc); self.stack.addWidget(w)
        add_sc = QScrollArea(); add_sc.setWidgetResizable(True)
        add_sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        add_inner = QWidget(); ail = QVBoxLayout(add_inner); ail.setContentsMargins(0,0,6,0)
        self.add_panel = AddGesturePanel(); self.add_panel.gesture_added.connect(self.on_gesture_added)
        ail.addWidget(self.add_panel); ail.addStretch(); add_sc.setWidget(add_inner)
        self.stack.addWidget(add_sc)
        right.addWidget(self.stack, 1); body.addLayout(right)
        mw = QWidget(); mw.setLayout(body); root.addWidget(mw, 1)
        self._load_cards()
        self.uptime_timer = QTimer(); self.uptime_timer.timeout.connect(self.update_uptime)
        self.session_start = None; self.total_gestures = 0

    def _stat_box(self, val, lbl):
        frame = QFrame(); frame.setStyleSheet(f"background:{CARD};border:1px solid {BORDER};border-radius:8px;")
        lay = QVBoxLayout(frame); lay.setContentsMargins(12,8,12,8); lay.setSpacing(2)
        v = QLabel(val); v.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        v.setStyleSheet(f"color:{ACCENT};"); v.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        l = QLabel(lbl); l.setFont(QFont("Segoe UI", 8))
        l.setStyleSheet(f"color:{MUTED};letter-spacing:1px;"); l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(v); lay.addWidget(l); frame.val_lbl = v; return frame

    def _load_cards(self):
        for gid, mapping in self.mappings.items():
            card = GestureCard(gid, mapping, on_edit_cooldown=self.on_cooldown_changed)
            self.gesture_cards[gid] = card
            self.all_cards_layout.insertWidget(self.all_cards_layout.count()-1, card)
        if self.custom:
            self.no_custom_lbl.hide()
            for pattern, mapping in self.custom.items():
                card = GestureCard(pattern, mapping, is_custom=True,
                                   on_delete=self.on_delete_custom,
                                   on_edit_cooldown=self.on_cooldown_changed)
                self.gesture_cards[pattern] = card
                self.custom_cards_layout.insertWidget(self.custom_cards_layout.count()-1, card)
                self.all_cards_layout.insertWidget(self.all_cards_layout.count()-1, card)

    def open_web_dashboard(self):
        import webbrowser
        html = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "frontend.html")
        webbrowser.open(f"file:///{html}")

    def switch_tab(self, idx): self.stack.setCurrentIndex(idx)

    def on_gesture_added(self, pattern, mapping):
        if pattern in self.mappings or pattern in self.custom:
            QMessageBox.warning(self, "Pattern Exists", f"Pattern {pattern} is already used."); return
        self.custom[pattern] = mapping; self.mappings[pattern] = mapping
        cfg_mgr.save({"mappings": self.mappings, "custom": self.custom})
        card = GestureCard(pattern, mapping, is_custom=True,
                           on_delete=self.on_delete_custom, on_edit_cooldown=self.on_cooldown_changed)
        self.gesture_cards[pattern] = card
        self.custom_cards_layout.insertWidget(self.custom_cards_layout.count()-1, card)
        self.all_cards_layout.insertWidget(self.all_cards_layout.count()-1, card)
        self.no_custom_lbl.hide()
        QMessageBox.information(self, "✅ Gesture Added", f"'{mapping['label']}' added!\n{pattern} → {mapping['key']}")
        self.switch_tab(1)

    def on_delete_custom(self, pattern):
        self.custom.pop(pattern, None); self.mappings.pop(pattern, None)
        cfg_mgr.save({"mappings": self.mappings, "custom": self.custom})
        if pattern in self.gesture_cards:
            self.gesture_cards.pop(pattern).deleteLater()
        if not self.custom: self.no_custom_lbl.show()

    def on_cooldown_changed(self, gesture_id, new_val):
        if gesture_id in self.mappings: self.mappings[gesture_id]["cooldown"] = new_val
        if gesture_id in self.custom:   self.custom[gesture_id]["cooldown"]   = new_val
        cfg_mgr.save({"mappings": self.mappings, "custom": self.custom})

    def toggle_mouse_control(self, checked):
        self.mouse_control_enabled = checked
        if self.camera_thread:
            self.camera_thread.mouse_control_enabled = checked
        if checked:
            self.mouse_chk.setStyleSheet("background: rgba(0, 229, 255, 0.15); border-color: #00e5ff; color: #00e5ff;")
        else:
            self.mouse_chk.setStyleSheet("")

    def toggle_camera(self):
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True); self.cam_combo.setEnabled(False)
        self.session_start = time.time(); self.uptime_timer.start(1000)
        cam_idx = self.cam_combo.currentIndex()
        self.camera_thread = CameraThread(self.mappings, self.custom, self.last_trigger, cam_idx)
        self.camera_thread.mouse_control_enabled = self.mouse_control_enabled
        self.camera_thread.frame_ready.connect(self.update_frame)
        self.camera_thread.gesture_ready.connect(self.update_gesture)
        self.camera_thread.error_occurred.connect(self.on_camera_error)
        self.camera_thread.start()
        self.status_dot.setStyleSheet(f"color:{GREEN};"); self.status_lbl.setStyleSheet(f"color:{GREEN};")
        self.status_lbl.setText("Camera Active")

    def stop_camera(self):
        if self.camera_thread: self.camera_thread.stop(); self.camera_thread = None
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.cam_combo.setEnabled(True)
        self.uptime_timer.stop()
        self.cam_lbl.setText("Camera stopped. Click START to begin.")
        self.cam_lbl.setStyleSheet(f"color:{MUTED};background:#020810;")
        self.status_dot.setStyleSheet(f"color:{RED};"); self.status_lbl.setStyleSheet(f"color:{RED};")
        self.status_lbl.setText("Camera Off"); self.fps_lbl.setText("-- FPS")

    def on_camera_error(self, message):
        self.stop_camera(); QMessageBox.critical(self, "Camera Error", message)

    def update_frame(self, qt_img):
        self.cam_lbl.setPixmap(QPixmap.fromImage(qt_img).scaled(
            self.cam_lbl.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def update_gesture(self, gesture, confidence, fingers, cooldown_left):
        self.finger_viz.set_fingers(fingers)
        for gid, card in self.gesture_cards.items(): card.set_active(gid == gesture)
        if gesture != "none":
            self.hand_badge.setText("✋ Hand detected"); self.hand_badge.setStyleSheet(f"color:{GREEN};")
            mapping = self.mappings.get(gesture) or self.custom.get(gesture) or {}
            self.active_icon.setText(mapping.get("icon", "—"))
            self.active_name.setText(mapping.get("label", "Unknown"))
            key = mapping.get("key", "")
            self.active_action.setText(f"KEY: {key.upper() if key else '—'}  •  {int(confidence*100)}%")
            self.conf_lbl.setText(f"{int(confidence*100)}%")
            self.cooldown_bar.set_cooldown(cooldown_left, mapping.get("cooldown", 1.0))
            if gesture != self.current_gesture:
                self.total_gestures += 1
                self.stat_total.val_lbl.setText(str(self.total_gestures))
                self.stat_top.val_lbl.setText(mapping.get("icon", "—"))
                self.current_gesture = gesture
        else:
            self.hand_badge.setText("No hand detected"); self.hand_badge.setStyleSheet(f"color:{MUTED};")
            self.active_icon.setText("—"); self.active_name.setText("Waiting for gesture...")
            self.active_action.setText("No action"); self.conf_lbl.setText("0%")
            self.cooldown_bar.set_cooldown(0, 1); self.current_gesture = "none"

    def update_uptime(self):
        if self.session_start:
            e = int(time.time() - self.session_start)
            self.stat_uptime.val_lbl.setText(f"{e//60:02d}:{e%60:02d}")
        self.fps_lbl.setText("28-30 FPS")

    def closeEvent(self, event):
        self.stop_camera(); super().closeEvent(event)


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("GestureSense"); app.setApplicationVersion("3.0")
    win = GestureSenseApp()
    ico = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.ico")
    if os.path.exists(ico): win.setWindowIcon(QIcon(ico))
    win.show(); sys.exit(app.exec())
