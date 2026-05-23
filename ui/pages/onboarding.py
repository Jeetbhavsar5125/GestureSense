"""
ui/pages/onboarding.py
======================
GestureSense — First-Run Onboarding Wizard (Feature 6)
Member 3 Responsibility: UI/UX Design

A 4-step wizard shown the first time GestureSense launches:
  Step 1: Welcome — project intro + feature highlights
  Step 2: Camera Test — verify webcam is accessible
  Step 3: Gesture Demo — animated gesture reference cheat-sheet
  Step 4: Done — CTA to open dashboard

Shown only when config["first_run"] == True.
Sets config["first_run"] = False on completion.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QSizePolicy,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui  import QFont, QColor, QPainter, QBrush, QLinearGradient, QPen

from ui.theme import (
    BG, BG2, BG3, CARD, ACCENT, ACCENT2, GREEN,
    WHITE, MUTED, BORDER, TEXT, ORANGE,
)


# ── Step indicator dots ───────────────────────────────────────────────────────

class _StepDots(QWidget):
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self._total   = total
        self._current = 0
        self.setFixedHeight(16)

    def set_step(self, idx: int):
        self._current = idx
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 6
        gap = 18
        total_w = self._total * (r * 2) + (self._total - 1) * (gap - r * 2)
        x0 = (self.width() - total_w) // 2
        y  = self.height() // 2
        for i in range(self._total):
            cx = x0 + i * gap
            if i == self._current:
                p.setBrush(QBrush(QColor(ACCENT)))
            else:
                p.setBrush(QBrush(QColor(BORDER)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - r, y - r, r * 2, r * 2)


# ── Feature card (Step 1) ─────────────────────────────────────────────────────

class _FeatureCard(QFrame):
    def __init__(self, icon: str, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG3};
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 28))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet(f"color: {WHITE};")
        lay.addWidget(title_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setFont(QFont("Segoe UI", 9))
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(desc_lbl)


# ── Gesture demo chip ─────────────────────────────────────────────────────────

class _GestureChip(QFrame):
    def __init__(self, icon: str, name: str, action: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setStyleSheet(f"""
            QFrame {{
                background: {CARD};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {ACCENT};
                background: rgba(0,229,255,0.06);
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(12)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 22))
        icon_lbl.setFixedWidth(36)
        lay.addWidget(icon_lbl)

        col = QVBoxLayout()
        col.setSpacing(1)
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {WHITE};")
        act_lbl = QLabel(action)
        act_lbl.setFont(QFont("Segoe UI", 8))
        act_lbl.setStyleSheet(f"color: {MUTED};")
        col.addWidget(name_lbl)
        col.addWidget(act_lbl)
        lay.addLayout(col, 1)


# ── Individual Steps ──────────────────────────────────────────────────────────

def _build_step1() -> QWidget:
    """Welcome — intro + feature highlights."""
    page = QWidget()
    lay  = QVBoxLayout(page)
    lay.setContentsMargins(60, 40, 60, 20)
    lay.setSpacing(20)

    # Hero
    hero_icon = QLabel("🖐")
    hero_icon.setFont(QFont("Segoe UI Emoji", 64))
    hero_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(hero_icon)

    title = QLabel("Welcome to GestureSense")
    title.setFont(QFont("Segoe UI Black", 28, QFont.Weight.Black))
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(f"""
        color: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {ACCENT2}, stop:1 {ACCENT});
    """)
    lay.addWidget(title)

    sub = QLabel("Control your computer with hand gestures — no hardware required.")
    sub.setFont(QFont("Segoe UI", 13))
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    sub.setStyleSheet(f"color: {TEXT};")
    sub.setWordWrap(True)
    lay.addWidget(sub)

    # Feature cards
    cards_row = QHBoxLayout()
    cards_row.setSpacing(14)
    for icon, title_txt, desc in [
        ("📷", "Webcam Only",     "Works with any standard webcam — no special hardware needed"),
        ("🤖", "AI Powered",     "MediaPipe ML tracks 21 hand landmarks in real time"),
        ("🖱",  "Air Mouse",      "Move cursor, click, scroll with just your hand in mid-air"),
        ("⚙",  "Customizable",   "Map any gesture to any key, hotkey, URL, or typed text"),
    ]:
        cards_row.addWidget(_FeatureCard(icon, title_txt, desc))
    lay.addLayout(cards_row)
    lay.addStretch()
    return page


