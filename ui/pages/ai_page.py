"""
ui/pages/ai_page.py
===================
AI Assistant chat page for GestureSense.
A beautiful chat-style interface with bubble messages, quick-action chips,
markdown-like rendering, and a typing indicator.
"""

import time
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QLineEdit,
    QSizePolicy, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui  import QFont, QColor, QPainter, QBrush, QPen

from ui.theme import (
    BG, BG2, BG3, CARD, ACCENT, ACCENT2, GREEN,
    WHITE, MUTED, BORDER, TEXT, ORANGE,
)
from core.ai_assistant import AIAssistant


# ─────────────────────────────────────────────────────────────────────────────
#  Message Bubble Widget
# ─────────────────────────────────────────────────────────────────────────────

class MessageBubble(QFrame):
    """A single chat message bubble (user or assistant)."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self._is_user = is_user
        self._build(text, is_user)

    def _build(self, text: str, is_user: bool):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(8)

        if is_user:
            outer.addStretch()

        # Avatar
        if not is_user:
            av = _AvatarWidget("🤖", ACCENT2)
            outer.addWidget(av, alignment=Qt.AlignmentFlag.AlignTop)

        # Bubble
        bubble = QFrame()
        if is_user:
            bubble.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {ACCENT2}, stop:1 {ACCENT});
                    border-radius: 16px;
                    border-bottom-right-radius: 4px;
                }}
            """)
        else:
            bubble.setStyleSheet(f"""
                QFrame {{
                    background: {BG3};
                    border: 1px solid {BORDER};
                    border-radius: 16px;
                    border-bottom-left-radius: 4px;
                }}
            """)

        b_lay = QVBoxLayout(bubble)
        b_lay.setContentsMargins(16, 12, 16, 12)
        b_lay.setSpacing(2)

        # Render text with basic markdown-like formatting
        lbl = _MarkdownLabel(text, is_user)
        b_lay.addWidget(lbl)

        bubble.setMaximumWidth(520)
        outer.addWidget(bubble)

        if not is_user:
            outer.addStretch()

        if is_user:
            av = _AvatarWidget("👤", MUTED)
            outer.addWidget(av, alignment=Qt.AlignmentFlag.AlignTop)


class _AvatarWidget(QWidget):
    def __init__(self, emoji: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self._emoji = emoji
        self._color = QColor(color)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 36, 36)
        p.setFont(QFont("Segoe UI Emoji", 16))
        p.setPen(QPen(QColor(WHITE)))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._emoji)


