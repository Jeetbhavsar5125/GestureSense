"""
ui/widgets/logo.py
==================
Painted GestureSense logo — a rounded rectangle with gradient background
and a simplified hand silhouette drawn using QPainter.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import (
    QPainter, QBrush, QPen, QColor, QRadialGradient
)


class LogoWidget(QWidget):
    def __init__(self, size: int = 48, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self._size

        # Gradient background
        grad = QRadialGradient(s / 2, s / 2, s / 2)
        grad.setColorAt(0.0, QColor("#7c3aed"))
        grad.setColorAt(1.0, QColor("#00e5ff"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, s, s, s * 0.22, s * 0.22)

        # Hand silhouette
        p.setPen(QPen(QColor("white"), max(1, s // 18)))
        p.setBrush(QBrush(QColor("white")))
        cx = s // 2

        palm_x = int(cx - s * 0.22)
        palm_y = int(s * 0.45)
        palm_w = int(s * 0.44)
        palm_h = int(s * 0.38)
        p.drawRoundedRect(palm_x, palm_y, palm_w, palm_h, s * 0.06, s * 0.06)

        fw  = int(s * 0.09)
        fhs = [int(s * 0.30), int(s * 0.36), int(s * 0.38),
               int(s * 0.34), int(s * 0.26)]
        fxs = [int(palm_x - fw // 2 + i * (palm_w // 4 - 1))
               for i in range(5)]
        fy  = int(palm_y - max(fhs) + s * 0.04)

        for fx, fh in zip(fxs, fhs):
            p.drawRoundedRect(fx, fy + (max(fhs) - fh), fw, fh, fw // 2, fw // 2)
