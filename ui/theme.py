"""
ui/theme.py
===========
Shared color palette and Qt stylesheet for GestureSense.
Import colors and APP_STYLE from here — never define colors inline.
"""

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = "#050d1a"
BG2     = "#0a1628"
BG3     = "#0f1f38"
CARD    = "#0d1f3c"
ACCENT  = "#00e5ff"
ACCENT2 = "#7c3aed"
GREEN   = "#00ff88"
ORANGE  = "#ff9500"
RED     = "#ff3b5c"
WHITE   = "#f0f8ff"
MUTED   = "#4a6080"
TEXT    = "#a8c4e0"
BORDER  = "#1a3050"

# ── High Contrast Palette (Feature 8 — Accessibility Mode) ────────────────────
HC_BG      = "#000000"
HC_BG2     = "#0a0a0a"
HC_BG3     = "#141414"
HC_CARD    = "#0f0f0f"
HC_ACCENT  = "#ffff00"    # bright yellow
HC_GREEN   = "#00ff00"
HC_ORANGE  = "#ff8800"
HC_RED     = "#ff0000"
HC_WHITE   = "#ffffff"
HC_MUTED   = "#aaaaaa"
HC_BORDER  = "#555555"

# ── Global Qt Stylesheet ───────────────────────────────────────────────────────
APP_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {WHITE};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QLabel {{ color: {WHITE}; background: transparent; }}

/* ── Buttons ── */
QPushButton {{
    background: {BG3};
    color: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
    background: rgba(0,229,255,0.07);
}}
QPushButton:pressed {{ background: rgba(0,229,255,0.15); }}

QPushButton#primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT2}, stop:1 {ACCENT});
    color: #050d1a;
    border: none;
    font-weight: 700;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #9b59f5, stop:1 #33eeff);
}}

QPushButton#danger  {{ border-color: {RED};   color: {RED};   }}
QPushButton#danger:hover  {{ background: rgba(255,59,92,0.12); }}
QPushButton#success {{
    background: rgba(0,255,136,0.10);
    border-color: {GREEN}; color: {GREEN};
}}
QPushButton#success:hover {{ background: rgba(0,255,136,0.18); }}

/* ── Sidebar nav buttons ── */
QPushButton#nav {{
    background: transparent;
    border: none;
    border-radius: 10px;
    text-align: left;
    padding: 11px 16px;
    font-size: 13px;
    color: {MUTED};
}}
QPushButton#nav:hover {{
    background: rgba(0,229,255,0.06);
    color: {WHITE};
}}
QPushButton#nav_active {{
    background: rgba(0,229,255,0.12);
    border: none;
    border-left: 3px solid {ACCENT};
    border-radius: 10px;
    text-align: left;
    padding: 11px 13px;
    font-size: 13px;
    color: {ACCENT};
    font-weight: 700;
}}

/* ── Inputs ── */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background: {BG2};
    color: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {BG3};
    color: {WHITE};
    border: 1px solid {BORDER};
    selection-background-color: rgba(0,229,255,0.15);
    padding: 4px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}

/* ── Scrollbars ── */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {BG2}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── Sliders ── */
QSlider::groove:horizontal {{
    background: {BORDER}; height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT}; width: 14px; height: 14px;
    border-radius: 7px; margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT}; border-radius: 2px;
}}
"""

# ── High Contrast Stylesheet (Feature 8 — Accessibility) ─────────────────────
HIGH_CONTRAST_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {HC_BG};
    color: {HC_WHITE};
    font-family: 'Segoe UI', Arial, sans-serif;
}}
QLabel {{ color: {HC_WHITE}; background: transparent; }}

QPushButton {{
    background: {HC_BG3};
    color: {HC_WHITE};
    border: 2px solid {HC_BORDER};
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton:hover {{
    border-color: {HC_ACCENT};
    color: {HC_ACCENT};
    background: rgba(255,255,0,0.10);
}}
QPushButton:pressed {{ background: rgba(255,255,0,0.20); }}

QPushButton#primary {{
    background: {HC_ACCENT};
    color: #000000;
    border: none;
    font-weight: 800;
}}
QPushButton#danger  {{ border-color: {HC_RED};   color: {HC_RED};   }}
QPushButton#success {{ border-color: {HC_GREEN}; color: {HC_GREEN}; background: rgba(0,255,0,0.10); }}

QPushButton#nav {{
    background: transparent;
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 12px 16px;
    font-size: 14px;
    color: {HC_MUTED};
}}
QPushButton#nav:hover  {{ background: rgba(255,255,0,0.08); color: {HC_WHITE}; }}
QPushButton#nav_active {{
    background: rgba(255,255,0,0.15);
    border: none;
    border-left: 3px solid {HC_ACCENT};
    border-radius: 8px;
    text-align: left;
    padding: 12px 13px;
    font-size: 14px;
    color: {HC_ACCENT};
    font-weight: 800;
}}

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background: {HC_BG2};
    color: {HC_WHITE};
    border: 2px solid {HC_BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 14px;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {HC_ACCENT}; }}
QComboBox QAbstractItemView {{
    background: {HC_BG3};
    color: {HC_WHITE};
    border: 2px solid {HC_BORDER};
    selection-background-color: rgba(255,255,0,0.20);
}}
QScrollBar:vertical {{ background: {HC_BG2}; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background: {HC_BORDER}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {HC_ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QSlider::groove:horizontal {{ background: {HC_BORDER}; height: 6px; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {HC_ACCENT}; width: 18px; height: 18px;
    border-radius: 9px; margin: -6px 0;
}}
QSlider::sub-page:horizontal {{ background: {HC_ACCENT}; border-radius: 3px; }}
"""


def get_stylesheet(high_contrast: bool = False) -> str:
    """Return the appropriate stylesheet based on accessibility setting."""
    return HIGH_CONTRAST_STYLE if high_contrast else APP_STYLE