def _build_step2() -> QWidget:
    """Camera Test — basic webcam check."""
    page = QWidget()
    lay  = QVBoxLayout(page)
    lay.setContentsMargins(80, 40, 80, 20)
    lay.setSpacing(20)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

    icon = QLabel("📷")
    icon.setFont(QFont("Segoe UI Emoji", 56))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(icon)

    title = QLabel("Camera Setup")
    title.setFont(QFont("Segoe UI Black", 22, QFont.Weight.Black))
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(f"color: {WHITE};")
    lay.addWidget(title)

    desc = QLabel(
        "GestureSense uses your webcam to track your hand in real time.\n\n"
        "Make sure:\n"
        "  ✅  Your webcam is plugged in and not in use by another app\n"
        "  ✅  You have adequate lighting (avoid backlit backgrounds)\n"
        "  ✅  Your hand fits comfortably in the camera frame\n\n"
        "If you have multiple cameras, you can change the camera index in ⚙ Settings."
    )
    desc.setFont(QFont("Segoe UI", 12))
    desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
    desc.setWordWrap(True)
    desc.setStyleSheet(f"color: {TEXT}; line-height: 1.6;")
    lay.addWidget(desc)
    lay.addStretch()
    return page


def _build_step3() -> QWidget:
    """Gesture Demo — scrollable cheat-sheet."""
    page = QWidget()
    lay  = QVBoxLayout(page)
    lay.setContentsMargins(60, 30, 60, 10)
    lay.setSpacing(16)

    title = QLabel("Your Gesture Reference")
    title.setFont(QFont("Segoe UI Black", 20, QFont.Weight.Black))
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(f"color: {WHITE};")
    lay.addWidget(title)

    sub = QLabel("Hold any gesture for 0.35 seconds to trigger its action")
    sub.setFont(QFont("Segoe UI", 10))
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    sub.setStyleSheet(f"color: {MUTED};")
    lay.addWidget(sub)

    # Grid 2 columns
    grid = QHBoxLayout()
    grid.setSpacing(10)
    col1 = QVBoxLayout()
    col2 = QVBoxLayout()
    col1.setSpacing(8)
    col2.setSpacing(8)

    gestures = [
        ("✊", "Fist",           "Play / Pause"),
        ("🖐", "Open Palm",      "Skip forward"),
        ("☝",  "Index Finger",   "Move cursor (Air Mouse)"),
        ("✌",  "Peace Sign",     "Right-click (Air Mouse)"),
        ("🤟", "Three Fingers",  "Scroll (Air Mouse)"),
        ("👍", "Thumb Up",       "Volume Up"),
        ("👎", "Thumb Down",     "Volume Down"),
        ("🤏", "Pinch",          "Left-click (Air Mouse)"),
        ("👌", "OK Sign",        "Double-click (Air Mouse)"),
        ("🤙", "Shaka",          "Mute toggle"),
        ("🤘", "Rock On",        "Next / Right Arrow"),
    ]

    for idx, (icon, name, action) in enumerate(gestures):
        chip = _GestureChip(icon, name, action)
        (col1 if idx % 2 == 0 else col2).addWidget(chip)

    grid.addLayout(col1)
    grid.addLayout(col2)
    lay.addLayout(grid)
    lay.addStretch()
    return page


