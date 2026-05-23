"""
ui/widgets/gesture_card.py
==========================
Individual gesture mapping card.

Layout (horizontal):
  [Icon] | [Name / ID] | [Action Combo] [Custom Input?] | [Cooldown] | [●] | [✕]

Changes to key action or cooldown auto-save via the provided callbacks.
"""

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QComboBox, QLineEdit, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui  import QFont

from ui.theme     import WHITE, MUTED, CARD, BORDER, ACCENT
from ui.constants import KEY_OPTIONS, find_option_index


class GestureCard(QFrame):
    """
    Parameters
    ----------
    gesture_id        : str   – gesture key ("fist", "11001", …)
    mapping           : dict  – {"label", "icon", "key", "key_type", "cooldown"}
    is_custom         : bool
    on_delete         : callable(gesture_id) | None
    on_action_change  : callable(gesture_id, key, key_type) | None
    on_cooldown_change: callable(gesture_id, cooldown_float) | None
    """

    def __init__(
        self,
        gesture_id: str,
        mapping: dict,
        is_custom: bool = False,
        on_delete=None,
        on_action_change=None,
        on_cooldown_change=None,
        parent=None,
    ):
        super().__init__(parent)
        self._id        = gesture_id
        self._mapping   = mapping
        self._is_custom = is_custom
        self._active    = False
        self._on_delete          = on_delete
        self._on_action_change   = on_action_change
        self._on_cooldown_change = on_cooldown_change

        # Debounce timer for custom text input changes
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._save_custom_input)

        self.setObjectName("gestureCard")
        self._apply_style(active=False)
        self._build_ui()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(12)

        # Icon
        icon_lbl = QLabel(self._mapping.get("icon", "🤌"))
        icon_lbl.setFont(QFont("Segoe UI Emoji", 22))
        icon_lbl.setFixedWidth(40)
        root.addWidget(icon_lbl)

        # Name + ID column
        info = QVBoxLayout()
        info.setSpacing(2)

        name_lbl = QLabel(self._mapping.get("label", "Custom"))
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {WHITE};")

        id_lbl = QLabel(f"ID: {self._id}")
        id_lbl.setFont(QFont("Courier New", 8))
        id_lbl.setStyleSheet(f"color: {MUTED};")

        info.addWidget(name_lbl)
        info.addWidget(id_lbl)
        root.addLayout(info, 1)

        # Action combo + optional custom input
        action_col = QVBoxLayout()
        action_col.setSpacing(4)

        self._combo = QComboBox()
        self._combo.setFixedWidth(230)
        for label, _, _, _ in KEY_OPTIONS:
            self._combo.addItem(label)

        # Pre-select current mapping
        cur_key  = self._mapping.get("key", "")
        cur_type = self._mapping.get("key_type", "none")
        idx, custom_val = find_option_index(cur_key, cur_type)
        self._combo.setCurrentIndex(idx)

        self._custom_input = QLineEdit()
        self._custom_input.setPlaceholderText("Enter value…")
        self._custom_input.setFixedWidth(230)
        self._custom_input.setText(custom_val)

        _, _, _, needs = KEY_OPTIONS[idx]
        self._custom_input.setVisible(needs)

        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._custom_input.textChanged.connect(
            lambda: self._debounce.start(600)
        )

        action_col.addWidget(self._combo)
        action_col.addWidget(self._custom_input)
        root.addLayout(action_col)

        # Cooldown slider
        cd_col = QVBoxLayout()
        cd_col.setSpacing(3)
        cd_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._cd_lbl = QLabel(f"⏱ {self._mapping.get('cooldown', 1.0):.1f}s")
        self._cd_lbl.setFont(QFont("Courier New", 9))
        self._cd_lbl.setStyleSheet(f"color: {ACCENT};")
        self._cd_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(1, 100)
        self._slider.setValue(int(self._mapping.get("cooldown", 1.0) * 10))
        self._slider.setFixedWidth(100)
        self._slider.valueChanged.connect(self._on_slider_changed)

        cd_col.addWidget(self._cd_lbl)
        cd_col.addWidget(self._slider)
        root.addLayout(cd_col)

        # Active indicator dot
        self._dot = QLabel("●")
        self._dot.setFont(QFont("Segoe UI", 14))
        self._dot.setStyleSheet(f"color: {MUTED};")
        self._dot.setFixedWidth(22)
        root.addWidget(self._dot)

        # Delete button (custom gestures only)
        if self._is_custom and self._on_delete:
            del_btn = QPushButton("✕")
            del_btn.setObjectName("danger")
            del_btn.setFixedSize(34, 34)
            del_btn.setToolTip("Delete this gesture")
            del_btn.clicked.connect(lambda: self._on_delete(self._id))
            root.addWidget(del_btn)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_combo_changed(self, idx: int):
        _, kv, kt, needs = KEY_OPTIONS[idx]
        self._custom_input.setVisible(needs)
        if needs:
            self._custom_input.setFocus()
            return  # wait for user input
        if self._on_action_change:
            self._on_action_change(self._id, kv, kt)

    def _save_custom_input(self):
        idx = self._combo.currentIndex()
        _, kv, kt, needs = KEY_OPTIONS[idx]
        if not needs:
            return
        raw = self._custom_input.text().strip()
        if not raw:
            return
        # Resolve sentinel to real value
        if kv == "__url__":
            if not raw.startswith(("http://", "https://", "file://")):
                raw = "https://" + raw
            real_type = "url"
        elif kv == "__type__":
            real_type = "type"
        else:
            real_type = "hotkey" if "+" in raw else "char"
        if self._on_action_change:
            self._on_action_change(self._id, raw, real_type)

    def _on_slider_changed(self, v: int):
        cd = v / 10.0
        self._cd_lbl.setText(f"⏱ {cd:.1f}s")
        if self._on_cooldown_change:
            self._on_cooldown_change(self._id, cd)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        col = "#00e5ff" if active else MUTED
        self._dot.setStyleSheet(f"color: {col};")
        self._apply_style(active=active)

    def _apply_style(self, active: bool) -> None:
        bg  = "rgba(0,229,255,0.06)" if active else CARD
        brd = "#00e5ff"              if active else BORDER
        self.setStyleSheet(f"""
            QFrame#gestureCard {{
                background: {bg};
                border: 1px solid {brd};
                border-radius: 12px;
            }}
        """)
