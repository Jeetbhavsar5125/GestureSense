"""
ui/pages/gestures.py
====================
Gesture Mappings page.

Sections:
  1. Quick-Launch Sites  — click any site badge to pre-fill the add-gesture panel
  2. Gesture Cards       — scrollable list (built-in + custom) with inline editing
  3. Add Custom Gesture  — finger-toggle panel at the bottom
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QLineEdit, QComboBox, QDoubleSpinBox,
    QGridLayout, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui  import QFont

from ui.theme     import (
    BG2, BG3, CARD, ACCENT, ACCENT2, GREEN, ORANGE,
    RED, WHITE, MUTED, BORDER, TEXT,
)
from ui.constants import KEY_OPTIONS, QUICK_SITES, find_option_index
from ui.widgets.gesture_card import GestureCard


class GesturesPage(QWidget):
    """
    Callbacks (all optional)
    ------------------------
    on_action_change(gesture_id, key, key_type)   – save new action
    on_cooldown_change(gesture_id, cooldown)       – save new cooldown
    on_add_gesture(pattern, mapping)               – register new custom gesture
    on_delete_gesture(gesture_id)                  – remove custom gesture
    """

    def __init__(
        self,
        cfg: dict,
        on_action_change=None,
        on_cooldown_change=None,
        on_add_gesture=None,
        on_delete_gesture=None,
        parent=None,
    ):
        super().__init__(parent)
        self._cfg                = cfg
        self._on_action_change   = on_action_change
        self._on_cooldown_change = on_cooldown_change
        self._on_add_gesture     = on_add_gesture
        self._on_delete_gesture  = on_delete_gesture

        self._cards: dict[str, GestureCard] = {}
        self._build_ui()
        self._populate_cards()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self._inner_lay = QVBoxLayout(inner)
        self._inner_lay.setContentsMargins(24, 24, 24, 24)
        self._inner_lay.setSpacing(18)

        # ── 1. Quick-launch sites ──────────────────────────────────────────────
        self._inner_lay.addWidget(self._build_quick_sites_section())

        # ── 2. Gesture cards container (populated later) ───────────────────────
        self._cards_header = self._section_header("🎯  Gesture Mappings",
            "Click the action dropdown on any row to change what a gesture does.")
        self._inner_lay.addWidget(self._cards_header)

        self._cards_container = QVBoxLayout()
        self._cards_container.setSpacing(8)
        self._inner_lay.addLayout(self._cards_container)

        # ── 3. Add custom gesture ──────────────────────────────────────────────
        self._inner_lay.addWidget(self._build_add_panel())
        self._inner_lay.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll)

    def _build_quick_sites_section(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lay.addWidget(self._section_header(
            "🌐  Quick-Launch Sites",
            "Click a site to pre-fill the Add Gesture panel below with its URL.",
        ))

        grid = QHBoxLayout()
        grid.setSpacing(8)

        for emoji, name, url in QUICK_SITES:
            btn = self._site_badge(emoji, name, url)
            grid.addWidget(btn)

        grid.addStretch()
        lay.addLayout(grid)
        return w

    def _site_badge(self, emoji: str, name: str, url: str) -> QPushButton:
        btn = QPushButton(f"{emoji}  {name}")
        btn.setFixedHeight(38)
        btn.setFont(QFont("Segoe UI", 10))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {BG3};
                border: 1px solid {BORDER};
                border-radius: 8px;
                color: {TEXT};
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
                color: {ACCENT};
                background: rgba(0,229,255,0.07);
            }}
        """)
        btn.clicked.connect(lambda _, u=url: self._prefill_url(u))
        return btn

    def _build_add_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("addPanel")
        frame.setStyleSheet(f"""
            QFrame#addPanel {{
                background: {BG2};
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)

        # Header
        hdr = QLabel("➕  Add Custom Gesture")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {ACCENT};")
        lay.addWidget(hdr)

        desc = QLabel(
            "Toggle which fingers should be UP to define the gesture's fingerprint."
        )
        desc.setFont(QFont("Segoe UI", 10))
        desc.setStyleSheet(f"color: {MUTED};")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Finger toggles
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)
        self._finger_btns = []
        finger_labels = [
            "👍 Thumb", "☝ Index", "🖕 Middle", "💍 Ring", "🤙 Pinky"
        ]
        for name in finger_labels:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setFixedHeight(46)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG3};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    color: {MUTED};
                    font-size: 10px;
                }}
                QPushButton:checked {{
                    background: rgba(0,229,255,0.12);
                    border-color: {ACCENT};
                    color: {ACCENT};
                    font-weight: bold;
                }}
            """)
            self._finger_btns.append(btn)
            toggle_row.addWidget(btn)
        lay.addLayout(toggle_row)

        # Pattern preview
        self._pattern_lbl = QLabel("Pattern: 00000")
        self._pattern_lbl.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        self._pattern_lbl.setStyleSheet(f"color: {ORANGE};")
        lay.addWidget(self._pattern_lbl)
        for btn in self._finger_btns:
            btn.toggled.connect(self._update_pattern)

        # Form grid
        grid = QGridLayout()
        grid.setSpacing(10)

        # Row 0: name + icon
        grid.addWidget(self._form_label("Gesture Name"), 0, 0)
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Open Dashboard")
        grid.addWidget(self._name_input, 0, 1)

        grid.addWidget(self._form_label("Icon (emoji)"), 0, 2)
        self._icon_input = QLineEdit()
        self._icon_input.setPlaceholderText("🤌")
        self._icon_input.setFixedWidth(70)
        grid.addWidget(self._icon_input, 0, 3)

        # Row 1: key action combo
        grid.addWidget(self._form_label("Key Action"), 1, 0)
        self._key_combo = QComboBox()
        for label, _, _, _ in KEY_OPTIONS:
            self._key_combo.addItem(label)
        self._key_combo.currentIndexChanged.connect(self._on_key_combo_changed)
        grid.addWidget(self._key_combo, 1, 1)

        # Custom value input
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("Enter URL, text, or key…")
        self._key_input.hide()
        grid.addWidget(self._key_input, 1, 2, 1, 2)

        # Row 2: cooldown
        grid.addWidget(self._form_label("Cooldown (sec)"), 2, 0)
        self._cd_spin = QDoubleSpinBox()
        self._cd_spin.setRange(0.1, 10.0)
        self._cd_spin.setSingleStep(0.1)
        self._cd_spin.setValue(1.0)
        grid.addWidget(self._cd_spin, 2, 1)

        lay.addLayout(grid)

        add_btn = QPushButton("  ✚  ADD GESTURE")
        add_btn.setObjectName("primary")
        add_btn.setFixedHeight(44)
        add_btn.clicked.connect(self._add_gesture)
        lay.addWidget(add_btn)
        return frame

    # ── Populate gesture cards ─────────────────────────────────────────────────

    def _populate_cards(self):
        # Clear existing
        while self._cards_container.count():
            item = self._cards_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        # Built-in
        for gid, mapping in self._cfg.get("mappings", {}).items():
            card = GestureCard(
                gid, mapping, is_custom=False,
                on_action_change=self._on_action_change,
                on_cooldown_change=self._on_cooldown_change,
            )
            self._cards[gid] = card
            self._cards_container.addWidget(card)

        # Custom
        for gid, mapping in self._cfg.get("custom", {}).items():
            card = GestureCard(
                gid, mapping, is_custom=True,
                on_delete=self._delete_gesture,
                on_action_change=self._on_action_change,
                on_cooldown_change=self._on_cooldown_change,
            )
            self._cards[gid] = card
            self._cards_container.addWidget(card)

    def refresh(self):
        """Re-build all cards from current cfg (call after add/delete)."""
        self._populate_cards()

    # ── Highlight active gesture ──────────────────────────────────────────────

    def highlight_card(self, gesture_name: str) -> None:
        for gid, card in self._cards.items():
            card.set_active(gid == gesture_name)

    # ── Add gesture ───────────────────────────────────────────────────────────

    def _update_pattern(self):
        p = "".join("1" if b.isChecked() else "0" for b in self._finger_btns)
        self._pattern_lbl.setText(f"Pattern: {p}")

    def _on_key_combo_changed(self, idx: int):
        _, _, _, needs = KEY_OPTIONS[idx]
        self._key_input.setVisible(needs)
        if needs:
            self._key_input.setFocus()
            # Update placeholder based on type
            _, kv, kt, _ = KEY_OPTIONS[idx]
            if kv == "__url__":
                self._key_input.setPlaceholderText("https://example.com")
            elif kv == "__type__":
                self._key_input.setPlaceholderText("Text to auto-type…")
            else:
                self._key_input.setPlaceholderText("e.g. a  or  ctrl+s")

    def _prefill_url(self, url: str):
        """Called when a Quick-Site badge is clicked."""
        # Find "Custom URL…" option and select it
        for idx, (_, kv, _, _) in enumerate(KEY_OPTIONS):
            if kv == "__url__":
                self._key_combo.setCurrentIndex(idx)
                break
        self._key_input.setText(url)
        self._key_input.show()
        # Scroll to add panel (rough — just show the text)
        self._name_input.setFocus()

    def _add_gesture(self):
        pattern = "".join("1" if b.isChecked() else "0" for b in self._finger_btns)
        if pattern == "00000":
            QMessageBox.warning(self, "Invalid Pattern",
                                "Please select at least one finger to be UP.")
            return
        if pattern in self._cfg.get("mappings", {}) or \
           pattern in self._cfg.get("custom", {}):
            QMessageBox.warning(self, "Pattern Conflict",
                                f"Pattern {pattern} is already mapped to a gesture.")
            return

        name = self._name_input.text().strip() or "Custom Gesture"
        icon = self._icon_input.text().strip() or "🤌"
        cd   = self._cd_spin.value()

        idx = self._key_combo.currentIndex()
        _, kv, kt, needs = KEY_OPTIONS[idx]

        if needs:
            raw = self._key_input.text().strip()
            if not raw:
                QMessageBox.warning(self, "Missing Value",
                                    "Please fill in the custom value field.")
                return
            if kv == "__url__":
                if not raw.startswith(("http://", "https://", "file://")):
                    raw = "https://" + raw
                kv, kt = raw, "url"
            elif kv == "__type__":
                kv, kt = raw, "type"
            else:
                kv, kt = raw, ("hotkey" if "+" in raw else "char")

        mapping = {
            "label":    name,
            "icon":     icon,
            "key":      kv,
            "key_type": kt,
            "cooldown": cd,
        }

        if self._on_add_gesture:
            self._on_add_gesture(pattern, mapping)

        # Reset form
        for b in self._finger_btns:
            b.setChecked(False)
        self._name_input.clear()
        self._icon_input.clear()
        self._key_input.clear()
        self._cd_spin.setValue(1.0)

    def _delete_gesture(self, gesture_id: str):
        if self._on_delete_gesture:
            self._on_delete_gesture(gesture_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _section_header(title: str, sub: str = "") -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {WHITE};")
        lay.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setFont(QFont("Segoe UI", 10))
            s.setStyleSheet(f"color: {MUTED};")
            s.setWordWrap(True)
            lay.addWidget(s)
        return w

    @staticmethod
    def _form_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet(f"color: {TEXT};")
        return lbl