class _MarkdownLabel(QLabel):
    """QLabel that renders **bold** and _italic_ markdown-like text."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setFont(QFont("Segoe UI", 11))
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setOpenExternalLinks(False)

        color = "#050d1a" if is_user else WHITE
        html = self._to_html(text, color)
        self.setText(html)
        self.setStyleSheet(f"color: {color}; background: transparent;")

    @staticmethod
    def _to_html(text: str, color: str) -> str:
        import re
        # Escape HTML
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # **bold**
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # _italic_
        text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
        # `code`
        text = re.sub(
            r"`(.+?)`",
            rf'<code style="background:rgba(0,229,255,0.15);padding:1px 4px;border-radius:3px;font-family:monospace;">\1</code>',
            text
        )
        # Newlines → <br>
        text = text.replace("\n", "<br>")
        # Horizontal rule ---
        text = re.sub(r"<br>---<br>", f'<hr style="border:1px solid {BORDER};">', text)
        return text


# ─────────────────────────────────────────────────────────────────────────────
#  Typing Indicator
# ─────────────────────────────────────────────────────────────────────────────

class _TypingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dots = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(36)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        av = _AvatarWidget("🤖", ACCENT2)
        lay.addWidget(av, alignment=Qt.AlignmentFlag.AlignTop)

        self._lbl = QLabel("●  ●  ●")
        self._lbl.setFont(QFont("Segoe UI", 11))
        self._lbl.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(self._lbl)
        lay.addStretch()

    def start(self):
        self._dots = 0
        self._timer.start(400)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._dots = (self._dots + 1) % 4
        dots = ("●" * self._dots).ljust(3, "○").replace("", "  ")[:-2]
        filled = "●" * self._dots
        empty  = "○" * (3 - self._dots)
        self._lbl.setText(f"{filled}  {empty}")


# ─────────────────────────────────────────────────────────────────────────────
#  Quick-Action Chip
# ─────────────────────────────────────────────────────────────────────────────

class _Chip(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,229,255,0.08);
                border: 1px solid {ACCENT};
                border-radius: 16px;
                color: {ACCENT};
                font-size: 12px;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background: rgba(0,229,255,0.18);
            }}
            QPushButton:pressed {{
                background: rgba(0,229,255,0.28);
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
#  AI Page
# ─────────────────────────────────────────────────────────────────────────────

QUICK_ACTIONS = [
    "List all gestures",
    "How does Air Mouse work?",
    "What gesture for next slide?",
    "Gestures firing accidentally",
    "How to map a gesture?",
    "Camera not working",
]


class AIPage(QWidget):
    def __init__(self, ai: AIAssistant, parent=None):
        super().__init__(parent)
        self._ai = ai
        self._build_ui()
        # Show welcome on first open (deferred so scroll is ready)
        QTimer.singleShot(200, self._show_welcome)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_chat_area(), 1)
        root.addWidget(self._build_chips_row())
        root.addWidget(self._build_input_bar())

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(72)
        bar.setStyleSheet(f"""
            QWidget {{
                background: {BG2};
                border-bottom: 1px solid {BORDER};
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(28, 0, 28, 0)
        lay.setSpacing(14)

        icon = QLabel("🤖")
        icon.setFont(QFont("Segoe UI Emoji", 26))
        lay.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(1)
        title = QLabel("GestureSense AI")
        title.setFont(QFont("Segoe UI Black", 14, QFont.Weight.Black))
        title.setStyleSheet(f"color: {WHITE};")
        sub = QLabel("Local assistant — no internet needed")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {MUTED};")
        col.addWidget(title)
        col.addWidget(sub)
        lay.addLayout(col, 1)

        # Status dot
        dot_frame = QFrame()
        dot_frame.setFixedSize(10, 10)
        dot_frame.setStyleSheet(f"""
            QFrame {{
                background: {GREEN};
                border-radius: 5px;
            }}
        """)
        status_lbl = QLabel("Online")
        status_lbl.setFont(QFont("Segoe UI", 9))
        status_lbl.setStyleSheet(f"color: {GREEN};")

        status_row = QHBoxLayout()
        status_row.setSpacing(5)
        status_row.addWidget(dot_frame)
        status_row.addWidget(status_lbl)
        lay.addLayout(status_row)

        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setFixedHeight(34)
        clear_btn.clicked.connect(self._clear_chat)
        lay.addWidget(clear_btn)

        return bar

    def _build_chat_area(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"background: {BG}; border: none;")

        container = QWidget()
        container.setStyleSheet(f"background: {BG};")
        self._chat_lay = QVBoxLayout(container)
        self._chat_lay.setContentsMargins(24, 20, 24, 20)
        self._chat_lay.setSpacing(4)
        self._chat_lay.addStretch()

        # Typing indicator (hidden by default)
        self._typing = _TypingIndicator()
        self._typing.hide()
        self._chat_lay.addWidget(self._typing)

        self._scroll.setWidget(container)
        return self._scroll

    def _build_chips_row(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"""
            QWidget {{
                background: {BG2};
                border-top: 1px solid {BORDER};
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(8)

        for label in QUICK_ACTIONS:
            chip = _Chip(label)
            chip.clicked.connect(lambda _, l=label: self._send_message(l))
            lay.addWidget(chip)
        lay.addStretch()
        return bar

    def _build_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"""
            QWidget {{
                background: {BG2};
                border-top: 1px solid {BORDER};
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask me anything about GestureSense…")
        self._input.setFixedHeight(46)
        self._input.setFont(QFont("Segoe UI", 12))
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG3};
                border: 1px solid {BORDER};
                border-radius: 23px;
                padding: 0 18px;
                color: {WHITE};
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
                background: rgba(0,229,255,0.04);
            }}
        """)
        self._input.returnPressed.connect(self._on_send)
        lay.addWidget(self._input, 1)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(46, 46)
        send_btn.setFont(QFont("Segoe UI", 14))
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {ACCENT2}, stop:1 {ACCENT});
                border: none;
                border-radius: 23px;
                color: #050d1a;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #9b59f5, stop:1 #33eeff);
            }}
        """)
        send_btn.clicked.connect(self._on_send)
        lay.addWidget(send_btn)
        return bar

    # ── Message Handling ──────────────────────────────────────────────────────

    def _show_welcome(self):
        self._add_bot_message(
            "👋 Hi! I'm the **GestureSense AI Assistant** — running fully offline.\n\n"
            "I know everything about your gestures, Air Mouse mode, and how to configure actions.\n\n"
            "Try one of the quick buttons below, or ask me anything! ✨"
        )

    def _on_send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._send_message(text)

    def _send_message(self, text: str):
        # Add user bubble
        self._add_user_message(text)
        # Show typing indicator
        self._typing.start()
        self._scroll_to_bottom()

        # Simulate thinking delay in a thread
        def _think():
            time.sleep(0.6)   # natural feel
            response = self._ai.chat(text)
            # Back to main thread via timer
            QTimer.singleShot(0, lambda: self._deliver_response(response))

        threading.Thread(target=_think, daemon=True).start()

    def _deliver_response(self, response: str):
        self._typing.stop()
        self._add_bot_message(response)

    def _add_user_message(self, text: str):
        bubble = MessageBubble(text, is_user=True)
        # Insert before typing indicator
        idx = self._chat_lay.count() - 1  # before typing indicator
        self._chat_lay.insertWidget(idx, bubble)
        self._scroll_to_bottom()

    def _add_bot_message(self, text: str):
        bubble = MessageBubble(text, is_user=False)
        idx = self._chat_lay.count() - 1  # before typing indicator
        self._chat_lay.insertWidget(idx, bubble)
        self._scroll_to_bottom()

    def _clear_chat(self):
        self._ai.clear_history()
        # Remove all MessageBubble widgets (keep stretch + typing)
        widgets_to_remove = []
        for i in range(self._chat_lay.count()):
            item = self._chat_lay.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), MessageBubble):
                widgets_to_remove.append(item.widget())
        for w in widgets_to_remove:
            self._chat_lay.removeWidget(w)
            w.deleteLater()
        # Re-show welcome
        QTimer.singleShot(100, self._show_welcome)

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))