def _build_step4() -> QWidget:
    """Done — CTA."""
    page = QWidget()
    lay  = QVBoxLayout(page)
    lay.setContentsMargins(80, 60, 80, 20)
    lay.setSpacing(20)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

    icon = QLabel("🎉")
    icon.setFont(QFont("Segoe UI Emoji", 72))
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(icon)

    title = QLabel("You're all set!")
    title.setFont(QFont("Segoe UI Black", 28, QFont.Weight.Black))
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(f"color: {GREEN};")
    lay.addWidget(title)

    desc = QLabel(
        "Click **Start Tracking** on the Dashboard to begin.\n"
        "Enable **Air Mouse** mode to control your cursor with gestures.\n"
        "Visit the **AI Assistant** tab for help at any time."
    )
    desc.setFont(QFont("Segoe UI", 13))
    desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desc.setWordWrap(True)
    desc.setStyleSheet(f"color: {TEXT};")
    desc.setTextFormat(Qt.TextFormat.RichText)
    lay.addWidget(desc)
    lay.addStretch()
    return page


# ── Main Onboarding Widget ─────────────────────────────────────────────────────

class OnboardingPage(QWidget):
    """
    Emits `finished` when the user clicks 'Get Started' on the last step.
    Parent (ui/app.py) should switch to the dashboard page on this signal.
    """
    from PyQt6.QtCore import pyqtSignal
    finished = pyqtSignal()

    STEPS = [
        ("Welcome",        _build_step1),
        ("Camera Setup",   _build_step2),
        ("Gesture Guide",  _build_step3),
        ("Ready!",         _build_step4),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        top = QWidget()
        top.setFixedHeight(56)
        top.setStyleSheet(f"background: {BG2}; border-bottom: 1px solid {BORDER};")
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(28, 0, 28, 0)
        app_label = QLabel("🖐  GestureSense")
        app_label.setFont(QFont("Segoe UI Black", 13, QFont.Weight.Black))
        app_label.setStyleSheet(f"color: {WHITE};")
        top_lay.addWidget(app_label)
        top_lay.addStretch()
        skip_btn = QPushButton("Skip setup →")
        skip_btn.setFixedHeight(30)
        skip_btn.setStyleSheet(f"color: {MUTED}; border: none; background: transparent;")
        skip_btn.clicked.connect(self.finished.emit)
        top_lay.addWidget(skip_btn)
        root.addWidget(top)

        # Stacked pages
        self._stack = QStackedWidget()
        for _, builder in self.STEPS:
            self._stack.addWidget(builder())
        root.addWidget(self._stack, 1)

        # Bottom navigation
        bottom = QWidget()
        bottom.setFixedHeight(72)
        bottom.setStyleSheet(f"background: {BG2}; border-top: 1px solid {BORDER};")
        bot_lay = QHBoxLayout(bottom)
        bot_lay.setContentsMargins(40, 0, 40, 0)
        bot_lay.setSpacing(16)

        self._back_btn = QPushButton("← Back")
        self._back_btn.setFixedSize(120, 42)
        self._back_btn.clicked.connect(self._prev)
        self._back_btn.setEnabled(False)
        bot_lay.addWidget(self._back_btn)

        self._dots = _StepDots(len(self.STEPS))
        bot_lay.addWidget(self._dots, 1, Qt.AlignmentFlag.AlignCenter)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setFixedSize(160, 42)
        self._next_btn.setObjectName("primary")
        self._next_btn.clicked.connect(self._next)
        bot_lay.addWidget(self._next_btn)

        root.addWidget(bottom)
        self._update_nav()

    def _update_nav(self):
        idx = self._current
        total = len(self.STEPS)
        self._stack.setCurrentIndex(idx)
        self._dots.set_step(idx)
        self._back_btn.setEnabled(idx > 0)
        if idx == total - 1:
            self._next_btn.setText("🚀  Get Started!")
        else:
            step_name = self.STEPS[idx + 1][0]
            self._next_btn.setText(f"Next: {step_name} →")

    def _next(self):
        if self._current >= len(self.STEPS) - 1:
            self.finished.emit()
        else:
            self._current += 1
            self._update_nav()

    def _prev(self):
        if self._current > 0:
            self._current -= 1
            self._update_nav()
