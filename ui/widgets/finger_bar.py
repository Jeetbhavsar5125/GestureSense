"""
ui/widgets/finger_bar.py
========================
Animated bar chart showing which fingers are currently up (lit) or down (dim).
Labels: T=Thumb, I=Index, M=Middle, R=Ring, P=Pinky.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QPainter, QBrush, QPen, QColor, QFont

from ui.theme import ACCENT, BORDER, MUTED


class FingerBar(QWidget):
    _NAMES   = ["T", "I", "M", "R", "P"]
    _HEIGHTS = [28, 38, 40, 36, 30]   # relative bar heights (px)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fingers = [0, 0, 0, 0, 0]
        self.setFixedSize(145, 78)

    def set_fingers(self, fingers: list) -> None:
        if list(fingers) != self._fingers:
            self._fingers = list(fingers)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h  = self.width(), self.height()
        gap   = w // 5
        bar_w = 18

        for i, (name, up) in enumerate(zip(self._NAMES, self._fingers)):
            bh  = self._HEIGHTS[i]
            x   = i * gap + gap // 2 - bar_w // 2
            y   = h - 16 - bh
            col = QColor(ACCENT) if up else QColor(BORDER)

            p.setBrush(QBrush(col))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, y, bar_w, bh, 4, 4)

            # Glow effect on raised finger
            if up:
                glow = QColor(ACCENT)
                glow.setAlpha(40)
                p.setBrush(QBrush(glow))
                p.drawRoundedRect(x - 2, y - 2, bar_w + 4, bh + 4, 5, 5)

            p.setPen(QPen(QColor(MUTED)))
            p.setFont(QFont("Segoe UI", 7))
            p.drawText(
                x, h - 4, bar_w, 12,
                Qt.AlignmentFlag.AlignHCenter,
                name,
            )
